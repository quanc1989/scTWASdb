/* Read-only figures for stored association records. No statistical inference. */
(function (root, factory) {
    var api = factory(root ? root.ScEvidence : require('./explore-evidence.js'));
    if (typeof module === 'object' && module.exports) module.exports = api;
    if (root) root.ScResults = api;
})(typeof window === 'undefined' ? null : window, function (evidence) {
    'use strict';
    var ns = 'http://www.w3.org/2000/svg';
    var methods = [
        {name:'FUSION', label:'FUSION', z:'fusion_z', p:'fusion_pval', color:'#0f766e'},
        {name:'SPrediXcan', label:'S-PrediXcan', z:'spred_z', p:'spred_pval', color:'#785d96'}
    ];
    function el(tag, attrs, text, parent) {
        var node = document.createElementNS(ns, tag);
        Object.keys(attrs || {}).forEach(function (key) {node.setAttribute(key, attrs[key]);});
        if (text !== undefined) node.textContent = text;
        if (parent) parent.appendChild(node);
        return node;
    }
    function svg(width, height, label) {
        return el('svg', {xmlns:ns, viewBox:'0 0 '+width+' '+height, width:'100%', height:height,
            role:'img', 'aria-label':label, style:'font-family:Arial,sans-serif;background:white'});
    }
    function text(parent, x, y, value, attrs) {
        return el('text', Object.assign({x:x,y:y,fill:'#52616b','font-size':12}, attrs || {}), value, parent);
    }
    function stepFor(span, count) {
        var raw = span / count, power = Math.pow(10, Math.floor(Math.log10(raw)));
        var scaled = raw / power;
        return (scaled >= 5 ? 5 : scaled >= 2 ? 2 : 1) * power;
    }
    function tickText(value, step) {
        if (Math.abs(value) > 1e6 || (step && step < 1e-4)) return value.toExponential(1);
        var digits = step ? Math.max(0, -Math.floor(Math.log10(step))) : 2;
        return Number(value.toFixed(Math.min(8,digits))).toString();
    }
    function signedRange(rows, zeroCentred) {
        var values = [];
        rows.forEach(function (row) {methods.forEach(function (method) {
            var z = evidence.finite(row[method.z]); if (z !== null) values.push(z);
        });});
        if (!values.length) return null;
        var low = Math.min.apply(null, values), high = Math.max.apply(null, values);
        var allPositive = low > 0, allNegative = high < 0;
        var maxAbs = Math.max(Math.abs(low),Math.abs(high),1);
        var span = Math.max(high-low,0.5,maxAbs*0.08), padding = span*0.12;
        var min = low-padding, max = high+padding;
        if (high-low < span) {min = low-(span-(high-low))/2-padding;max=high+(span-(high-low))/2+padding;}
        if (zeroCentred) {max = Math.min(Number.MAX_VALUE,maxAbs*1.08);min = -max;}
        min=Math.max(-Number.MAX_VALUE,min);max=Math.min(Number.MAX_VALUE,max);
        var finiteSpan = max-min;
        var step = Number.isFinite(finiteSpan) ? stepFor(finiteSpan,6) : maxAbs/3;
        if (Number.isFinite(finiteSpan)) {
            min = Math.floor(min/step)*step; max = Math.ceil(max/step)*step;
            if (zeroCentred) {max=Math.max(Math.abs(min),Math.abs(max));min=-max;}
        }
        var ticks=[];
        for (var i=0;i<30;i++) {
            var value=min+i*step;
            if (!Number.isFinite(value) || value>max+step*0.01) break;
            ticks.push({value:value,label:tickText(value,step)});
        }
        return {min:min,max:max,step:step,ticks:ticks,allPositive:allPositive,allNegative:allNegative,
            mode:zeroCentred?'zero-centred':'local',count:values.length};
    }
    function xValue(value, range, width, margin) {
        var scale=Math.max(Math.abs(range.min),Math.abs(range.max),1);
        return margin+(value/scale-range.min/scale)/(range.max/scale-range.min/scale)*(width-2*margin);
    }
    function marker(parent, method, x, y, hit, attrs) {
        attrs=Object.assign({fill:hit?method.color:'white',stroke:method.color,'stroke-width':1.8},attrs || {});
        if (method.name==='SPrediXcan') return el('path',Object.assign(attrs,{d:'M '+x+' '+(y-5)+' L '+(x+5)+' '+y+' L '+x+' '+(y+5)+' L '+(x-5)+' '+y+' Z'}),undefined,parent);
        return el('circle',Object.assign(attrs,{cx:x,cy:y,r:4.5}),undefined,parent);
    }
    function pairedRow(parent, row, range, width, y, index, threshold) {
        var points=[];
        methods.forEach(function (method) {
            var z=evidence.finite(row[method.z]);
            if (z!==null) points.push({method:method,z:z,p:row[method.p],x:xValue(z,range,width,25),y:y});
        });
        if (points.length===2 && Math.abs(points[0].x-points[1].x)<13) {points[0].y-=5;points[1].y+=5;}
        if (points.length===2) el('line',{x1:points[0].x,y1:points[0].y,x2:points[1].x,y2:points[1].y,
            stroke:'#b0bdc2','stroke-width':1,'data-connector-record':index},undefined,parent);
        points.forEach(function (point) {
            var state=evidence.pState(point.p,threshold);
            var attrs={'data-record':index,'data-method':point.method.name,'data-z':String(row[point.method.z]),
                'data-p':String(point.p),'data-p-state':state.state,'data-hit':String(state.passes)};
            if (state.state==='unavailable'||state.state==='invalid') attrs['stroke-dasharray']='2 2';
            var node=marker(parent,point.method,point.x,point.y,state.passes,attrs);
            el('title',{},point.method.label+' · Z '+String(row[point.method.z])+' · nominal P '+evidence.valueText(point.p)+' · '+row.celltype, node);
        });
        if (range.min<=0 && range.max>=0) el('line',{x1:xValue(0,range,width,25),x2:xValue(0,range,width,25),
            y1:y-15,y2:y+15,stroke:'#c9d3d8','stroke-dasharray':'3 3'},undefined,parent);
        if(points.length<2) text(parent,25,y+20,methods.filter(function (method) {
            return evidence.finite(row[method.z])===null;
        }).map(function (method) {return method.label+' Z unavailable';}).join(' · '),{'font-size':10});
    }
    function axis(parent, range, width, y) {
        el('line',{x1:25,x2:width-25,y1:y,y2:y,stroke:'#9eafb7'},undefined,parent);
        range.ticks.forEach(function (tick) {
            if(width<300 && range.ticks.length>7 && range.ticks.indexOf(tick)%2===1) return;
            var x=xValue(tick.value,range,width,25);
            el('line',{x1:x,x2:x,y1:y,y2:y+4,stroke:'#9eafb7'},undefined,parent);
            text(parent,x,y+19,tick.label,{'text-anchor':'middle'});
        });
        text(parent,width/2,y+39,'Signed TWAS Z statistic',{'text-anchor':'middle'});
    }
    function legend(parent, threshold, y) {
        methods.forEach(function (method,index) {
            var x=24+index*154;marker(parent,method,x,y,true);text(parent,x+12,y+4,method.label);
        });
        text(parent,18,y+27,'Filled: nominal P ≤ '+threshold+'; open: above threshold; dashed: P unavailable.');
    }
    function drawPaired(container, rows, options) {
        container.textContent='';
        var range=signedRange(rows,options.zeroCentred);
        var notice=document.createElement('p');notice.className='paired-range-note';
        notice.textContent=options.singleModel?'Two association methods for one reference model.':range?((range.allPositive?'All available Z values are positive. ':range.allNegative?'All available Z values are negative. ':'Available Z values include zero or both signs. ')+
            (options.zeroCentred?'Zero-centred symmetric scale.':'Local signed-Z range; '+(range.min>0||range.max<0?'zero is outside this range.':'zero is included.'))):'No finite Z statistics are available. Expand a record to inspect its stored values.';
        container.appendChild(notice);
        var head=document.createElement('div');head.className='paired-axis';container.appendChild(head);
        var mobile=container.clientWidth<700;
        var width=Math.max(190,Math.floor(mobile?container.clientWidth:container.clientWidth*0.62));
        if(range&&!options.singleModel){var ax=svg(width,65,'Common signed-Z axis');axis(ax,range,width,15);head.appendChild(ax);}
        rows.forEach(function (row,index) {
            var details=document.createElement('details');details.className='paired-record';details.dataset.record=String(index+1);
            if (rows.length===1) details.open=true;
            var display=options.label?options.label(row):{primary:row.celltype,secondary:row.collectionid};
            var summary=document.createElement('summary');summary.setAttribute('aria-label','Record '+(index+1)+': '+display.primary+'. Inspect both methods and source.');
            var label=document.createElement('span');label.className='paired-model';
            var name=document.createElement('strong');name.textContent=display.primary;label.appendChild(name);
            var sub=document.createElement('small');sub.textContent='Record '+(index+1)+' · '+display.secondary+' · '+row.n_snps+' SNPs';label.appendChild(sub);
            summary.appendChild(label);
            if(options.singleModel){
                var note=document.createElement('span');note.className='single-model-note';note.textContent='FUSION and S-PrediXcan statistics';summary.appendChild(note);
            }else if(range){
                var line=svg(width,45,row.celltype+': FUSION and S-PrediXcan Z statistics');
                pairedRow(line,row,range,width,22,index+1,options.threshold);summary.appendChild(line);
            }else{
                var missing=document.createElement('span');missing.textContent='FUSION Z unavailable · S-PrediXcan Z unavailable';summary.appendChild(missing);
            }
            details.appendChild(summary);
            var body=document.createElement('div');body.className='paired-record-body';
            options.describe(body,row,index);details.appendChild(body);container.appendChild(details);
        });
        container.dataset.rangeMin=range?String(range.min):'';container.dataset.rangeMax=range?String(range.max):'';container.dataset.scale=range?range.mode:'unavailable';
        return range;
    }
    function pairedExport(rows, options) {
        var width=1000,range=signedRange(rows,options.zeroCentred);
        if(options.singleModel&&rows.length===1){
            var row=rows[0],single=svg(width,260,options.title+' · single-model method statistics');
            text(single,18,28,options.title,{'font-size':18,fill:'#243640'});
            text(single,18,53,options.label?options.label(row).primary:row.celltype);
            text(single,18,75,row.celltype+' · '+row.collectionid+' · '+row.n_snps+' SNPs',{'font-size':11});
            methods.forEach(function (method,index) {
                var x=18+index*480,state=evidence.pState(row[method.p],options.threshold);
                text(single,x,115,method.label,{'font-size':16,fill:method.color});
                text(single,x,143,'Z '+evidence.valueText(row[method.z]));
                text(single,x,169,'Nominal P '+evidence.valueText(row[method.p]));
                text(single,x,195,state.passes?'Meets nominal P filter':state.state==='finite'?'Above nominal P filter':'P unavailable or invalid');
            });
            text(single,18,235,'Selected nominal P threshold: '+options.threshold+' · stored precision.');
            return single;
        }
        if (!range) return null;
        var names=rows.map(function (row) {return String(row.celltype).match(/.{1,55}/g)||[''];});
        var heights=names.map(function (lines) {return Math.max(63,lines.length*14+32);});
        var totalHeight=heights.reduce(function (a,b) {return a+b;},0);
        var chart=svg(width,totalHeight+220,options.title+' · all matching records for selected gene');
        text(chart,18,27,options.title,{'font-size':18,fill:'#243640'});
        text(chart,18,49,(range.allPositive?'All Z positive. ':range.allNegative?'All Z negative. ':'Signed Z values. ')+
            (options.zeroCentred?'Zero-centred symmetric scale.':'Local signed-Z range.')+' '+rows.length+' records.');
        legend(chart,options.threshold,75);
        var y=128;
        rows.forEach(function (row,index) {
            names[index].forEach(function (line,lineIndex) {text(chart,18,y+lineIndex*14,line,{'font-size':12,fill:'#243640'});});
            text(chart,18,y+names[index].length*14+3,'Record '+(index+1)+' · '+row.collectionid+' · '+row.n_snps+' SNPs',{'font-size':11});
            var group=el('g',{transform:'translate(420,0)'},undefined,chart);
            pairedRow(group,row,range,560,y,index+1,options.threshold);
            y+=heights[index];
        });
        var group=el('g',{transform:'translate(420,0)'},undefined,chart);
        axis(group,range,560,124+totalHeight);
        return chart;
    }
    function regionalLayout(records, method, threshold) {
        var all=records.filter(function (row) {
            return evidence.finite(row.GeneStart)!==null&&evidence.finite(row.GeneEnd)!==null&&
                evidence.finite(row.Zscore)!==null&&evidence.pState(row.PVALUE,threshold).state!=='invalid'&&evidence.finite(row.PVALUE)!==null;
        });
        if (!all.length) return null;
        var positions=all.map(function (row) {return (Number(row.GeneStart)/2+Number(row.GeneEnd)/2)/1e6;});
        var min=Math.min.apply(null,positions),max=Math.max.apply(null,positions),pad=Math.max((max-min)*0.04,0.05);
        var finiteYs=all.filter(function (row) {return Number(row.PVALUE)>0;}).map(function (row) {return -Math.log10(Number(row.PVALUE));});
        var thresholdY=-Math.log10(Number(threshold));
        // The task, not the chosen threshold or method, determines both axes.
        var yMax=Math.max.apply(null,[1].concat(finiteYs))+0.6;
        var yStep=stepFor(yMax,5);yMax=Math.ceil(yMax/yStep)*yStep;
        var selected=all.filter(function (row) {return row.Method===method;});
        return {min:min-pad,max:max+pad,yMax:yMax,yStep:yStep,thresholdY:thresholdY,valid:selected.length,
            hits:selected.filter(function (row) {return Number(row.PVALUE)<=threshold;}).length,
            points:selected.map(function (row) {return {row:row,x:(Number(row.GeneStart)/2+Number(row.GeneEnd)/2)/1e6,
                y:Number(row.PVALUE)===0?yMax:-Math.log10(Number(row.PVALUE)),zero:Number(row.PVALUE)===0,hit:Number(row.PVALUE)<=threshold};})};
    }
    function regionSvg(records, methodName, options, width, onSelect) {
        var layout=regionalLayout(records,methodName,options.threshold);
        if (!layout) return null;
        var mobile=width<500,height=mobile?360:390,left=53,right=18,top=75,bottom=height-53;
        var chart=svg(width,height,'Regional association plot, '+options.chrom+' '+options.build+', '+methodName);
        var method=methods.filter(function (m) {return m.name===methodName;})[0]||{name:methodName,label:methodName,color:'#0f766e'};
        var x=function (v) {return left+(v-layout.min)/(layout.max-layout.min)*(width-left-right);};
        var y=function (v) {return bottom-v/layout.yMax*(bottom-top);};
        text(chart,15,23,method.label+' · '+layout.valid+' valid genes · '+layout.hits+' hits',{'font-size':14,fill:'#243640'});
        text(chart,15,44,'Filled: nominal P ≤ '+options.threshold+' · grey open: background',{'font-size':mobile?9:12});
        var modelLines=('Model: '+(options.model||'Not recorded')).match(new RegExp('.{1,'+Math.max(26,Math.floor((width-30)/5.5))+'}','g'));
        modelLines.forEach(function (line,i) {text(chart,15,63+i*12,line,{'font-size':10});});
        var hasZero=layout.points.some(function (p) {return p.zero;});
        top=70+modelLines.length*12+(hasZero?16:0);
        var step=stepFor(layout.yMax,5);
        for(var v=0;v<=layout.yMax+step*0.01;v+=step) {
            el('line',{x1:left,x2:width-right,y1:y(v),y2:y(v),stroke:'#edf1f3'},undefined,chart);
            text(chart,left-8,y(v)+4,tickText(v,step),{'text-anchor':'end'});
        }
        var xStep=stepFor(layout.max-layout.min,mobile?3:7),start=Math.ceil(layout.min/xStep)*xStep;
        for(var tick=start;tick<=layout.max;tick+=xStep) {
            text(chart,x(tick),bottom+21,tickText(tick,xStep),{'text-anchor':'middle'});
        }
        el('line',{x1:left,x2:width-right,y1:bottom,y2:bottom,stroke:'#9eafb7'},undefined,chart);
        text(chart,(left+width-right)/2,height-7,options.chrom+' interval midpoint (Mb) · '+options.build,{'text-anchor':'middle','font-size':mobile?10:12});
        text(chart,14,(top+bottom)/2,'−log10(nominal P)',{transform:'rotate(-90 14 '+((top+bottom)/2)+')','text-anchor':'middle','font-size':11});
        if(layout.thresholdY<=layout.yMax){
            el('line',{x1:left,x2:width-right,y1:y(layout.thresholdY),y2:y(layout.thresholdY),stroke:'#9a6671','stroke-dasharray':'5 4','data-threshold':options.threshold},undefined,chart);
            text(chart,width-right,y(layout.thresholdY)-6,'P = '+options.threshold,{'text-anchor':'end','font-size':10,fill:'#89535f'});
        }else{
            text(chart,width-right,top-5,'↑ P = '+options.threshold+' above plot',{'text-anchor':'end','font-size':10,fill:'#89535f','data-threshold':options.threshold,'data-threshold-offscale':'above'});
        }
        layout.points.slice().sort(function (a,b) {return Number(a.hit)-Number(b.hit);}).forEach(function (point) {
            var attrs={fill:point.hit?method.color:'white',stroke:point.hit?method.color:'#94a3ad','stroke-width':1.5,
                'data-gene':point.row.TargetID,'data-p':point.row.PVALUE,'data-z':point.row.Zscore,'data-hit':String(point.hit),'data-zero':String(point.zero)};
            var px=x(point.x),py=y(point.y),node;
            if (point.zero) node=el('path',Object.assign(attrs,{d:'M '+px+' '+(py-1)+' L '+(px-5)+' '+(py+8)+' L '+(px+5)+' '+(py+8)+' Z'}),undefined,chart);
            else node=el('circle',Object.assign(attrs,{cx:px,cy:py,r:point.hit?4.8:3.5}),undefined,chart);
            el('title',{},(point.row.GeneName||point.row.TargetID)+' · '+point.row.TargetID+' · '+options.chrom+':'+point.row.GeneStart+'–'+point.row.GeneEnd+' · Z '+point.row.Zscore+' · nominal P '+point.row.PVALUE+(point.zero?' (stored zero; upper-edge marker)':''),node);
            if (onSelect) {
                node.setAttribute('role','button');node.setAttribute('tabindex','0');node.setAttribute('aria-label',(point.row.GeneName||point.row.TargetID)+', nominal P '+point.row.PVALUE+', inspect record');
                node.addEventListener('click',function () {onSelect(point.row,point.zero);});
                node.addEventListener('keydown',function (event) {if(event.key==='Enter'||event.key===' '){event.preventDefault();onSelect(point.row,point.zero);}});
            }
        });
        var labels=layout.points.slice().sort(function (a,b) {return Number(a.row.PVALUE)-Number(b.row.PVALUE);}).slice(0,1);
        var used=[];
        labels.forEach(function (point) {
            var px=x(point.x),py=y(point.y)-10;
            while(used.some(function (p) {return Math.abs(p.x-px)<75&&Math.abs(p.y-py)<14;})) py+=15;
            py=Math.max(top+12,Math.min(bottom-8,py));used.push({x:px,y:py});
            text(chart,Math.max(left+5,Math.min(width-right-5,px)),py,point.row.GeneName||point.row.TargetID,{'text-anchor':px>width*0.75?'end':px<width*0.25?'start':'middle','font-size':11,fill:'#243640'});
        });
        if (hasZero) text(chart,left,top-5,'▲ Stored P = 0: upper-edge marker.',{'font-size':10});
        return chart;
    }
    function saveSvg(chart, filename) {
        if (!chart) return;
        var clone=chart.cloneNode(true);clone.setAttribute('width',chart.viewBox.baseVal.width);clone.setAttribute('xmlns',ns);
        var blob=new Blob([new XMLSerializer().serializeToString(clone)],{type:'image/svg+xml;charset=utf-8'});
        var url=URL.createObjectURL(blob),link=document.createElement('a');link.href=url;link.download=filename;
        document.body.appendChild(link);link.click();link.remove();setTimeout(function () {URL.revokeObjectURL(url);},1000);
    }
    return {signedRange:signedRange,xValue:xValue,regionalLayout:regionalLayout,drawPaired:drawPaired,pairedExport:pairedExport,regionSvg:regionSvg,saveSvg:saveSvg};
});

/* Paged, read-only evidence presentation. No statistic is recalculated here. */
(function (root,factory) {
    var api=factory();
    if (typeof module==='object'&&module.exports) module.exports=api;
    if (root) root.ScEvidence=api;
})(typeof window==='undefined'?null:window,function () {
    'use strict';
    function finite(value) {
        if (typeof value==='number') return Number.isFinite(value)?value:null;
        if (typeof value!=='string'||!/^[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[-+]?\d+)?$/i.test(value.trim())) return null;
        var number=Number(value);return Number.isFinite(number)?number:null;
    }
    function valueText(value) { return finite(value)===null?'Unavailable':String(value); }
    function pState(value,threshold) {
        var p=finite(value),limit=finite(threshold);
        if (p===null) return {state:'unavailable',passes:false};
        if (p<0||p>1) return {state:'invalid',passes:false};
        return {state:p===0?'stored_zero':'finite',passes:limit!==null&&p<=limit};
    }
    function matchingMethods(row,threshold) {
        return [{name:'FUSION',field:'fusion_pval'},{name:'SPrediXcan',field:'spred_pval'}].map(function (method) {
            return {name:method.name,result:pState(row[method.field],threshold)};
        });
    }
    function plotLayout(rows,width) {
        var label=width<500?105:255,space=Math.max(80,width-label-35),zero=label+space/2;
        var maximum=1,points=[];
        rows.forEach(function (row,index) {
            [{name:'FUSION',field:'fusion_z',p:'fusion_pval',dy:-4},{name:'SPrediXcan',field:'spred_z',p:'spred_pval',dy:4},
             {name:row._method_label||'Unspecified method',field:'_unassigned_z',p:'_unassigned_p',dy:0}].forEach(function (method) {
                var z=finite(row[method.field]);
                if (z===null) return;
                maximum=Math.max(maximum,Math.abs(z));
                points.push({row:index,method:method.name,z:z,p:row[method.p],dy:method.dy});
            });
        });
        points.forEach(function (point) {point.x=zero+(point.z/maximum)*(space/2-8);point.y=25+point.row*35+point.dy;});
        return {width:width,height:Math.max(100,rows.length*35+65),labelWidth:label,plotWidth:space,zero:zero,limit:maximum,points:points};
    }
    function modelKey(collection,id) {return JSON.stringify([String(collection||''),String(id||'')]);}
    function metadataIndex(rows) {
        var result={};
        rows.forEach(function (row) {
            var key=modelKey(row.collectionid,row.celltypeid);
            if (!result[key]) result[key]=[];
            result[key].push(row);
        });
        return result;
    }
    function drawPlot(node,rows,description) {
        node.textContent='';
        var width=Math.max(180,Math.floor(node.clientWidth)),layout=plotLayout(rows,width);
        if (!layout.points.length) {node.textContent='No Z statistics are available for these records.';return;}
        var ns='http://www.w3.org/2000/svg',svg=document.createElementNS(ns,'svg');
        function element(tag,attributes,text,parent) {
            var item=document.createElementNS(ns,tag);
            Object.keys(attributes).forEach(function (key) {item.setAttribute(key,attributes[key]);});
            if (text!==undefined) item.textContent=text;
            (parent||svg).appendChild(item);return item;
        }
        svg.setAttribute('viewBox','0 0 '+layout.width+' '+layout.height);
        svg.setAttribute('width','100%');svg.setAttribute('height',layout.height);
        svg.setAttribute('role','img');svg.setAttribute('aria-label',description || 'TWAS Z statistics for '+rows.length+' selected-gene '+(rows.length===1?'record':'records')+' on the current page. The following table lists Z statistics, nominal P values and reference models.');
        element('line',{x1:layout.zero,x2:layout.zero,y1:8,y2:layout.height-45,stroke:'#bac8cc','stroke-width':1});
        [-layout.limit,0,layout.limit].forEach(function (value) {
            var label=Math.abs(value)>=10000?value.toExponential(1):Number(value.toPrecision(3)).toString();
            element('text',{x:layout.zero+(value/layout.limit)*(layout.plotWidth/2-8),y:layout.height-27,'text-anchor':'middle',fill:'#52616b','font-size':12},label);
        });
        element('text',{x:layout.zero,y:layout.height-6,'text-anchor':'middle',fill:'#52616b','font-size':12},'TWAS Z statistic');
        rows.forEach(function (row,index) {
            var characters=Math.max(10,Math.floor((layout.labelWidth-15)/6.6));
            var full=String(row._record_index)+'. '+(row._plot_label||row.celltype),label=full.length>characters?full.slice(0,characters-1)+'…':full;
            var name=element('text',{x:0,y:29+index*35,fill:'#243640','font-size':12},label);
            element('title',{},full,name);
        });
        layout.points.forEach(function (point) {
            var row=rows[point.row],color=point.method==='FUSION'?'#0f766e':point.method==='SPrediXcan'?'#785d96':'#52616b';
            var attributes={fill:color,'data-method':point.method,'data-z':String(point.z),'data-record-index':String(row._record_index)};
            var marker;
            if (point.method==='FUSION') {
                attributes.cx=point.x;attributes.cy=point.y;attributes.r=4;marker=element('circle',attributes);
            } else if (point.method==='SPrediXcan') {
                attributes.d='M '+point.x+' '+(point.y-5)+' L '+(point.x+5)+' '+point.y+' L '+point.x+' '+(point.y+5)+' L '+(point.x-5)+' '+point.y+' Z';marker=element('path',attributes);
            } else {
                attributes.cx=point.x;attributes.cy=point.y;attributes.r=4;attributes.fill='white';attributes.stroke=color;
                marker=element('circle',attributes);
            }
            var identity=[row.ensemblid,row.celltype,row.collectionid].filter(Boolean).join(' · ');
            element('title',{},identity+' · '+point.method+' Z '+String(point.z)+' · nominal P '+valueText(point.p),marker);
        });
        node.appendChild(svg);
    }
    function Preview(node) {
        this.node=node;this.$node=$(node);this.scope=0;this.page=0;this.requests=[];this.trigger=null;this.rows=[];this.metadata={};
        var self=this;
        this.$node.find('#evidence-close').on('click',function () {
            var trigger=self.trigger;self.reset();if(trigger&&trigger.isConnected)trigger.focus();else $('#search-submit').trigger('focus');
        });
        this.$node.find('#evidence-gene').on('change',function () {self.gene=this.value;self.render();});
        this.$node.find('#evidence-order,#evidence-page-size').on('change',function () {self.loadPage(0);});
        this.$node.find('#evidence-prev').on('click',function () {self.loadPage(Math.max(0,self.start-self.length));});
        this.$node.find('#evidence-next').on('click',function () {self.loadPage(self.start+self.length);});
        this.$node.find('#evidence-retry').on('click',function () {self.loadPage(self.start);});
        this.$node.find('#evidence-models-retry').on('click',function () {self.loadModels();});
        var timer;
        window.addEventListener('resize',function () {clearTimeout(timer);timer=setTimeout(function () {if(!self.node.hidden&&self.gene)self.render();},140);});
    }
    Preview.prototype.reset=function () {
        this.scope++;this.page++;
        this.requests.forEach(function (request) {request.abort();});this.requests=[];
        if(this.trigger)this.trigger.setAttribute('aria-expanded','false');this.trigger=null;
        this.rows=[];this.metadata={};this.gene='';this.total=null;this.node.hidden=true;
        this.$node.find('#evidence-page-scope,#evidence-gene-scope,#evidence-model-status').text('');
        this.$node.find('#evidence-chart,#evidence-table tbody').empty();
        this.$node.find('#evidence-selected,#evidence-retry,#evidence-models-retry').prop('hidden',true);
    };
    Preview.prototype.status=function (text,state) {this.$node.find('#evidence-status').text(text).attr('data-state',state);};
    Preview.prototype.open=function (trait,query,href,trigger) {
        this.reset();this.trait=trait;this.query=query;this.trigger=trigger;this.params=$.extend({},query,{phecode:trait.phecode,gene:(trait.target_genes||[])[0]||''});
        trigger.setAttribute('aria-expanded','true');this.node.hidden=false;
        this.$node.find('#evidence-title').text(trait.description+' · '+trait.phecode);
        this.$node.find('#evidence-selection').text('Original query: '+query.data+' · '+query.celltype+' · TWAS nominal P ≤ '+query.thres_twas+' (either method).');
        this.$node.find('#evidence-details').attr('href',href);
        this.$node.find('#evidence-order').val('4:asc');this.$node.find('#evidence-page-size').val('25');
        this.loadModels();this.loadPage(0);this.node.scrollIntoView({block:'start',behavior:'auto'});
    };
    Preview.prototype.loadModels=function () {
        var self=this,scope=this.scope;
        this.$node.find('#evidence-model-status').text('Loading source metadata…');
        this.$node.find('#evidence-models-retry').prop('hidden',true);
        var request=$.ajax({url:'association_models',data:this.params,dataType:'json',timeout:60000}).done(function (result) {
            if(scope!==self.scope)return;
            if(!Array.isArray(result.data)){self.sourceFailed();return;}
            self.metadata=metadataIndex(result.data);
            self.$node.find('#evidence-model-status').text('Source studies and experimental contexts are listed with the reference models.');
            self.render();
        }).fail(function (xhr,reason) {if(scope===self.scope&&reason!=='abort')self.sourceFailed();});
        this.requests.push(request);
    };
    Preview.prototype.sourceFailed=function () {
        this.metadata={};this.$node.find('#evidence-model-status').text('Source metadata could not be loaded.');
        this.$node.find('#evidence-models-retry').prop('hidden',false);this.render();
    };
    Preview.prototype.loadPage=function (start) {
        var self=this,scope=this.scope,page=++this.page;
        if(this.dataRequest)this.dataRequest.abort();
        this.start=start;this.length=Number(this.$node.find('#evidence-page-size').val());
        var order=this.$node.find('#evidence-order').val().split(':');
        this.rows=[];this.total=null;this.$node.find('#evidence-page-scope').text('');this.$node.find('#evidence-selected,#evidence-retry').prop('hidden',true);
        this.$node.find('#evidence-gene,#evidence-prev,#evidence-next').prop('disabled',true);
        this.status('Loading association records…','loading');
        var request=$.ajax({url:'association_data',data:$.extend({},this.params,{kind:'twas',draw:page,start:start,length:this.length,
            'search[value]':'','search[regex]':'false','order[0][column]':order[0],'order[0][dir]':order[1]}),dataType:'json',timeout:60000})
        .done(function (result) {
            if(scope!==self.scope||page!==self.page)return;
            var valid=Array.isArray(result.data)&&Number.isInteger(result.recordsFiltered)&&result.recordsFiltered>=0&&result.data.length<=self.length;
            valid=valid&&result.data.every(function (row) {return String(row.phecode)===String(self.trait.phecode)&&typeof row.ensemblid==='string'&&typeof row.celltype==='string'&&typeof row.collectionid==='string';});
            if(!valid){self.failed();return;}
            self.rows=result.data.map(function (row,index) {return $.extend({},row,{_record_index:start+index+1});});
            self.total=result.recordsFiltered;
            var ids=Array.from(new Set(self.rows.map(function (row) {return row.ensemblid;}))).sort();
            if((self.query.key==='0'||self.query.key==='4')&&ids.length===1&&!self.gene)self.gene=ids[0];
            var select=self.$node.find('#evidence-gene').empty();select.append(new Option('Choose a gene on this page',''));
            ids.forEach(function (id) {select.append(new Option(id,id));});
            if(self.gene&&ids.indexOf(self.gene)===-1)select.append(new Option(self.gene+' (not on this page)',self.gene));
            select.val(self.gene||'').prop('disabled',!self.rows.length);
            self.$node.find('#evidence-prev').prop('disabled',start===0);
            self.$node.find('#evidence-next').prop('disabled',start+self.rows.length>=self.total);
            var orderLabel=self.$node.find('#evidence-order option:selected').text();
            self.$node.find('#evidence-page-scope').text('Records '+(self.rows.length?start+1:0)+'–'+(start+self.rows.length)+' of '+self.total+' · '+orderLabel);
            self.render();
        }).fail(function (xhr,reason) {if(scope===self.scope&&page===self.page&&reason!=='abort')self.failed();});
        this.dataRequest=request;this.requests.push(request);
    };
    Preview.prototype.failed=function () {
        this.rows=[];this.$node.find('#evidence-selected').prop('hidden',true);this.$node.find('#evidence-retry').prop('hidden',false);
        this.status('The association records could not be loaded. Retry this page.','error');
    };
    Preview.prototype.render=function () {
        if(this.node.hidden||!this.rows.length){
            if(!this.node.hidden&&this.total===0)this.status('No matching association records under this selection and its filters.','empty');
            return;
        }
        var selected=this.rows.filter(function (row) {return row.ensemblid===this.gene;},this);
        this.$node.find('#evidence-gene-scope').text((this.gene?this.gene+' · Page records '+selected.length+' of '+this.rows.length+'. ':'')+'Full details and downloads cover all records for the selected query and trait.');
        if(!this.gene){this.$node.find('#evidence-selected').prop('hidden',true);this.status('Select a gene from this record page.','choose-gene');return;}
        if(!selected.length){this.$node.find('#evidence-selected').prop('hidden',true);this.status('The selected gene has no records on this page. Change the page or choose another listed gene.','empty-page');return;}
        this.$node.find('#evidence-selected').prop('hidden',false);
        this.status('Showing '+selected.length+(selected.length===1?' record':' records')+' for the selected gene on this page.','ready');
        drawPlot(this.$node.find('#evidence-chart')[0],selected);
        var body=this.$node.find('#evidence-table tbody').empty(),self=this;
        selected.forEach(function (row) {
            var tr=$('<tr>').attr('data-record-index',row._record_index).attr('data-gene',row.ensemblid).attr('data-model',row.celltype).attr('data-collection',row.collectionid);
            $('<td>').text(row._record_index).appendTo(tr);
            var model=$('<td>').append($('<span class="model-value">').text(row.celltype));
            var sources=self.metadata[modelKey(row.collectionid,row.celltype)]||[],meta=sources.length===1?sources[0]:null;
            if(meta)model.append($('<span class="cell-note">').text(meta.subtype+' · '+meta.condition));
            model.appendTo(tr);
            ['fusion_z','fusion_pval','spred_z','spred_pval'].forEach(function (field) {
                var value=valueText(row[field]),p=/_pval$/.test(field)?pState(row[field],self.query.thres_twas):null;
                if(p&&p.state==='invalid')value+=' (invalid P)';
                if(p&&p.state==='stored_zero')value+=' (stored as zero)';
                $('<td class="stored-number">').attr('data-field',field).text(value).appendTo(tr);
            });
            var states=matchingMethods(row,self.query.thres_twas),passing=states.filter(function (m) {return m.result.passes;});
            var match=passing.length?passing.map(function (m) {return m.name;}).join(' + '):'No method meets the nominal P filter';
            $('<td>').attr('data-threshold-methods',passing.map(function (m) {return m.name;}).join(',')).text(match).appendTo(tr);
            var source=$('<td>'),details=$('<details>');$('<summary>').text('Model & source').appendTo(details);
            var dl=$('<dl>');
            function item(label,value) {$('<dt>').text(label).appendTo(dl);$('<dd>').text(value===null||value===undefined||value===''?'Not recorded':value).appendTo(dl);}
            item('Ensembl gene',row.ensemblid);item('Model ID',row.celltype);item('Collection',row.collectionid);item('SNP count',row.n_snps);
            if(meta){
                item('Cell subtype',meta.subtype);item('Condition',meta.condition);item('Source study ID',meta.studyid);item('Source title',meta.title);item('Expression assay',ScUI.studyDisplay(query_catalog.study_presentations,meta,'method'));
                if(meta.doi){
                    $('<dt>').text('Source link').appendTo(dl);
                    var doi=String(meta.doi),url=/^https?:\/\//i.test(doi)?doi:(/^10\.\d{4,9}\//.test(doi)?'https://doi.org/'+doi:null);
                    $('<dd>').html(url?ScUI.link(url,doi):ScUI.text(doi)).appendTo(dl);
                }
                if(meta.source_records>1)item('Source records','Showing one of '+meta.source_records+' records for this study ID.');
            }else item('Source metadata',sources.length>1?'Multiple records share this model identifier.':'Unavailable');
            details.append(dl);source.append(details).appendTo(tr);body.append(tr);
        });
    };
    return {finite:finite,valueText:valueText,pState:pState,matchingMethods:matchingMethods,plotLayout:plotLayout,drawPlot:drawPlot,metadataIndex:metadataIndex,modelKey:modelKey,
        createPreview:function (node) {return new Preview(node);}};
});

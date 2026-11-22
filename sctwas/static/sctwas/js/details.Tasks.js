/* Presentation of the gene–method records returned for this task. */
function taskNumber(exponential) {
    return function (value,type) {
        var number=ScEvidence.finite(value);
        if (number===null) return type==='display'?'Unavailable':null;
        return type==='display'?(exponential?number.toExponential(4):number.toFixed(3)):number;
    };
}

function initTable() {
    $('#table_twas').DataTable({
        scrollX:true,
        lengthMenu:[[10,25,50,-1],[10,25,50,'All']],
        language:{emptyTable:cache_query.state==='no_hits'?
            'No associations meet the selected nominal P threshold.':'No association records are available for this task.'},
        order:[[6,'asc']],
        data:data_twas,
        columns:[
            {data:'GeneName'},{data:'TargetID'},{data:'celltype'},{data:'n_snps'},{data:'Method'},
            {data:'Zscore',className:'text-nowrap',render:taskNumber(false)},
            {data:'PVALUE',className:'text-nowrap',render:taskNumber(true)},
            {data:'CHROM'},{data:'GeneStart'},{data:'GeneEnd'}
        ]
    });
    $('#table_celltype').DataTable({
        scrollX:true,
        lengthMenu:[[10,25,50,-1],[10,25,50,'All']],
        language:{emptyTable:'No reference model metadata are available for this task.'},
        order:[[0,'asc']],
        data:data_celltype,
        columns:[
            {data:'celltypeid'},{data:'subtype'},{data:'condition'},ScUI.studyColumn(payload.study_presentations,'method'),
            {data:'sample'},ScUI.studyColumn(payload.study_presentations,'samplesize'),
            {data:'journal',orderable:false,render:function (data,type,row) {
                return type==='display'?ScUI.link(row.doi,data):data;
            }}
        ]
    });
}

$(document).ready(function () {
    initTable();
    var chart=document.getElementById('main');
    if (!chart) return;
    var rows=payload.all_rows||[],methods=Array.from(new Set(rows.map(function (row) {return row.Method;}))),timer;
    var selector=$('#task-region-method');
    methods.forEach(function (method) {selector.append(new Option(method==='SPrediXcan'?'S-PrediXcan':method,method));});
    var build=cache_query.reference==='hg38'?'GRCh38 (hg38)':cache_query.reference==='hg19'?'GRCh37 (hg19)':cache_query.reference||'Genome build not recorded';
    var options={threshold:cache_query.thres_twas,chrom:cache_query.chrom,build:build,model:cache_query.celltype||'Not recorded'};
    var currentSvg=null;
    function inspect(row,zero) {
        var node=$('#task-point-detail').empty();
        $('<strong>').text((row.GeneName||row.TargetID)+' · '+row.TargetID).appendTo(node);
        var list=$('<dl class="record-source">').appendTo(node);
        function item(name,value) {$('<dt>').text(name).appendTo(list);$('<dd>').text(value).appendTo(list);}
        item('Method',row.Method==='SPrediXcan'?'S-PrediXcan':row.Method);
        item('Coordinates',cache_query.chrom+':'+row.GeneStart+'–'+row.GeneEnd+' · '+build);
        item('Interval midpoint (Mb)',String((Number(row.GeneStart)/2+Number(row.GeneEnd)/2)/1e6));
        item('TWAS Z',row.Zscore);item('Nominal P',row.PVALUE+(zero?' (stored zero; upper-edge marker)':''));item('SNP count',row.n_snps);
        $('<p>').text(Number(row.PVALUE)<=Number(options.threshold)?'Meets the selected nominal P filter.':'Background record above the selected threshold. The table filter is unchanged.').appendTo(node);
        if(Number(row.PVALUE)<=Number(options.threshold)) {
            $('<button type="button" class="btn btn-sm btn-outline-primary">').text('View table row').appendTo(node).on('click',function () {
                var table=$('#table_twas').DataTable();
                var index=table.rows().indexes().toArray().filter(function (i) {
                    var candidate=table.row(i).data();return candidate.TargetID===row.TargetID&&candidate.Method===row.Method;
                })[0];
                if(index===undefined)return;
                var ordered=table.rows({search:'applied',order:'applied'}).indexes().toArray();
                if(ordered.indexOf(index)===-1){table.search('').columns().search('').draw();ordered=table.rows({search:'applied',order:'applied'}).indexes().toArray();}
                var length=table.page.len();table.page(length<0?0:Math.floor(ordered.indexOf(index)/length)).draw('page');
                $('#table_twas tr').removeClass('selected-result-row');
                var target=table.row(index).node();target.classList.add('selected-result-row');target.setAttribute('tabindex','-1');
                target.scrollIntoView({block:'center'});target.focus({preventScroll:true});
            });
        }
    }
    function draw() {
        chart.textContent='';
        var method=selector.val(),layout=ScResults.regionalLayout(rows,method,options.threshold);
        if(!layout){chart.textContent='No valid association records are available for a regional plot.';return;}
        currentSvg=ScResults.regionSvg(rows,method,options,Math.max(230,Math.floor(chart.clientWidth)),inspect);
        chart.appendChild(currentSvg);
        $('#task-plot-scope').text(layout.valid+' valid genes · '+layout.hits+' hits for '+(method==='SPrediXcan'?'S-PrediXcan':method)+'. Axes are fixed across methods and thresholds for this saved task.');
    }
    selector.on('change',function () {$('#task-point-detail').text('Select a point to inspect its stored statistics and coordinates.');draw();});
    $('#task-region-svg').on('click',function () {ScResults.saveSvg(currentSvg,'task-regional-'+selector.val()+'.svg');});
    draw();
    window.addEventListener('resize',function () {clearTimeout(timer);timer=setTimeout(draw,150);});
});

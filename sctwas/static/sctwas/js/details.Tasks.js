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

function taskPlotRows(records) {
    var ranked=records.filter(function (row) {return ScEvidence.finite(row.Zscore)!==null;});
    ranked.sort(function (a,b) {
        var first=ScEvidence.finite(a.PVALUE), second=ScEvidence.finite(b.PVALUE);
        if (first===null) return second===null?0:1;
        if (second===null) return -1;
        return first-second;
    });
    return ranked.slice(0,10).map(function (row,index) {
        var method=row.Method==='single'||!row.Method?'Unspecified method':row.Method;
        var point={_record_index:index+1,ensemblid:row.TargetID,celltype:row.celltype,
            _plot_label:(row.GeneName||row.TargetID)+' · '+method};
        if (method==='FUSION') {
            point.fusion_z=row.Zscore;
            point.fusion_pval=row.PVALUE;
        } else if (method==='SPrediXcan') {
            point.spred_z=row.Zscore;
            point.spred_pval=row.PVALUE;
        } else {
            point._unassigned_z=row.Zscore;
            point._unassigned_p=row.PVALUE;
            point._method_label=method;
        }
        return point;
    });
}

$(document).ready(function () {
    initTable();
    var chart=document.getElementById('main');
    if (!chart) return;
    var rows=taskPlotRows(data_twas),timer;
    if (!rows.length) {
        chart.textContent='No Z statistics are available for this task at the selected threshold.';
        return;
    }
    var methods=ScEvidence.plotLayout(rows,320).points.map(function (point) {return point.method;});
    var legend=$('#task-plot-legend');
    Array.from(new Set(methods)).forEach(function (method) {
        var marker=method==='FUSION'?'method-fusion':method==='SPrediXcan'?'method-spred':'method-unspecified';
        $('<span>').append($('<i aria-hidden="true">').addClass(marker),document.createTextNode(method)).appendTo(legend);
    });
    $('#task-plot-scope').text(rows.length+' gene–method records ordered by nominal P value.');
    function draw() {ScEvidence.drawPlot(chart,rows,'TWAS Z statistics for the selected gene–method records.');}
    draw();
    window.addEventListener('resize',function () {clearTimeout(timer);timer=setTimeout(draw,150);});
});

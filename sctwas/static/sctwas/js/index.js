var oTable_traits = null;
var cache_query = {};
$(function () {
    var key='0', lastQuery=null, submitted=false, restoring=false, pendingView=null, generation=0;
    var status=$('#query-status'), searchForm=$('#form_search');
    var evidence=ScEvidence.createPreview(document.getElementById('evidence-preview'));
    var thresholds=['1e-5','1e-4','1e-3','0.05','1'];
    function select(id,values) { values.forEach(function (v) { $(id).append(new Option(v,v)); }); $(id).select2({width:'100%'}); }
    select('#select_celltype',['All Celltypes'].concat(query_catalog.celltypes));
    select('#select_icd10',['All Traits'].concat(query_catalog.categories));
    select('#select_thres',thresholds);select('#select_thres_twas',thresholds);
    function summary() {
        var text=$('#select_celltype').val()+' · '+$('#select_icd10').val()+' · TWAS P ≤ '+$('#select_thres_twas').val();
        if (key==='2') text+=' · eQTL P ≤ '+$('#select_thres').val();
        $('#filter-summary').text(text);
    }
    function changeKey(value) {
        key=value;
        $('.query-tabs button').each(function () { $(this).attr('aria-pressed',this.dataset.key===key?'true':'false'); });
        $('#select_thres').prop('disabled',key!=='2');$('#eqtl-filter-field').prop('hidden',key!=='2');
        $('#input_search').attr('placeholder',{'0':'Gene symbol or Ensembl ID, e.g. RGL4','1':'Trait description or category, e.g. sinusitis','2':'A dbSNP rsID, e.g. rs12740374','3':'Cell type or model ID, e.g. CD8'}[key]);
        summary();
    }
    $('#select_celltype,#select_icd10,#select_thres,#select_thres_twas').on('change',summary);
    function message(text,state) { status.text(text).attr('data-state',state||'idle'); }
    function busy(value) {
        searchForm.attr('aria-busy',value?'true':'false').find(':input').prop('disabled',value);
        if (!value) $('#select_thres').prop('disabled',key!=='2');
    }
    function count(value) { return Number.isInteger(value) && value>=0 ? String(value) : 'Not recorded'; }
    function examples(row,field,unit,countField) {
        var labels=Array.isArray(row[field])?row[field]:[], value=labels.join(', ');
        return '<span class="context-examples">'+ScUI.text(value||'Not recorded')+'</span><span class="cell-note">'+ScUI.text(count(row[countField])+' '+unit+(row[countField]===1?'':'s'))+(labels.length<row[countField]?' · '+labels.length+' labels shown':'')+'</span>';
    }
    function details(row) {
        return 'detail?'+$.param($.extend({},cache_query,{phecode:row.phecode,gene:(row.target_genes||[])[0]||''}));
    }
    oTable_traits=$('#table_traits').DataTable({scrollX:true,order:[[2,'asc']],data:[],pageLength:10,
        dom:'<"explore-table-controls"lf>rt<"row"<"col-sm-5"i><"col-sm-7"p>>',
        language:{search:'Filter these results:',lengthMenu:'Show _MENU_ traits',emptyTable:'Run a search to view matching traits.'},
        columns:[
            {data:'phecode'},{data:'icd10'},{data:'description'},
            {data:null,render:function (data,type,row) { return type==='display'?examples(row,'target_celltype','cell subtype','n_subtypes'):(row.target_celltype||[]).join(', '); }},
            {data:null,render:function (data,type,row) { return type==='display'?examples(row,'target_condition','condition','n_conditions'):(row.target_condition||[]).join(', '); }},
            {data:'n_genes',render:function (data,type,row) {
                if (type!=='display') return data;
                return '<strong class="count-value">'+ScUI.text(count(data))+'</strong><span class="cell-note">Ensembl IDs</span><span class="cell-note">'+ScUI.text((row.target_genes||[]).join(', '))+'</span>';
            }},
            {data:'n_celltypes',render:function (data,type) { return type==='display'?'<strong class="count-value">'+ScUI.text(count(data))+'</strong><span class="cell-note">model IDs</span>':data; }},
            {data:null,orderable:false,render:function (data,type,row) {
                if (type!=='display') return row.phecode;
                return '<div class="query-evidence-actions"><button type="button" class="btn btn-sm btn-outline-primary preview-association" aria-expanded="false" aria-controls="evidence-preview">Preview</button>'+ScUI.link(details(row),'Full details →')+'</div>';
            }}
        ]
    });
    function queryURL(params) {
        var url=new URL('query',document.baseURI);
        url.searchParams.set('q',params.data);url.searchParams.set('key',params.key==='4'?'0':params.key);
        ['celltype','icd10','thres','thres_twas'].forEach(function (name) {url.searchParams.set(name,params[name]);});
        return url.pathname+url.search;
    }
    function saveView() {
        if (!submitted||restoring||searchForm.attr('aria-busy')==='true') return;
        var info=oTable_traits.page.info();
        ScUI.queryView.save(queryURL(cache_query),{order:oTable_traits.order(),page:info.page,length:info.length,filter:oTable_traits.search()});
    }
    function restoreView() {
        if (!pendingView) return;
        var view=pendingView;pendingView=null;restoring=true;
        var order=Array.isArray(view.order)&&view.order.every(function (item) {
            return Array.isArray(item)&&Number.isInteger(item[0])&&item[0]>=0&&item[0]<7&&/^(asc|desc)$/.test(item[1]);
        })?view.order:null;
        if (order&&order.length) oTable_traits.order(order);
        if ([10,25,50,100].indexOf(view.length)!==-1) oTable_traits.page.len(view.length);
        if (typeof view.filter==='string'&&view.filter.length<=200) oTable_traits.search(view.filter);
        oTable_traits.draw(false);
        var pages=oTable_traits.page.info().pages;
        if (Number.isInteger(view.page)&&view.page>=0&&view.page<pages) oTable_traits.page(view.page).draw('page');
        restoring=false;
    }
    $('#table_traits').on('order.dt page.dt length.dt search.dt',saveView)
    .on('click','.preview-association',function () {
        var row=oTable_traits.row($(this).closest('tr')).data();
        if (!row||!submitted) return;
        saveView();evidence.open(row,$.extend({},cache_query),details(row),this);
    }).on('click','a',saveView);
    $('#evidence-details').on('click',saveView);
    window.addEventListener('pagehide',saveView);
    function failed(text) {
        $('#query-count').text(oTable_traits.rows().count()+' traits · incomplete');
        message(text+' Results shown so far are incomplete. Retry to continue from cached batches.','error');
        oTable_traits.settings()[0].oLanguage.sEmptyTable='The search did not complete. Retry using the form above.';oTable_traits.draw();
    }
    function query(restore) {
        var value=$('#input_search').val().trim(),valid=value.length>0&&value.length<=200;
        if (key==='0') {value=value.toUpperCase();valid=valid&&/^[A-Z0-9._-]+$/.test(value);}
        if (key==='2') {value=value.toLowerCase();valid=/^rs[0-9]+$/.test(value);}
        if (!valid) {message(key==='2'?'Enter one valid rsID, such as rs12740374.':'Enter a valid search value (up to 200 characters).','error');$('#input_search').focus();return;}
        if(lastQuery){lastQuery.abort();lastQuery=null;}
        if(!restore)pendingView=null;
        var params={data:value,key:key==='0'&&/^ENSG[0-9]{11}$/.test(value)?'4':key,celltype:$('#select_celltype').val(),icd10:$('#select_icd10').val(),thres:$('#select_thres').val(),thres_twas:$('#select_thres_twas').val()};
        var token=++generation;evidence.reset();
        $('#input_search').val(value);busy(true);submitted=true;message('Searching the association database…','loading');
        oTable_traits.settings()[0].oLanguage.sEmptyTable='Search in progress. Results are not complete.';
        oTable_traits.clear().draw();$('#query-count').text('Searching');
        $('#result-context').text('Results for '+value+' · '+params.celltype+' · nominal TWAS P ≤ '+params.thres_twas+' (either method).');
        cache_query=params;
        try {history.replaceState(history.state,'',queryURL(params));} catch(e) { /* The search remains available. */ }
        $('#cancel-search').prop('hidden',false);
        lastQuery=ScUI.searchTraits(params,function (result) {
            if (token!==generation) return;
            oTable_traits.settings()[0].oLanguage.sEmptyTable=result.complete?'No matching records under the submitted query and filters.':'Search is incomplete. No rows have been loaded yet.';
            oTable_traits.rows.add(result.data).draw(false).columns.adjust();
            var n=oTable_traits.rows().count();
            $('#query-count').text(n+' traits'+(result.complete?'':' · partial'));
            message(result.complete?(n?'Search complete. Counts are specific to each trait and the submitted filters.':'No matching records under this query and these filters. Check the identifier or broaden the filters.'):
                'Checked '+result.checked+' of '+result.candidates+' candidate traits. Results are still incomplete…',result.complete?'complete':'loading');
            if (result.complete) {
                oTable_traits.settings()[0].oLanguage.sEmptyTable='No matching records under the submitted query and filters.';
                oTable_traits.draw(false);
            }
        },function () {
            if (token!==generation) return;
            restoreView();busy(false);lastQuery=null;$('#cancel-search').prop('hidden',true);saveView();
        },function (text) {
            if (token!==generation) return;
            failed(text);busy(false);lastQuery=null;$('#cancel-search').prop('hidden',true);
        });
    }
    $('#cancel-search').on('click',function () {
        generation++;if(lastQuery)lastQuery.abort();lastQuery=null;busy(false);$(this).prop('hidden',true);failed('Search paused.');
    });
    searchForm.on('submit',function (event) {event.preventDefault();if(!lastQuery)query();});
    $('.query-tabs button').on('click',function () {changeKey(this.dataset.key);});
    $('[data-example]').on('click',function () {changeKey(this.dataset.exampleKey);$('#input_search').val(this.dataset.example);query();});
    changeKey('0');
    var url=new URL(location.href),value=url.searchParams.get('q');
    if (value) {
        var requested=url.searchParams.get('key');
        if (!/^[0-3]$/.test(requested||'')) requested=/^rs\d+$/i.test(value)?'2':(/^[A-Z0-9._-]+$/.test(value)?'0':'1');
        changeKey(requested);$('#input_search').val(value);
        ['celltype','icd10','thres','thres_twas'].forEach(function (name) {
            var id={celltype:'#select_celltype',icd10:'#select_icd10',thres:'#select_thres',thres_twas:'#select_thres_twas'}[name];
            var v=url.searchParams.get(name);
            if(v&&$(id+' option').toArray().some(function (option) {return option.value===v;}))$(id).val(v).trigger('change');
        });
        var saved=ScUI.queryView.read();if(saved&&saved.url===url.pathname+url.search)pendingView=saved.view;
        query(true);
    }
});

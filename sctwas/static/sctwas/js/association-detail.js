/* Database detail tables share the server's selection, ordering and export scope. */
window.ScAssociation = {
    number: function (exponential) {
        return function (value, type) {
            var number = ScEvidence.finite(value);
            if (number === null) return type === 'display' ? 'Unavailable' : null;
            return type === 'display' ? (exponential ? number.toExponential(4) : number.toFixed(3)) : number;
        };
    },
    fields: {
        twas: ['ensemblid','celltype','n_snps','fusion_z','fusion_pval','spred_z','spred_pval','collectionid','phecode'],
        eqtl: ['genename','celltype','beta','se','pvalue','collectionid','rsid']
    }
};
$(function () {
    var query = pageData.cache_query, tables = {};
    function requestParams(kind, state) {
        return $.extend({}, query, {kind:kind, draw:state.draw, start:state.start, length:state.length,
            'search[value]':state.search.value, 'search[regex]':'false',
            'order[0][column]':state.order[0].column, 'order[0][dir]':state.order[0].dir});
    }
    function table(kind) {
        var status = $('#status-'+kind), link = $('#export-'+kind), pending, exportRequest, exportParams;
        var exportTimer=null, exportGeneration=0;
        var api = $('#table_'+kind).DataTable({
            serverSide:true, processing:true, scrollX:true, pageLength:25,
            dom:'B<"row"<"col-sm-6"l><"col-sm-6"f>>rt<"row"<"col-sm-5"i><"col-sm-7"p>>',
            lengthMenu:[10,25,50,100], order:[[4,'asc']], searchDelay:450,
            language:{search:'Filter gene / model / collection:',processing:'Loading records…'},
            buttons:[{extend:'copy',text:'Copy current page',exportOptions:{orthogonal:'export',modifier:{page:'current'}}}],
            ajax:function (state, callback) {
                if (pending) pending.abort();
                var params = requestParams(kind, state);
                exportGeneration++;
                clearTimeout(exportTimer);exportTimer=null;
                if(exportRequest) exportRequest.abort();
                exportRequest=null;
                exportParams=null;link.removeAttr('data-ready').text('Download all filtered rows (TSV)');
                link.removeAttr('href').attr('aria-disabled','true');
                status.removeClass('notice error').text('Loading records…');
                pending = $.ajax({url:'association_data',data:params,dataType:'json',timeout:60000})
                    .done(function (result) {
                        callback(result);
                        exportParams=params;
                        link.attr('href','association_download?'+$.param(params)).removeAttr('aria-disabled');
                        var count=result.recordsFiltered;
                        status.text(count.toLocaleString()+(count===1?' matching record.':' matching records.')+' TSV download includes all matching rows; copy includes this page.');
                    }).fail(function (xhr, reason) {
                        if (reason === 'abort') return;
                        callback({draw:state.draw,data:[],recordsTotal:0,recordsFiltered:0});
                        status.addClass('notice error').text('Records could not be loaded. ').append(
                            $('<button type="button" class="btn btn-sm btn-outline-primary">Retry</button>').on('click',function () { api.ajax.reload(null,false); }));
                    });
            },
            columns:ScAssociation.fields[kind].map(function (field) {
                var column = {data:field};
                if (/pval|pvalue/.test(field)) column.render = ScAssociation.number(true);
                else if (/_z$|^beta$|^se$/.test(field)) column.render = ScAssociation.number(false);
                return column;
            })
        });
        link.on('click',function (event) {
            if ($(this).attr('data-ready')==='true') return;
            event.preventDefault();
            if (!exportParams || exportRequest || exportTimer) return;
            var generation=exportGeneration, deadline=Date.now()+15*60*1000, failures=0;
            link.attr('aria-disabled','true').text('Preparing complete TSV…');
            status.text('Preparing all matching rows. You can keep browsing while the file is built.');
            function retryMessage(message) {
                link.removeAttr('aria-disabled').text('Retry complete TSV download');
                status.text(message);
            }
            function schedule(url, data, delay) {
                if (Date.now()>deadline) {
                    retryMessage('Preparation is taking longer than expected. Retry to check the existing export.');
                    return;
                }
                exportTimer=setTimeout(function () {exportTimer=null;prepare(url,data);},delay);
            }
            function prepare(url, data) {
                exportRequest=$.ajax({url:url,data:data,dataType:'json',timeout:20000})
                .done(function (result) {
                    if(generation!==exportGeneration) return;
                    failures=0;
                    if(result.state==='queued' || result.state==='running') {
                        link.text(result.state==='queued'?'Export queued…':'Preparing complete TSV…');
                        status.text(result.worker_ready===false?'Preparation is temporarily paused and will resume when the service recovers.':
                            'Your export continues in the background. You can keep browsing; request the same export to return to it.');
                        schedule(result.status_url,{},Math.max(1000,(result.retry_after||2)*1000));
                        return;
                    }
                    var size=result.bytes<1024 ? result.bytes+' B' : result.bytes<1048576 ? (result.bytes/1024).toFixed(1)+' KiB' : (result.bytes/1048576).toFixed(2)+' MiB';
                    link.attr('href',result.download_url).attr('download','sctwas-'+kind+'-filtered.tsv').attr('data-ready','true').removeAttr('aria-disabled').text('Download ready · '+size);
                    status.text(result.rows.toLocaleString()+' rows · available until '+new Date(result.expires_at*1000).toLocaleString()+' · resumable download. ').append(
                        $('<a>').attr('href',result.download_url+'&metadata=1').attr('target','_blank').attr('rel','noopener').text('File details & SHA-256'));
                    // Use the ready link for a user-initiated download, including retry.
                    link[0].click();
                }).fail(function (xhr, reason) {
                    if(reason==='abort' || generation!==exportGeneration) return;
                    if([0,502,503,504].indexOf(xhr.status)!==-1 && (!xhr.responseJSON || xhr.responseJSON.state!=='failed') && ++failures<=3) {
                        status.text('Reconnecting to your export…');schedule(url,data,3000);return;
                    }
                    retryMessage(xhr.responseJSON && xhr.responseJSON.error || 'The export could not be prepared. Retry the download.');
                }).always(function () {if(generation===exportGeneration) exportRequest=null;});
            }
            prepare('association_export',exportParams);
        });
        tables[kind] = api;
    }
    table('twas');
    if (pageData.detail_kind === 'variant') table('eqtl');

    var models = $('#table_celltype').DataTable({data:[],scrollX:true,pageLength:10,order:[[0,'asc']],
        columns:[{data:'celltypeid'},{data:'subtype'},{data:'condition'},ScUI.studyColumn(pageData.study_presentations,'method'),
                 {data:'sample'},ScUI.studyColumn(pageData.study_presentations,'samplesize'),{data:'journal',render:function (value,type,row) {
                    if (type !== 'display') return value;
                    return ScUI.link(row.doi,value)+(row.source_records>1 ? ' <span class="muted">('+row.source_records+' source records)</span>' : '');
                 }}]});
    function loadModels() {
        $('#status-models').removeClass('notice error').text('Loading source metadata…');
        $.ajax({url:'association_models',data:query,dataType:'json',timeout:60000}).done(function (result) {
            models.clear().rows.add(result.data).draw();
            var count=result.data.length;
            $('#status-models').text(count+(count===1?' model':' models')+' in this selection.');
        }).fail(function () {
            $('#status-models').addClass('notice error').text('Source metadata could not be loaded. ').append(
                $('<button type="button" class="btn btn-sm btn-outline-primary">Retry</button>').on('click',loadModels));
        });
    }
    loadModels();

    var overview = document.getElementById('association-overview');
    if (overview) {
        var chartRows, request, resizeTimer;
        var chart = document.getElementById('main');
        function drawOverview() {
            ScEvidence.drawPlot(chart, chartRows, 'TWAS Z statistics for the selected gene and reference models.');
        }
        function loadOverview() {
            if (request || chartRows) return;
            $('#chart-status').text('Loading association statistics…');
            $('#retry-overview').prop('hidden',true);
            request = $.ajax({url:'association_data',data:$.extend({},query,{
                kind:'twas',start:0,length:10,'order[0][column]':4,'order[0][dir]':'asc'
            }),dataType:'json',timeout:60000}).done(function (result) {
                chartRows = result.data.map(function (row,index) {
                    return $.extend({},row,{_record_index:index+1});
                });
                $('#chart-status').text('Records '+chartRows.length+' of '+result.recordsFiltered+' · FUSION nominal P ascending');
                var body = $('#overview-values tbody');
                chartRows.forEach(function (row) {
                    var tr = $('<tr>').appendTo(body);
                    ['_record_index','ensemblid','celltype','collectionid'].forEach(function (key) {
                        $('<td>').text(row[key]).appendTo(tr);
                    });
                    ['fusion_z','fusion_pval','spred_z','spred_pval'].forEach(function (key) {
                        $('<td>').text(ScEvidence.valueText(row[key])).appendTo(tr);
                    });
                });
                $('#overview-values').prop('hidden',!chartRows.length);
                drawOverview();
            }).fail(function () {
                $('#chart-status').text('The Z statistic overview could not be loaded.');
                $('#retry-overview').prop('hidden',false);
            }).always(function () {request=null;});
        }
        overview.addEventListener('toggle',function () {
            if (!overview.open) return;
            if (chartRows) drawOverview(); else loadOverview();
        });
        $('#retry-overview').on('click',loadOverview);
        window.addEventListener('resize',function () {
            clearTimeout(resizeTimer);
            if (overview.open && chartRows) resizeTimer=setTimeout(drawOverview,150);
        });
    }

    $('#load-related').on('click',function () {
        var button = $(this).prop('disabled',true);
        $('#status-related').removeClass('notice error').text('Searching related traits…');
        var all=[];
        ScUI.searchTraits(query,function (result) {
            all=all.concat(result.data);
            $('#status-related').text('Checked '+result.checked+' of '+result.candidates+' candidate traits'+(result.complete?'.':' · search incomplete…'));
        },function () {
            var rows = all.filter(function (row) { return row.phecode !== pageData.data_trait.phecode; });
            $('#related-results').prop('hidden',false);
            $('#table_traits').DataTable({data:rows,scrollX:true,order:[[2,'asc']],columns:[
                {data:'phecode'},{data:'icd10'},{data:'description'},{data:'n_celltypes'},{data:'n_conditions'},{data:'n_genes'},
                {data:null,orderable:false,render:function (value,type,row) {
                    var params = $.extend({},query,{phecode:row.phecode,gene:row.target_genes[0] || ''});
                    return type === 'display' ? ScUI.link('detail?'+$.param(params),'View →') : row.phecode;
                }}]});
            $('#status-related').text(rows.length+' other traits match the original query. Gene counts use distinct Ensembl IDs.');
            button.hide();
        },function (message) {
            $('#status-related').addClass('notice error').text(message);
            button.prop('disabled',false).text('Retry related traits');
        });
    });
});

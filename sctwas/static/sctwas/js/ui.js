/* Shared presentation helpers. Table exports retain underlying numeric values. */
$.ajaxSetup({beforeSend:function (xhr, settings) {
    if (!/^(GET|HEAD|OPTIONS|TRACE)$/i.test(settings.type) && !settings.crossDomain) {
        xhr.setRequestHeader('X-CSRFToken', window.scCsrfToken || '');
    }
}});
window.ScUI = {
    text: function (value) { return $('<span>').text(value == null ? '' : value).html(); },
    link: function (url, label) {
        if (!url) return ScUI.text(label);
        try {
            var target = new URL(url, document.baseURI);
            if (!/^https?:$/.test(target.protocol)) return ScUI.text(label);
            return '<a href="'+ScUI.text(target.href)+'"'+(target.origin !== location.origin ? ' target="_blank" rel="noopener noreferrer"' : '')+'>'+ScUI.text(label)+'</a>';
        } catch (e) { return ScUI.text(label); }
    }
};
ScUI.studyDisplay = function (presentations,row,field) {
    var study=Object.prototype.hasOwnProperty.call(presentations,row.studyid)?presentations[row.studyid]:null;
    if (!study) return row[field];
    if (field==='method') return study.assay;
    if (field==='samplesize') {
        var label=study.catalogue_sample_label;
        return label?label+' · '+(row.samplesize==null?'Unavailable':row.samplesize)+'. '+study.cohort:study.cohort;
    }
    return row[field];
};
ScUI.studyColumn = function (presentations,field) {
    return {data:field,render:function (data,type,row) {
        if (type!=='display') return data;
        var text=ScUI.studyDisplay(presentations,row,field);
        return field==='samplesize'&&text!==data?'<span class="study-cohort">'+ScUI.text(text)+'</span>':ScUI.text(text);
    }};
};
/* Only public Explore presentation state is stored, never task or upload data.
 * Results are always queried again; this is not a cache of scientific records.
 */
ScUI.queryView = {
    storageKey: 'sctwas.explore.view.v1',
    safeURL: function (value) {
        try {
            var url = new URL(value, document.baseURI), query = new URL('query', document.baseURI);
            if (url.origin !== location.origin || url.pathname !== query.pathname ||
                !url.searchParams.get('q') || url.searchParams.get('q').length > 200) return null;
            return url;
        } catch (e) { return null; }
    },
    read: function () {
        try {
            var raw = sessionStorage.getItem(this.storageKey);
            if (!raw || raw.length > 16384) return null;
            var record = JSON.parse(raw);
            if (record.version !== 1 || !Number.isFinite(record.savedAt) ||
                Date.now()-record.savedAt > 86400000 || !this.safeURL(record.url)) return null;
            return record;
        } catch (e) { return null; }
    },
    save: function (url, view) {
        var safe = this.safeURL(url);
        if (!safe) return;
        var record = {version:1, savedAt:Date.now(), url:safe.pathname+safe.search, view:view};
        try { sessionStorage.setItem(this.storageKey, JSON.stringify(record)); } catch (e) { /* URL restoration still works. */ }
    }
};
$(function () {
if ($.fn.dataTable) {
$.extend(true, $.fn.dataTable.defaults, {
    language: {search:'Filter rows:',lengthMenu:'Show _MENU_ rows',info:'_START_–_END_ of _TOTAL_ records',infoEmpty:'0 records',zeroRecords:'No rows match this table filter.',emptyTable:'No records are available for this selection.'},
    columnDefs: [{targets:'_all',render:$.fn.dataTable.render.text()}]
});
$.fn.dataTable.ext.errMode = 'none';
}
});
$(document).on('error.dt', function (event, settings) {
    var table = $(settings.nTable), parent = table.closest('.card-body');
    if (!parent.find('.table-error').length) $('<p class="notice error table-error" role="alert">This table could not be loaded. Reload the page to retry.</p>').prependTo(parent);
});
$(function () {
    var page = document.body.dataset.page;
    $('[data-nav]').each(function () {
        if (this.dataset.nav === page) $(this).addClass('active').attr('aria-current','page');
    });
    $('[data-copy-link]').on('click', function () {
        var button = this;
        if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(location.href).then(function () { $(button).text('Link copied'); }, function () { $(button).text('Copy the address from your browser'); });
        else $(button).text('Copy the address from your browser');
    });
    document.querySelectorAll('.nav-group').forEach(function (group) {
        group.classList.toggle('is-current', group.dataset.navGroup.split(',').indexOf(page) !== -1);
        group.querySelectorAll('a').forEach(function (link) {
            if (new URL(link.href).pathname === location.pathname) link.setAttribute('aria-current','page');
        });
        group.addEventListener('toggle', function () {
            if (group.open) document.querySelectorAll('.nav-group').forEach(function (other) { if (other !== group) other.open=false; });
        });
    });
    document.addEventListener('click', function (event) {
        document.querySelectorAll('.nav-group[open]').forEach(function (group) { if (!group.contains(event.target)) group.open=false; });
    });
    document.addEventListener('keydown', function (event) {
        if (event.key !== 'Escape') return;
        document.querySelectorAll('.nav-group[open]').forEach(function (group) {
            var focusInside=group.contains(document.activeElement);group.open=false;
            if (focusInside) group.querySelector('summary').focus();
        });
    });
    var savedView=ScUI.queryView.read(), detailURL=new URL(location.href);
    if (savedView && detailURL.searchParams.has('data')) {
        var queryURL=ScUI.queryView.safeURL(savedView.url), detailKey=detailURL.searchParams.get('key');
        var same=queryURL.searchParams.get('q') === detailURL.searchParams.get('data') &&
            queryURL.searchParams.get('key') === (detailKey === '4' ? '0' : detailKey);
        ['celltype','icd10','thres','thres_twas'].forEach(function (name) {
            if (detailURL.searchParams.has(name) && queryURL.searchParams.get(name) !== detailURL.searchParams.get(name)) same=false;
        });
        if (same) $('[data-query-return]').attr('href', queryURL.pathname+queryURL.search);
    }
    function identifiers() {
        document.querySelectorAll('.model-identifier, .metadata-grid .mono').forEach(function (node) {
            if (node.dataset.copyEnhanced) return;
            var value=node.textContent.trim();if (!value) return;
            node.dataset.copyEnhanced='true';node.title=value;
            var button=document.createElement('button');button.type='button';button.className='copy-identifier';
            button.textContent='Copy';button.setAttribute('aria-label','Copy full identifier');
            button.addEventListener('click',function () {
                if (!navigator.clipboard || !window.isSecureContext) { button.textContent='Select to copy';return; }
                navigator.clipboard.writeText(value).then(function () {button.textContent='Copied';},function () {button.textContent='Select to copy';});
            });
            node.insertAdjacentElement('afterend',button);
        });
    }
    identifiers();
    function tablePresentation(event, settings) {
        var table = new $.fn.dataTable.Api(settings), changed=false;
        table.columns().every(function () {
            var field=this.dataSrc(), numeric=typeof field==='string' &&
                /^(n|n_case|n_control|n_snps|samplesize|modelsize|fusion_z|fusion_pval|spred_z|spred_pval|beta|se|pvalue|Zscore|PVALUE|N_SNP|n_snps_used|GeneStart|GeneEnd|Start|End)$/.test(field);
            var identifier=typeof field==='string' && /^(celltype|celltypeid|ensemblid|ensemblID|TargetID|genename|rsid)$/.test(field);
            if (numeric) {
                if (!$(this.header()).hasClass('sc-numeric') || $(this.nodes()).filter(':not(.sc-numeric)').length) changed=true;
                $(this.header()).addClass('sc-numeric');$(this.nodes()).addClass('sc-numeric');
            }
            if (identifier) {
                if ($(this.nodes()).filter(':not(.sc-identifier)').length) changed=true;
                $(this.nodes()).addClass('sc-identifier');
            }
        });
        if (changed && !settings._scStyleAdjust) {
            settings._scStyleAdjust=true;
            requestAnimationFrame(function () {
                settings._scStyleAdjust=false;
                if ($.fn.dataTable.isDataTable(settings.nTable)) table.columns.adjust();
            });
        }
    }
    $(document).on('init.dt draw.dt', tablePresentation);
    function resize() {
        if ($.fn.dataTable && $.fn.dataTable.tables) $($.fn.dataTable.tables(true)).DataTable().columns.adjust();
        document.querySelectorAll('#main, .science-chart').forEach(function (node) {
            var chart = window.echarts && echarts.getInstanceByDom(node);
            if (chart) chart.resize();
        });
    }
    var timer;
    window.addEventListener('resize', function () { clearTimeout(timer); timer=setTimeout(resize,160); });
    $(document).on('shown.bs.collapse', resize);
});

/* Every batch is bounded; only the explicit complete flag denotes a full search. */
ScUI.searchTraits = function (params, progress, complete, failed) {
    var pending, timer, stopped=false, start=0, retries=0;
    function next() {
        pending=$.ajax({url:'explore_data',data:$.extend({},params,{start:start}),dataType:'json',timeout:60000})
            .done(function (result) {
                if (stopped) return;
                if (!Array.isArray(result.data) || typeof result.complete!=='boolean' || (!result.complete && result.next_start<=start)) {
                    failed('The service returned an unreadable search batch.');return;
                }
                progress(result);
                retries=0;
                if (result.complete) complete();
                else {start=result.next_start;next();}
            }).fail(function (xhr, reason) {
                if (!stopped && reason!=='abort' && [0,502,503,504].indexOf(xhr.status)!==-1 && retries<2) {
                    retries++;timer=setTimeout(next,1200*retries);return;
                }
                if (!stopped && reason!=='abort') failed(xhr.responseJSON && xhr.responseJSON.error || 'The search could not be completed. Check your connection and retry.');
            });
    }
    next();
    return {abort:function () {stopped=true;clearTimeout(timer);if(pending) pending.abort();}};
};

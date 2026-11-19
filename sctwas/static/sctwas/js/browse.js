/* A shared catalogue dataset drives responsive rows, filters and the original exports. */
(function () {
    'use strict';
    const navigation = document.querySelector('.catalog-tabs');
    const tabs = Array.from(navigation.querySelectorAll('a'));
    let active;
    const initialize = new Map();

    function show(tab) {
        if (active === tab) return;
        const previous = active && document.getElementById(active.hash.slice(1));
        const restoreFocus = previous && previous.contains(document.activeElement);
        active = tab;
        tabs.forEach(link => {
            const current = link === tab;
            link.setAttribute('aria-selected', String(current));
            link.tabIndex = current ? 0 : -1;
            document.getElementById(link.hash.slice(1)).hidden = !current;
        });
        if (restoreFocus) tab.focus();
        const enhance = initialize.get(tab.hash);
        if (enhance) enhance();
    }

    function visitLocation() {
        const target = tabs.find(tab => tab.hash === location.hash);
        if (target || !location.hash || !active) show(target || tabs[0]);
    }

    function activate(tab) {
        if (tab === active) return;
        history.pushState(null, '', tab.hash);
        show(tab);
    }

    navigation.setAttribute('role', 'tablist');
    tabs.forEach((tab, index) => {
        const panel = document.getElementById(tab.hash.slice(1));
        tab.setAttribute('role', 'tab');
        tab.setAttribute('aria-controls', panel.id);
        panel.setAttribute('role', 'tabpanel');
        panel.setAttribute('aria-labelledby', tab.id);
        tab.addEventListener('click', event => {
            if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
            event.preventDefault();
            activate(tab);
        });
        tab.addEventListener('keydown', event => {
            const targets = {
                ArrowLeft: (index + tabs.length - 1) % tabs.length,
                ArrowRight: (index + 1) % tabs.length,
                Home: 0,
                End: tabs.length - 1
            };
            if (event.key === ' ') {
                event.preventDefault();
                activate(tab);
            } else if (Object.hasOwn(targets, event.key)) {
                event.preventDefault();
                tabs[targets[event.key]].focus();
            }
        });
    });
    visitLocation();
    navigation.parentElement.dataset.tabsReady = '';
    window.addEventListener('popstate', visitLocation);
    window.addEventListener('hashchange', visitLocation);

    if (!window.jQuery || !$.fn.dataTable || !$.fn.dataTable.ext.buttons?.csvHtml5 || !window.ScUI) return;
    const mobile = window.matchMedia('(max-width: 700px)');
    const presentations = catalog.study_presentations;
    const text = ScUI.text;
    const link = ScUI.link;

    function value(raw) {
        return raw == null || raw === '' ? 'Not recorded' : raw;
    }

    function number(raw) {
        const original = String(value(raw));
        return /^\d+$/.test(original) ? original.replace(/\B(?=(\d{3})+(?!\d))/g, ',') : original;
    }

    function secondary(raw) {
        return '<span class="catalog-secondary">' + text(raw) + '</span>';
    }

    function mobileLabel(label, html) {
        return '<span class="catalog-mobile-label" aria-hidden="true">' + text(label) + '</span>' + html;
    }

    function details(fields, links = []) {
        const items = fields.map(([label, raw]) => '<div><dt>' + text(label) + '</dt><dd>' + text(value(raw)) + '</dd></div>');
        return '<dl class="catalog-detail-fields">' + items.join('') + '</dl>' +
            (links.length ? '<p class="catalog-detail-links">' + links.join('') + '</p>' : '');
    }

    const modelURL = row => 'provenance?model=' + encodeURIComponent(row.evidence_id);
    const traitURL = row => 'detail?' + $.param({
        key: '1', phecode: row.phecode, data: row.description, celltype: 'All Celltypes',
        icd10: 'All Traits', thres: '1e-5', thres_twas: '1e-5'
    });
    const citation = row => [row.journal, row.year].filter(Boolean).join(' · ');
    const assay = row => ScUI.studyDisplay(presentations, row, 'method');

    function displayed(render, filter, orderData, className = '') {
        return {data: null, className, orderData, render(row, type) {
            return type === 'display' ? render(row) : filter(row);
        }};
    }

    const tables = {
        '#card_celltype': {
            records: catalog.data_celltype, category: 'majortype', categoryColumn: 4,
            exportFields: [['Major type','majortype'], ['Subtype','subtype'], ['Condition','condition'],
                ['Model ID','celltypeid'], ['Details','celltypeid']],
            initial: [4,'asc'],
            sorts: [[4,'asc','Major type ↑'], [4,'desc','Major type ↓'],
                [0,'asc','Cell population ↑'], [0,'desc','Cell population ↓'],
                [1,'asc','Condition ↑'], [1,'desc','Condition ↓'],
                [2,'asc','Source study ↑'], [2,'desc','Source study ↓']],
            subject: row => row.subtype, recordName: 'model',
            columns: [
                displayed(row => link(modelURL(row), row.subtype) + secondary(row.majortype),
                    row => row.subtype, [5], 'catalog-primary'),
                displayed(row => mobileLabel('Condition', text(value(row.condition))), row => row.condition, [6]),
                {
                    data: null,
                    render(row, type) {
                        if (type === 'display') return mobileLabel('Source study', link(row.doi, value(citation(row))));
                        if (type === 'filter') return [row.studyid, row.title, row.journal, row.year, row.doi,
                            row.evidence_id, assay(row)].filter(Boolean).join(' ');
                        return citation(row);
                    }
                }
            ],
            detail: row => details([['Registered model',row.celltypeid], ['Catalogue ID',row.evidence_id],
                ['Expression assay',assay(row)], ['Source study',row.title]], [link(modelURL(row),'View model'),
                link('twas?model='+encodeURIComponent(row.celltypeid),'Use model')])
        },
        '#card_trait': {
            records: catalog.data_trait, category: 'icd10', categoryColumn: 5,
            exportFields: [['Phecode','phecode'], ['Category','icd10'], ['Description','description'],
                ['Study sample size','n'], ['Cases','n_case'], ['Controls','n_control'], ['Details','phecode']],
            initial: [4,'asc'],
            sorts: [[4,'asc','PheCode ↑'], [4,'desc','PheCode ↓'],
                [1,'asc','Category ↑'], [1,'desc','Category ↓'],
                [2,'asc','GWAS N ↑'], [2,'desc','GWAS N ↓']],
            mobileSortAliases: {0:4},
            subject: row => row.description, recordName: 'trait',
            columns: [
                displayed(row => link(traitURL(row), row.description) + secondary('PheCode ' + row.phecode),
                    row => row.description, [4], 'catalog-primary'),
                displayed(row => mobileLabel('Category', text(value(row.icd10))), row => row.icd10, [5]),
                displayed(row => mobileLabel('GWAS sample size', text(number(row.n))), row => row.n, [7], 'catalog-number')
            ],
            detail: row => details([['Cases',number(row.n_case)], ['Controls',number(row.n_control)]],
                [link(traitURL(row),'View associations')])
        },
        '#card_study': {
            records: catalog.data_study,
            exportFields: [['Publication','journal'], ['Year','year'], ['Title','title'],
                ['Registered assay','method'], ['Tissue','sample'], ['Study sample size','samplesize'],
                ['Recorded models','modelsize']],
            initial: [5,'desc'],
            sorts: [[5,'desc','Year (newest)'], [5,'asc','Year (oldest)'],
                [0,'asc','Title (A–Z)'], [0,'desc','Title (Z–A)'],
                [1,'asc','Expression assay (A–Z)'], [1,'desc','Expression assay (Z–A)'],
                [2,'desc','Recorded models (most)'], [2,'asc','Recorded models (fewest)']],
            subject: row => row.title, recordName: 'source record',
            columns: [
                displayed(row => '<span class="catalog-name">' + text(row.title) + '</span>' + secondary(citation(row)),
                    row => row.title, [6], 'catalog-primary'),
                {
                    data: null,
                    render(row, type) {
                        if (type === 'display') return text(value(assay(row))) + secondary('Catalogue collection · ' + value(row.sample));
                        if (type === 'filter') return [assay(row), row.sample, row.authors, row.doi, row.studyid]
                            .filter(Boolean).join(' ');
                        return assay(row);
                    }
                },
                displayed(row => mobileLabel('Recorded models', text(number(row.modelsize))), row => row.modelsize, [10], 'catalog-number')
            ],
            detail: row => details([['Publication',citation(row)], ['Authors',row.authors],
                ['Study sample context',ScUI.studyDisplay(presentations,row,'samplesize')]],
                row.doi ? [link(row.doi,'View publication')] : [])
        }
    };

    function enhance(panel, spec) {
        const node = panel.querySelector('table');
        const header = node.tHead.rows[0];
        spec.exportFields.forEach(([title]) => {
            const th = document.createElement('th');
            th.scope = 'col';
            th.textContent = title;
            header.append(th);
        });
        node.tBodies[0].replaceChildren();

        const tools = panel.querySelector('.catalog-tools');
        const search = tools.querySelector('.catalog-search');
        const category = tools.querySelector('.catalog-category');
        const sort = tools.querySelector('.catalog-sort');

        // Visible cells may combine fields or format values. The hidden columns
        // retain the original order, labels and orthogonal export data.
        const exportOptions = {
            columns: spec.exportFields.map((entry, index) => index + 4),
            orthogonal: 'export',
            modifier: {search: 'applied', page: 'all', selected: null}
        };
        const table = $(node).DataTable({
            data: spec.records,
            pageLength: 10,
            order: [spec.initial],
            orderMulti: false,
            autoWidth: false,
            dom: '<"catalog-export"B><"catalog-results"t><"catalog-table-footer"ilp>',
            buttons: [
                {extend:'csv',text:'Export CSV',exportOptions},
                {extend:'copy',text:'Copy table',exportOptions}
            ],
            language: {info:'_TOTAL_ matching ' + spec.recordName + 's · showing _START_–_END_',
                infoEmpty:'0 matching ' + spec.recordName + 's', infoFiltered:'(of _MAX_)',
                zeroRecords:'No matches. Try another keyword or reset filters.'},
            infoCallback(_settings, _start, _end, _maximum, total, formatted) {
                return total === 1 ? formatted.replace('matching ' + spec.recordName + 's',
                    'matching ' + spec.recordName) : formatted;
            },
            columns: [
                ...spec.columns,
                {data: null, className:'catalog-control', searchable:false, orderable:false,
                    render: (row, type) => type === 'display' ?
                        '<button type="button" class="btn btn-light catalog-detail-toggle" aria-expanded="false" aria-label="Details for ' +
                        text(spec.subject(row)).replace(/"/g, '&quot;') + '">Details</button>' : ''},
                ...spec.exportFields.map(([,field]) => ({data:field,visible:false}))
            ],
            createdRow(row) {
                row.classList.add('catalog-record');
                row.setAttribute('role', 'row');
                Array.from(row.cells).forEach(cell => cell.setAttribute('role', 'cell'));
            }
        });

        function refreshSort() {
            const [col, direction] = table.order()[0];
            const choice = spec.mobileSortAliases?.[col] ?? col;
            sort.value = choice + ':' + direction;
        }

        spec.sorts.forEach(([col, dir, label]) => sort.add(new Option(label, col + ':' + dir)));
        refreshSort();
        table.on('order.dt', refreshSort);
        sort.addEventListener('change', () => {
            const [column, direction] = sort.value.split(':');
            table.order([[Number(column),direction]]).draw();
        });

        if (category) {
            Array.from(new Set(spec.records.map(row => row[spec.category]))).sort((a, b) => a.localeCompare(b))
                .forEach(label => category.add(new Option(label, label)));
            category.addEventListener('change', applyFilters);
        }
        function applyFilters() {
            table.search(search.value);
            if (category) {
                const exact = category.value && '^' + $.fn.dataTable.util.escapeRegex(category.value) + '$';
                table.column(spec.categoryColumn).search(exact, true, false, false);
            }
            table.draw();
        }
        search.addEventListener('input', applyFilters);
        tools.querySelector('.catalog-reset').addEventListener('click', () => {
            search.value = '';
            if (category) category.value = '';
            applyFilters();
        });

        $(node).on('click', '.catalog-detail-toggle', function () {
            const row = table.row(this.closest('tr'));
            if (row.child.isShown()) {
                row.child.remove();
                this.setAttribute('aria-expanded', 'false');
                this.removeAttribute('aria-controls');
                return;
            }
            const detail = document.createElement('div');
            detail.className = 'catalog-details';
            detail.id = node.id + '-detail-' + row.index();
            detail.setAttribute('role', 'region');
            detail.setAttribute('aria-label', 'Details for ' + spec.subject(row.data()));
            detail.innerHTML = spec.detail(row.data());
            row.child(detail, 'catalog-detail-row').show();
            const detailRow = row.child()[0];
            detailRow.setAttribute('role', 'row');
            detailRow.firstElementChild.setAttribute('role', 'cell');
            this.setAttribute('aria-controls', detail.id);
            this.setAttribute('aria-expanded', 'true');
        });
        function headingFocus() {
            node.tHead.querySelectorAll('th[tabindex]').forEach(th => th.tabIndex = mobile.matches ? -1 : 0);
        }
        headingFocus();
        mobile.addEventListener('change', headingFocus);
        panel.querySelector('.catalog-fallback').hidden = true;
        tools.hidden = false;
        panel.classList.add('catalog-enhanced');
    }

    $(function () {
        Object.entries(tables).forEach(([hash, spec]) => initialize.set(hash, () => {
            initialize.delete(hash);
            enhance(document.getElementById(hash.slice(1)), spec);
        }));
        initialize.get(active.hash)();
    });
}());

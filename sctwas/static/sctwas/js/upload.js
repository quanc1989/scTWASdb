/* Upload progress is transfer progress only; computation is reported on the task page. */
$(function () {
    var form = document.getElementById('form_upload');
    var kind = form.dataset.kind;
    var busy = false;
    var modelSelect = $('#select_celltype');
    var errorBox = $('#submission-error');
    function options(select, values) {
        select.empty();
        values.forEach(function (value) { select.append(new Option(value, value)); });
        select.trigger('change');
    }
    function unique(values) { return Array.from(new Set(values)).sort(); }
    function updateModels() {
        var matches = data_celltype.filter(function (row) { return row.majortype === $('#select_majortype').val() && row.condition === $('#select_condition').val(); });
        options(modelSelect, matches.map(function (row) { return row.celltypeid; }));
        form.querySelector('[type=submit]').disabled = matches.length === 0;
    }
    function updateConditions() {
        options($('#select_condition'), unique(data_celltype.filter(function (row) { return row.majortype === $('#select_majortype').val(); }).map(function (row) { return row.condition; })));
        updateModels();
    }
    $('#form_upload select').select2({width:'100%'});
    if (kind === 'twas') {
        options($('#select_majortype'), unique(data_celltype.map(function (row) { return row.majortype; })));
        updateConditions();
        $('#select_majortype').on('change', updateConditions);
        $('#select_condition').on('change', updateModels);
        var requested = new URL(location.href).searchParams.get('model');
        var selected = data_celltype.find(function (row) { return row.celltypeid === requested; });
        if (selected) {
            $('#select_majortype').val(selected.majortype).trigger('change');
            $('#select_condition').val(selected.condition).trigger('change');
            modelSelect.val(selected.celltypeid).trigger('change');
        }
        if (!data_celltype.length) errorBox.text('No expression models are available in this database. Please try again after the catalog is restored.').prop('hidden', false);
    }
    $('#file').on('change', function () {
        var file = this.files[0];
        this.setCustomValidity(file && file.size > 100 * 1024 * 1024 ? 'Choose a file no larger than 100 MiB.' : '');
        $('#label_file').text(file ? file.name + ' · ' + (file.size / 1024 / 1024).toFixed(2) + ' MiB' : 'No file selected');
        if (!this.checkValidity()) this.reportValidity();
    });
    $(form).on('submit', function (event) {
        event.preventDefault();
        if (busy || !form.reportValidity()) return;
        var payload = new FormData(form);
        if (kind === 'twas') {
            var model = data_celltype.find(function (row) { return row.celltypeid === modelSelect.val(); });
            if (!model) { errorBox.text('Choose an available expression model.').prop('hidden',false); return; }
            payload.set('majortype', model.collectionid);
        }
        busy = true;
        errorBox.prop('hidden',true);
        var controls = $(form).find(':input');
        controls.prop('disabled',true);
        $(form).attr('aria-busy','true');
        $('#upload-status').text('Uploading summary data…');
        function failed(message) {
            errorBox.text(message).prop('hidden',false);
            $('#upload-status').text('Submission did not complete. Your file and parameters are retained.');
            errorBox.attr('tabindex','-1').trigger('focus');
        }
        $.ajax({url:form.action, type:'POST', data:payload, processData:false, contentType:false, timeout:120000,
            xhr:function () {
                var xhr = $.ajaxSettings.xhr();
                xhr.upload.addEventListener('progress',function (event) {
                    if (event.lengthComputable) $('#upload-status').text(event.loaded === event.total ? 'Upload complete. Waiting for the task ID…' : 'Uploading: '+Math.round(event.loaded/event.total*100)+'%');
                });
                return xhr;
            },
            success:function (data) {
                if (data.result !== 'ok' || !/^[a-f0-9]{32}$/.test(data.tag || '')) { failed(data.error || 'The service did not return a valid task ID. Please retry.'); return; }
                var prefix = kind === 'twas' ? 'twas' : 'training';
                var target = kind === 'twas' ? 'detail?'+$.param({key:'5',data:data.tag,chrom:payload.get('chrom'),thres_twas:payload.get('thres')}) : 'training_result?'+$.param({task:data.tag});
                $('#'+prefix+'-task-link').attr('href',target).text('Open task '+data.tag);
                $('#'+prefix+'-task-notice').prop('hidden',false).attr('tabindex','-1').trigger('focus');
                $('#upload-status').text('Task created. Follow the task link for computation status.');
            },
            error:function (xhr) { failed(xhr.responseJSON && xhr.responseJSON.error || 'The service could not confirm submission. Check your connection before retrying; a task may already have been created.'); },
            complete:function () { busy=false; controls.prop('disabled',false); $(form).attr('aria-busy','false'); }
        });
    });
});

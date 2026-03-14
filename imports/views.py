from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from database.models import ImportBatch

from .forms import CsvImportUploadForm
from .services import build_preview, run_import

PREVIEW_SESSION_KEY = 'imports_preview'
IMPORT_TYPE_LABELS = dict(CsvImportUploadForm.IMPORT_TYPE_CHOICES)
PREVIEW_COLUMNS = {
    'organism': [
        ('row_number', 'Row'),
        ('ncbi_taxonomy_id', 'NCBI Taxonomy ID'),
        ('scientific_name', 'Scientific Name'),
        ('taxonomic_rank', 'Rank'),
        ('parent_ncbi_taxonomy_id', 'Parent Taxonomy ID'),
        ('genus', 'Genus'),
        ('species', 'Species'),
    ],
    'study': [
        ('row_number', 'Row'),
        ('source_doi', 'Source DOI'),
        ('title', 'Title'),
        ('country', 'Country'),
        ('journal', 'Journal'),
        ('publication_year', 'Publication Year'),
    ],
    'sample': [
        ('row_number', 'Row'),
        ('study_source_doi', 'Study DOI'),
        ('label', 'Label'),
        ('site', 'Site'),
        ('method', 'Method'),
        ('cohort', 'Cohort'),
        ('sample_size', 'Sample Size'),
    ],
    'core_metadata': [
        ('row_number', 'Row'),
        ('study_source_doi', 'Study DOI'),
        ('sample_label', 'Sample Label'),
        ('condition', 'Condition'),
        ('male_percent', 'Male %'),
        ('age_mean', 'Age Mean'),
        ('age_sd', 'Age SD'),
        ('bmi_mean', 'BMI Mean'),
        ('bmi_sd', 'BMI SD'),
    ],
    'metadata_variable': [
        ('row_number', 'Row'),
        ('name', 'Name'),
        ('display_name', 'Display Name'),
        ('domain', 'Domain'),
        ('value_type', 'Value Type'),
        ('default_unit', 'Default Unit'),
        ('is_filterable', 'Filterable'),
    ],
    'metadata_value': [
        ('row_number', 'Row'),
        ('study_source_doi', 'Study DOI'),
        ('sample_label', 'Sample Label'),
        ('variable_name', 'Variable'),
        ('value_float', 'Float'),
        ('value_int', 'Integer'),
        ('value_text', 'Text'),
        ('value_bool', 'Boolean'),
        ('unit', 'Unit'),
        ('raw_value', 'Raw Value'),
    ],
    'relative_association': [
        ('row_number', 'Row'),
        ('study_source_doi', 'Study DOI'),
        ('sample_label', 'Sample Label'),
        ('organism_1_taxonomy_id', 'Organism 1 Taxonomy ID'),
        ('organism_2_taxonomy_id', 'Organism 2 Taxonomy ID'),
        ('association_type', 'Association Type'),
        ('value', 'Value'),
        ('sign', 'Sign'),
        ('method', 'Method'),
        ('confidence', 'Confidence'),
    ],
    'alpha_metric': [
        ('row_number', 'Row'),
        ('study_source_doi', 'Study DOI'),
        ('sample_label', 'Sample Label'),
        ('metric_type', 'Metric Type'),
        ('value', 'Value'),
        ('unit', 'Unit'),
    ],
    'beta_metric': [
        ('row_number', 'Row'),
        ('study_source_doi', 'Study DOI'),
        ('sample_1_label', 'Sample 1 Label'),
        ('sample_2_label', 'Sample 2 Label'),
        ('metric_type', 'Metric Type'),
        ('value', 'Value'),
        ('unit', 'Unit'),
    ],
}


@staff_member_required
@require_http_methods(['GET', 'POST'])
def upload_csv(request):
    if request.method == 'POST':
        form = CsvImportUploadForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = form.cleaned_data['csv_file']
            preview = build_preview(
                file_name=csv_file.name,
                content=csv_file.read().decode('utf-8-sig'),
                import_type=form.cleaned_data['import_type'],
                batch_name=form.cleaned_data['name'],
            )
            request.session[PREVIEW_SESSION_KEY] = preview.to_dict()
            return redirect('imports:preview')
    else:
        form = CsvImportUploadForm()

    return render(
        request,
        'imports/upload.html',
        {
            'form': form,
            'import_choices': CsvImportUploadForm.IMPORT_TYPE_CHOICES,
        },
    )


@staff_member_required
def preview_csv(request):
    preview = request.session.get(PREVIEW_SESSION_KEY)
    if not preview:
        return redirect('imports:upload')

    import_type = preview['import_type']
    preview_columns = PREVIEW_COLUMNS.get(
        import_type,
        [(key, key.replace('_', ' ').title()) for key in preview['valid_rows'][0].keys()] if preview['valid_rows'] else [],
    )
    return render(
        request,
        'imports/preview.html',
        {
            'preview': preview,
            'import_label': IMPORT_TYPE_LABELS.get(import_type, import_type.replace('_', ' ').title()),
            'preview_columns': preview_columns,
        },
    )


@staff_member_required
@require_http_methods(['POST'])
def confirm_csv(request):
    preview = request.session.get(PREVIEW_SESSION_KEY)
    if not preview:
        return redirect('imports:upload')

    batch = run_import(preview)
    request.session.pop(PREVIEW_SESSION_KEY, None)
    return redirect('imports:result', batch_id=batch.pk)


@staff_member_required
def import_result(request, batch_id):
    batch = get_object_or_404(ImportBatch, pk=batch_id)
    import_key = batch.import_type.removesuffix('_csv')
    return render(
        request,
        'imports/result.html',
        {
            'batch': batch,
            'import_label': IMPORT_TYPE_LABELS.get(import_key, import_key.replace('_', ' ').title()),
        },
    )

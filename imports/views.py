from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from database.models import ImportBatch

from .forms import CsvImportUploadForm
from .services import build_preview, run_import

PREVIEW_SESSION_KEY = 'imports_preview'
IMPORT_TYPE_LABELS = {
    **dict(CsvImportUploadForm.IMPORT_TYPE_CHOICES),
    CsvImportUploadForm.SOURCE_FORMAT_WORKBOOK: 'Excel Workbook',
}
PREVIEW_COLUMNS = {
    'taxon': [
        ('row_number', 'Row'),
        ('ncbi_taxonomy_id', 'NCBI Taxonomy ID'),
        ('scientific_name', 'Scientific Name'),
        ('rank', 'Rank'),
        ('resolution_status', 'Resolution Status'),
        ('review_required', 'Review Required'),
        ('lineage_summary', 'Lineage'),
    ],
    'study': [
        ('row_number', 'Row'),
        ('doi', 'DOI'),
        ('title', 'Title'),
        ('country', 'Country'),
        ('journal', 'Journal'),
        ('year', 'Year'),
    ],
    'group': [
        ('row_number', 'Row'),
        ('study_doi', 'Study DOI'),
        ('study_title', 'Study Title'),
        ('name', 'Group Name'),
        ('condition', 'Condition'),
        ('cohort', 'Cohort'),
        ('site', 'Site'),
        ('sample_size', 'Sample Size'),
    ],
    'comparison': [
        ('row_number', 'Row'),
        ('study_doi', 'Study DOI'),
        ('study_title', 'Study Title'),
        ('group_a_name', 'Group A'),
        ('group_b_name', 'Group B'),
        ('label', 'Label'),
    ],
    'metadata_variable': [
        ('row_number', 'Row'),
        ('name', 'Name'),
        ('display_name', 'Display Name'),
        ('value_type', 'Value Type'),
        ('is_filterable', 'Filterable'),
    ],
    'metadata_value': [
        ('row_number', 'Row'),
        ('study_doi', 'Study DOI'),
        ('study_title', 'Study Title'),
        ('group_name', 'Group'),
        ('variable_name', 'Variable'),
        ('value_float', 'Float'),
        ('value_int', 'Integer'),
        ('value_text', 'Text'),
        ('value_bool', 'Boolean'),
    ],
    'qualitative_finding': [
        ('row_number', 'Row'),
        ('study_doi', 'Study DOI'),
        ('study_title', 'Study Title'),
        ('group_a_name', 'Group A'),
        ('group_b_name', 'Group B'),
        ('comparison_label', 'Comparison'),
        ('taxon_scientific_name', 'Taxon'),
        ('direction', 'Direction'),
        ('source', 'Source'),
    ],
    'quantitative_finding': [
        ('row_number', 'Row'),
        ('study_doi', 'Study DOI'),
        ('study_title', 'Study Title'),
        ('group_name', 'Group'),
        ('taxon_scientific_name', 'Taxon'),
        ('value_type', 'Value Type'),
        ('value', 'Value'),
        ('unit', 'Unit'),
        ('source', 'Source'),
    ],
    'alpha_metric': [
        ('row_number', 'Row'),
        ('study_doi', 'Study DOI'),
        ('study_title', 'Study Title'),
        ('group_name', 'Group'),
        ('metric', 'Metric'),
        ('value', 'Value'),
        ('source', 'Source'),
    ],
    'beta_metric': [
        ('row_number', 'Row'),
        ('study_doi', 'Study DOI'),
        ('study_title', 'Study Title'),
        ('group_a_name', 'Group A'),
        ('group_b_name', 'Group B'),
        ('comparison_label', 'Comparison'),
        ('metric', 'Metric'),
        ('value', 'Value'),
        ('source', 'Source'),
    ],
}


@staff_member_required
@require_http_methods(['GET', 'POST'])
def upload_csv(request):
    if request.method == 'POST':
        form = CsvImportUploadForm(request.POST, request.FILES)
        if form.is_valid():
            data_file = form.cleaned_data['data_file']
            source_format = form.cleaned_data['source_format']
            import_type = (
                form.cleaned_data['import_type']
                if source_format == CsvImportUploadForm.SOURCE_FORMAT_CSV
                else CsvImportUploadForm.SOURCE_FORMAT_WORKBOOK
            )
            try:
                content = (
                    data_file.read().decode('utf-8-sig')
                    if source_format == CsvImportUploadForm.SOURCE_FORMAT_CSV
                    else data_file.read()
                )
                preview = build_preview(
                    file_name=data_file.name,
                    content=content,
                    import_type=import_type,
                    batch_name=form.cleaned_data['name'],
                )
            except (UnicodeDecodeError, ValueError) as exc:
                form.add_error('data_file', str(exc))
            else:
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
        [(key, key.replace('_', ' ').title()) for key in preview['valid_rows'][0].keys()] if preview.get('valid_rows') else [],
    )
    section_previews = []
    if import_type == CsvImportUploadForm.SOURCE_FORMAT_WORKBOOK:
        for section in preview.get('sections', []):
            section_columns = PREVIEW_COLUMNS.get(
                section['import_type'],
                [(key, key.replace('_', ' ').title()) for key in section['valid_rows'][0].keys()] if section.get('valid_rows') else [],
            )
            section_previews.append(
                {
                    **section,
                    'label': IMPORT_TYPE_LABELS.get(
                        section['import_type'],
                        section['import_type'].replace('_', ' ').title(),
                    ),
                    'preview_columns': section_columns,
                }
            )
    return render(
        request,
        'imports/preview.html',
        {
            'preview': preview,
            'import_label': IMPORT_TYPE_LABELS.get(import_type, import_type.replace('_', ' ').title()),
            'preview_columns': preview_columns,
            'section_previews': section_previews,
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

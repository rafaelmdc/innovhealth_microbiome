import csv
import json
from dataclasses import asdict, dataclass
from io import StringIO

from django.db import transaction

from database.models import (
    AlphaMetric,
    BetaMetric,
    CoreMetadata,
    ImportBatch,
    MetadataValue,
    MetadataVariable,
    Organism,
    RelativeAssociation,
    Sample,
    Study,
)


@dataclass
class ImportPreview:
    batch_name: str
    import_type: str
    required_columns: list[str]
    file_name: str
    total_rows: int
    valid_rows: list[dict]
    errors: list[dict]
    duplicates: list[dict]

    def to_dict(self):
        return asdict(self)


SUPPORTED_IMPORT_TYPES = (
    'organism',
    'study',
    'sample',
    'core_metadata',
    'metadata_variable',
    'metadata_value',
    'relative_association',
    'alpha_metric',
    'beta_metric',
)

BOOLEAN_TRUE_VALUES = {'1', 'true', 'yes', 'on'}
BOOLEAN_FALSE_VALUES = {'0', 'false', 'no', 'off'}


def build_preview(*, file_name, content, import_type, batch_name):
    if import_type not in SUPPORTED_IMPORT_TYPES:
        raise ValueError(f'Unsupported import type: {import_type}')

    reader = csv.DictReader(StringIO(content))
    fieldnames = reader.fieldnames or []
    rows = list(reader)

    # Each import type owns its own contract and validation path instead of
    # sharing one generic parser with many conditional branches.
    preview_builder = PREVIEW_BUILDERS[import_type]
    return preview_builder(
        file_name=file_name,
        fieldnames=fieldnames,
        rows=rows,
        batch_name=batch_name,
        import_type=import_type,
    )


@transaction.atomic
def run_import(preview_data):
    import_type = preview_data['import_type']
    if import_type not in IMPORT_RUNNERS:
        raise ValueError(f'Unsupported import type: {import_type}')

    batch = ImportBatch.objects.create(
        name=preview_data['batch_name'],
        import_type=f'{import_type}_csv',
        status=ImportBatch.Status.VALIDATED,
        source_file=preview_data.get('file_name', ''),
    )

    created_count = IMPORT_RUNNERS[import_type](preview_data['valid_rows'], batch)
    duplicate_count = len(preview_data.get('duplicates', []))
    error_count = len(preview_data.get('errors', []))
    batch.success_count = created_count
    batch.error_count = duplicate_count + error_count
    batch.status = ImportBatch.Status.COMPLETED if error_count == 0 else ImportBatch.Status.FAILED
    batch.notes = (
        f'Imported {created_count} {import_type} rows from CSV. '
        f'Skipped {duplicate_count} duplicates. '
        f'Validation errors: {error_count}.'
    )
    batch.save(update_fields=['success_count', 'error_count', 'status', 'notes'])
    return batch


def _missing_columns_preview(*, batch_name, import_type, file_name, required_columns, missing_columns):
    return ImportPreview(
        batch_name=batch_name,
        import_type=import_type,
        required_columns=list(required_columns),
        file_name=file_name,
        total_rows=0,
        valid_rows=[],
        errors=[
            {
                'row_number': None,
                'message': f'Missing required columns: {", ".join(missing_columns)}',
            }
        ],
        duplicates=[],
    )


def _build_preview_response(*, batch_name, import_type, file_name, required_columns, valid_rows, errors, duplicates):
    return ImportPreview(
        batch_name=batch_name,
        import_type=import_type,
        required_columns=list(required_columns),
        file_name=file_name,
        total_rows=len(valid_rows) + len(errors) + len(duplicates),
        valid_rows=valid_rows,
        errors=errors,
        duplicates=duplicates,
    )


def _cleaned_row(raw_row):
    return {key: (value or '').strip() for key, value in raw_row.items()}


def _parse_int(value, field_name):
    try:
        return int(value), None
    except (TypeError, ValueError):
        return None, f'{field_name} must be an integer.'


def _parse_float(value, field_name):
    try:
        return float(value), None
    except (TypeError, ValueError):
        return None, f'{field_name} must be a float.'


def _parse_optional_int(value, field_name):
    if value == '':
        return None, None
    return _parse_int(value, field_name)


def _parse_optional_float(value, field_name):
    if value == '':
        return None, None
    return _parse_float(value, field_name)


def _parse_optional_bool(value, field_name):
    if value == '':
        return None, None
    normalized = value.lower()
    if normalized in BOOLEAN_TRUE_VALUES:
        return True, None
    if normalized in BOOLEAN_FALSE_VALUES:
        return False, None
    return None, f'{field_name} must be a boolean.'


def _resolve_sample(study_source_doi, sample_label):
    # Sample lookups intentionally use the contract-level natural key rather
    # than exposing internal database IDs in CSV files.
    return Sample.objects.filter(
        study__source_doi=study_source_doi,
        label=sample_label,
    ).select_related('study').first()


def _build_organism_preview(*, file_name, fieldnames, rows, batch_name, import_type):
    required_columns = ('ncbi_taxonomy_id', 'scientific_name', 'taxonomic_rank')
    missing_columns = [column for column in required_columns if column not in fieldnames]
    if missing_columns:
        return _missing_columns_preview(
            batch_name=batch_name,
            import_type=import_type,
            file_name=file_name,
            required_columns=required_columns,
            missing_columns=missing_columns,
        )

    existing_taxonomy_ids = set(Organism.objects.values_list('ncbi_taxonomy_id', flat=True))
    seen_taxonomy_ids = set()
    valid_rows = []
    errors = []
    duplicates = []

    for row_number, raw_row in enumerate(rows, start=2):
        row = _cleaned_row(raw_row)
        taxonomy_id, error = _parse_int(row['ncbi_taxonomy_id'], 'ncbi_taxonomy_id')
        if error:
            errors.append({'row_number': row_number, 'message': error})
            continue
        if not row['scientific_name'] or not row['taxonomic_rank']:
            errors.append({'row_number': row_number, 'message': 'scientific_name and taxonomic_rank are required.'})
            continue

        duplicate_key = taxonomy_id
        if duplicate_key in seen_taxonomy_ids:
            duplicates.append({'row_number': row_number, 'message': 'Duplicate ncbi_taxonomy_id in uploaded file.', 'taxonomy_id': taxonomy_id})
            continue
        if duplicate_key in existing_taxonomy_ids:
            duplicates.append({'row_number': row_number, 'message': 'Organism with this ncbi_taxonomy_id already exists.', 'taxonomy_id': taxonomy_id})
            continue

        parent_taxonomy_id, parent_error = _parse_optional_int(row.get('parent_ncbi_taxonomy_id', ''), 'parent_ncbi_taxonomy_id')
        if parent_error:
            errors.append({'row_number': row_number, 'message': parent_error})
            continue

        seen_taxonomy_ids.add(duplicate_key)
        valid_rows.append(
            {
                'row_number': row_number,
                'ncbi_taxonomy_id': taxonomy_id,
                'scientific_name': row['scientific_name'],
                'taxonomic_rank': row['taxonomic_rank'],
                'parent_ncbi_taxonomy_id': parent_taxonomy_id,
                'genus': row.get('genus', ''),
                'species': row.get('species', ''),
                'notes': row.get('notes', ''),
            }
        )

    return _build_preview_response(
        batch_name=batch_name,
        import_type=import_type,
        file_name=file_name,
        required_columns=required_columns,
        valid_rows=valid_rows,
        errors=errors,
        duplicates=duplicates,
    )


def _build_study_preview(*, file_name, fieldnames, rows, batch_name, import_type):
    required_columns = ('title',)
    missing_columns = [column for column in required_columns if column not in fieldnames]
    if missing_columns:
        return _missing_columns_preview(
            batch_name=batch_name,
            import_type=import_type,
            file_name=file_name,
            required_columns=required_columns,
            missing_columns=missing_columns,
        )

    existing_dois = set(
        Study.objects.exclude(source_doi__isnull=True).exclude(source_doi='').values_list('source_doi', flat=True)
    )
    seen_dois = set()
    valid_rows = []
    errors = []
    duplicates = []

    for row_number, raw_row in enumerate(rows, start=2):
        row = _cleaned_row(raw_row)
        if not row['title']:
            errors.append({'row_number': row_number, 'message': 'title is required.'})
            continue

        publication_year, year_error = _parse_optional_int(row.get('publication_year', ''), 'publication_year')
        if year_error:
            errors.append({'row_number': row_number, 'message': year_error})
            continue

        source_doi = row.get('source_doi', '')
        if source_doi:
            if source_doi in seen_dois:
                duplicates.append({'row_number': row_number, 'message': 'Duplicate source_doi in uploaded file.', 'source_doi': source_doi})
                continue
            if source_doi in existing_dois:
                duplicates.append({'row_number': row_number, 'message': 'Study with this source_doi already exists.', 'source_doi': source_doi})
                continue
            seen_dois.add(source_doi)

        valid_rows.append(
            {
                'row_number': row_number,
                'source_doi': source_doi or None,
                'title': row['title'],
                'country': row.get('country', ''),
                'journal': row.get('journal', ''),
                'publication_year': publication_year,
                'notes': row.get('notes', ''),
            }
        )

    return _build_preview_response(
        batch_name=batch_name,
        import_type=import_type,
        file_name=file_name,
        required_columns=required_columns,
        valid_rows=valid_rows,
        errors=errors,
        duplicates=duplicates,
    )


def _build_sample_preview(*, file_name, fieldnames, rows, batch_name, import_type):
    required_columns = ('study_source_doi', 'label')
    missing_columns = [column for column in required_columns if column not in fieldnames]
    if missing_columns:
        return _missing_columns_preview(
            batch_name=batch_name,
            import_type=import_type,
            file_name=file_name,
            required_columns=required_columns,
            missing_columns=missing_columns,
        )

    existing_pairs = set(
        Sample.objects.exclude(study__source_doi__isnull=True).values_list('study__source_doi', 'label')
    )
    seen_pairs = set()
    study_map = {
        study.source_doi: study.id
        for study in Study.objects.exclude(source_doi__isnull=True).exclude(source_doi='')
    }
    valid_rows = []
    errors = []
    duplicates = []

    for row_number, raw_row in enumerate(rows, start=2):
        row = _cleaned_row(raw_row)
        study_source_doi = row['study_source_doi']
        label = row['label']
        if not study_source_doi or not label:
            errors.append({'row_number': row_number, 'message': 'study_source_doi and label are required.'})
            continue
        study_id = study_map.get(study_source_doi)
        if not study_id:
            errors.append({'row_number': row_number, 'message': 'study_source_doi does not resolve to an existing Study.'})
            continue

        sample_size, sample_size_error = _parse_optional_int(row.get('sample_size', ''), 'sample_size')
        if sample_size_error:
            errors.append({'row_number': row_number, 'message': sample_size_error})
            continue

        duplicate_key = (study_source_doi, label)
        if duplicate_key in seen_pairs:
            duplicates.append({'row_number': row_number, 'message': 'Duplicate study/sample pair in uploaded file.', 'study_source_doi': study_source_doi, 'label': label})
            continue
        if duplicate_key in existing_pairs:
            duplicates.append({'row_number': row_number, 'message': 'Sample with this study_source_doi and label already exists.', 'study_source_doi': study_source_doi, 'label': label})
            continue
        seen_pairs.add(duplicate_key)

        valid_rows.append(
            {
                'row_number': row_number,
                'study_id': study_id,
                'study_source_doi': study_source_doi,
                'label': label,
                'site': row.get('site', ''),
                'method': row.get('method', ''),
                'cohort': row.get('cohort', ''),
                'sample_size': sample_size,
                'notes': row.get('notes', ''),
            }
        )

    return _build_preview_response(
        batch_name=batch_name,
        import_type=import_type,
        file_name=file_name,
        required_columns=required_columns,
        valid_rows=valid_rows,
        errors=errors,
        duplicates=duplicates,
    )


def _build_core_metadata_preview(*, file_name, fieldnames, rows, batch_name, import_type):
    required_columns = ('study_source_doi', 'sample_label')
    missing_columns = [column for column in required_columns if column not in fieldnames]
    if missing_columns:
        return _missing_columns_preview(
            batch_name=batch_name,
            import_type=import_type,
            file_name=file_name,
            required_columns=required_columns,
            missing_columns=missing_columns,
        )

    existing_sample_ids = set(CoreMetadata.objects.values_list('sample_id', flat=True))
    seen_pairs = set()
    valid_rows = []
    errors = []
    duplicates = []

    for row_number, raw_row in enumerate(rows, start=2):
        row = _cleaned_row(raw_row)
        if not row['study_source_doi'] or not row['sample_label']:
            errors.append({'row_number': row_number, 'message': 'study_source_doi and sample_label are required.'})
            continue

        sample = _resolve_sample(row['study_source_doi'], row['sample_label'])
        if not sample:
            errors.append({'row_number': row_number, 'message': 'study_source_doi and sample_label do not resolve to an existing Sample.'})
            continue

        numeric_values = {}
        numeric_error = None
        for field_name in ('male_percent', 'age_mean', 'age_sd', 'bmi_mean', 'bmi_sd'):
            value, error = _parse_optional_float(row.get(field_name, ''), field_name)
            if error:
                numeric_error = error
                break
            numeric_values[field_name] = value
        if numeric_error:
            errors.append({'row_number': row_number, 'message': numeric_error})
            continue

        duplicate_key = (row['study_source_doi'], row['sample_label'])
        if duplicate_key in seen_pairs:
            duplicates.append({'row_number': row_number, 'message': 'Duplicate study/sample pair in uploaded file.'})
            continue
        if sample.pk in existing_sample_ids:
            duplicates.append({'row_number': row_number, 'message': 'CoreMetadata already exists for this sample.'})
            continue
        seen_pairs.add(duplicate_key)

        valid_rows.append(
            {
                'row_number': row_number,
                'sample_id': sample.pk,
                'study_source_doi': row['study_source_doi'],
                'sample_label': row['sample_label'],
                'condition': row.get('condition', ''),
                **numeric_values,
                'notes': row.get('notes', ''),
            }
        )

    return _build_preview_response(
        batch_name=batch_name,
        import_type=import_type,
        file_name=file_name,
        required_columns=required_columns,
        valid_rows=valid_rows,
        errors=errors,
        duplicates=duplicates,
    )


def _build_metadata_variable_preview(*, file_name, fieldnames, rows, batch_name, import_type):
    required_columns = ('name', 'display_name', 'value_type')
    missing_columns = [column for column in required_columns if column not in fieldnames]
    if missing_columns:
        return _missing_columns_preview(
            batch_name=batch_name,
            import_type=import_type,
            file_name=file_name,
            required_columns=required_columns,
            missing_columns=missing_columns,
        )

    existing_names = set(MetadataVariable.objects.values_list('name', flat=True))
    seen_names = set()
    valid_rows = []
    errors = []
    duplicates = []

    for row_number, raw_row in enumerate(rows, start=2):
        row = _cleaned_row(raw_row)
        name = row['name']
        display_name = row['display_name']
        value_type = row['value_type']
        if not name or not display_name or not value_type:
            errors.append({'row_number': row_number, 'message': 'name, display_name, and value_type are required.'})
            continue
        if value_type not in MetadataVariable.ValueType.values:
            errors.append({'row_number': row_number, 'message': 'value_type must be one of: float, int, text, bool.'})
            continue

        is_filterable, bool_error = _parse_optional_bool(row.get('is_filterable', ''), 'is_filterable')
        if bool_error:
            errors.append({'row_number': row_number, 'message': bool_error})
            continue

        allowed_values = []
        if row.get('allowed_values', ''):
            try:
                allowed_values = json.loads(row['allowed_values'])
            except json.JSONDecodeError:
                errors.append({'row_number': row_number, 'message': 'allowed_values must be a JSON array.'})
                continue
            if not isinstance(allowed_values, list):
                errors.append({'row_number': row_number, 'message': 'allowed_values must be a JSON array.'})
                continue

        if name in seen_names:
            duplicates.append({'row_number': row_number, 'message': 'Duplicate variable name in uploaded file.', 'name': name})
            continue
        if name in existing_names:
            duplicates.append({'row_number': row_number, 'message': 'MetadataVariable with this name already exists.', 'name': name})
            continue
        seen_names.add(name)

        valid_rows.append(
            {
                'row_number': row_number,
                'name': name,
                'display_name': display_name,
                'domain': row.get('domain', ''),
                'value_type': value_type,
                'default_unit': row.get('default_unit', ''),
                'description': row.get('description', ''),
                'is_filterable': False if is_filterable is None else is_filterable,
                'allowed_values': allowed_values,
            }
        )

    return _build_preview_response(
        batch_name=batch_name,
        import_type=import_type,
        file_name=file_name,
        required_columns=required_columns,
        valid_rows=valid_rows,
        errors=errors,
        duplicates=duplicates,
    )


def _build_metadata_value_preview(*, file_name, fieldnames, rows, batch_name, import_type):
    required_columns = ('study_source_doi', 'sample_label', 'variable_name')
    missing_columns = [column for column in required_columns if column not in fieldnames]
    if missing_columns:
        return _missing_columns_preview(
            batch_name=batch_name,
            import_type=import_type,
            file_name=file_name,
            required_columns=required_columns,
            missing_columns=missing_columns,
        )

    existing_keys = {
        (study_source_doi, label, variable_name)
        for study_source_doi, label, variable_name in MetadataValue.objects.filter(
            sample__study__source_doi__isnull=False
        ).values_list('sample__study__source_doi', 'sample__label', 'variable__name')
    }
    variables = {variable.name: variable for variable in MetadataVariable.objects.all()}
    seen_keys = set()
    valid_rows = []
    errors = []
    duplicates = []

    for row_number, raw_row in enumerate(rows, start=2):
        row = _cleaned_row(raw_row)
        if not row['study_source_doi'] or not row['sample_label'] or not row['variable_name']:
            errors.append({'row_number': row_number, 'message': 'study_source_doi, sample_label, and variable_name are required.'})
            continue

        sample = _resolve_sample(row['study_source_doi'], row['sample_label'])
        if not sample:
            errors.append({'row_number': row_number, 'message': 'study_source_doi and sample_label do not resolve to an existing Sample.'})
            continue

        variable = variables.get(row['variable_name'])
        if not variable:
            errors.append({'row_number': row_number, 'message': 'variable_name does not resolve to an existing MetadataVariable.'})
            continue

        # The EAV contract allows exactly one typed value and it must match
        # the variable's declared value_type, so both checks happen here
        # before the row is allowed into the preview.
        typed_fields = {}
        typed_count = 0

        value_float, float_error = _parse_optional_float(row.get('value_float', ''), 'value_float')
        if float_error:
            errors.append({'row_number': row_number, 'message': float_error})
            continue
        typed_fields['value_float'] = value_float
        typed_count += value_float is not None

        value_int, int_error = _parse_optional_int(row.get('value_int', ''), 'value_int')
        if int_error:
            errors.append({'row_number': row_number, 'message': int_error})
            continue
        typed_fields['value_int'] = value_int
        typed_count += value_int is not None

        value_text = row.get('value_text', '')
        typed_fields['value_text'] = value_text or None
        typed_count += bool(value_text)

        value_bool, bool_error = _parse_optional_bool(row.get('value_bool', ''), 'value_bool')
        if bool_error:
            errors.append({'row_number': row_number, 'message': bool_error})
            continue
        typed_fields['value_bool'] = value_bool
        typed_count += value_bool is not None

        if typed_count != 1:
            errors.append({'row_number': row_number, 'message': 'Exactly one typed value field must be populated.'})
            continue

        expected_field = {
            MetadataVariable.ValueType.FLOAT: 'value_float',
            MetadataVariable.ValueType.INTEGER: 'value_int',
            MetadataVariable.ValueType.TEXT: 'value_text',
            MetadataVariable.ValueType.BOOLEAN: 'value_bool',
        }[variable.value_type]
        populated_field = next(field_name for field_name, value in typed_fields.items() if value is not None)
        if expected_field != populated_field:
            errors.append({'row_number': row_number, 'message': f'Variable "{variable.name}" requires {expected_field}.'})
            continue

        duplicate_key = (row['study_source_doi'], row['sample_label'], variable.name)
        if duplicate_key in seen_keys:
            duplicates.append({'row_number': row_number, 'message': 'Duplicate sample/variable row in uploaded file.'})
            continue
        if duplicate_key in existing_keys:
            duplicates.append({'row_number': row_number, 'message': 'MetadataValue already exists for this sample and variable.'})
            continue
        seen_keys.add(duplicate_key)

        valid_rows.append(
            {
                'row_number': row_number,
                'sample_id': sample.pk,
                'variable_id': variable.pk,
                'study_source_doi': row['study_source_doi'],
                'sample_label': row['sample_label'],
                'variable_name': variable.name,
                **typed_fields,
                'unit': row.get('unit', ''),
                'raw_value': row.get('raw_value', ''),
                'variation': row.get('variation', ''),
                'notes': row.get('notes', ''),
            }
        )

    return _build_preview_response(
        batch_name=batch_name,
        import_type=import_type,
        file_name=file_name,
        required_columns=required_columns,
        valid_rows=valid_rows,
        errors=errors,
        duplicates=duplicates,
    )


def _build_relative_association_preview(*, file_name, fieldnames, rows, batch_name, import_type):
    required_columns = (
        'study_source_doi',
        'sample_label',
        'organism_1_taxonomy_id',
        'organism_2_taxonomy_id',
        'association_type',
    )
    missing_columns = [column for column in required_columns if column not in fieldnames]
    if missing_columns:
        return _missing_columns_preview(
            batch_name=batch_name,
            import_type=import_type,
            file_name=file_name,
            required_columns=required_columns,
            missing_columns=missing_columns,
        )

    organisms = {organism.ncbi_taxonomy_id: organism for organism in Organism.objects.all()}
    existing_keys = set(
        RelativeAssociation.objects.values_list(
            'sample_id',
            'organism_1_id',
            'organism_2_id',
            'association_type',
        )
    )
    seen_keys = set()
    valid_rows = []
    errors = []
    duplicates = []

    for row_number, raw_row in enumerate(rows, start=2):
        row = _cleaned_row(raw_row)
        if not row['study_source_doi'] or not row['sample_label'] or not row['association_type']:
            errors.append({'row_number': row_number, 'message': 'study_source_doi, sample_label, and association_type are required.'})
            continue

        sample = _resolve_sample(row['study_source_doi'], row['sample_label'])
        if not sample:
            errors.append({'row_number': row_number, 'message': 'study_source_doi and sample_label do not resolve to an existing Sample.'})
            continue

        taxonomy_1, error_1 = _parse_int(row['organism_1_taxonomy_id'], 'organism_1_taxonomy_id')
        taxonomy_2, error_2 = _parse_int(row['organism_2_taxonomy_id'], 'organism_2_taxonomy_id')
        if error_1 or error_2:
            errors.append({'row_number': row_number, 'message': error_1 or error_2})
            continue
        if taxonomy_1 == taxonomy_2:
            errors.append({'row_number': row_number, 'message': 'RelativeAssociation self-pairs are not allowed.'})
            continue

        organism_1 = organisms.get(taxonomy_1)
        organism_2 = organisms.get(taxonomy_2)
        if not organism_1 or not organism_2:
            errors.append({'row_number': row_number, 'message': 'Both organism taxonomy IDs must resolve to existing Organism rows.'})
            continue

        # Reverse organism pairs should collapse onto one canonical key so
        # duplicate detection matches the model constraint.
        if organism_1.pk > organism_2.pk:
            organism_1, organism_2 = organism_2, organism_1
            taxonomy_1, taxonomy_2 = taxonomy_2, taxonomy_1

        parsed_values = {}
        numeric_error = None
        for field_name in ('value', 'p_value', 'q_value', 'confidence'):
            value, error = _parse_optional_float(row.get(field_name, ''), field_name)
            if error:
                numeric_error = error
                break
            parsed_values[field_name] = value
        if numeric_error:
            errors.append({'row_number': row_number, 'message': numeric_error})
            continue

        sign = row.get('sign', '')
        if sign and sign not in RelativeAssociation.Sign.values:
            errors.append({'row_number': row_number, 'message': 'sign must be one of: positive, negative, neutral.'})
            continue

        duplicate_key = (sample.pk, organism_1.pk, organism_2.pk, row['association_type'])
        if duplicate_key in seen_keys:
            duplicates.append({'row_number': row_number, 'message': 'Duplicate association row in uploaded file.'})
            continue
        if duplicate_key in existing_keys:
            duplicates.append({'row_number': row_number, 'message': 'RelativeAssociation already exists for this canonical organism pair and association type.'})
            continue
        seen_keys.add(duplicate_key)

        valid_rows.append(
            {
                'row_number': row_number,
                'sample_id': sample.pk,
                'study_source_doi': row['study_source_doi'],
                'sample_label': row['sample_label'],
                'organism_1_id': organism_1.pk,
                'organism_2_id': organism_2.pk,
                'organism_1_taxonomy_id': taxonomy_1,
                'organism_2_taxonomy_id': taxonomy_2,
                'association_type': row['association_type'],
                **parsed_values,
                'sign': sign,
                'method': row.get('method', ''),
                'notes': row.get('notes', ''),
            }
        )

    return _build_preview_response(
        batch_name=batch_name,
        import_type=import_type,
        file_name=file_name,
        required_columns=required_columns,
        valid_rows=valid_rows,
        errors=errors,
        duplicates=duplicates,
    )


def _build_alpha_metric_preview(*, file_name, fieldnames, rows, batch_name, import_type):
    required_columns = ('study_source_doi', 'sample_label', 'metric_type', 'value')
    missing_columns = [column for column in required_columns if column not in fieldnames]
    if missing_columns:
        return _missing_columns_preview(
            batch_name=batch_name,
            import_type=import_type,
            file_name=file_name,
            required_columns=required_columns,
            missing_columns=missing_columns,
        )

    existing_keys = set(
        AlphaMetric.objects.filter(sample__study__source_doi__isnull=False).values_list(
            'sample__study__source_doi',
            'sample__label',
            'metric_type',
        )
    )
    seen_keys = set()
    valid_rows = []
    errors = []
    duplicates = []

    for row_number, raw_row in enumerate(rows, start=2):
        row = _cleaned_row(raw_row)
        if not row['study_source_doi'] or not row['sample_label'] or not row['metric_type']:
            errors.append({'row_number': row_number, 'message': 'study_source_doi, sample_label, and metric_type are required.'})
            continue

        sample = _resolve_sample(row['study_source_doi'], row['sample_label'])
        if not sample:
            errors.append({'row_number': row_number, 'message': 'study_source_doi and sample_label do not resolve to an existing Sample.'})
            continue

        value, value_error = _parse_float(row.get('value', ''), 'value')
        if value_error:
            errors.append({'row_number': row_number, 'message': value_error})
            continue

        duplicate_key = (row['study_source_doi'], row['sample_label'], row['metric_type'])
        if duplicate_key in seen_keys:
            duplicates.append({'row_number': row_number, 'message': 'Duplicate alpha metric row in uploaded file.'})
            continue
        if duplicate_key in existing_keys:
            duplicates.append({'row_number': row_number, 'message': 'AlphaMetric already exists for this sample and metric type.'})
            continue
        seen_keys.add(duplicate_key)

        valid_rows.append(
            {
                'row_number': row_number,
                'sample_id': sample.pk,
                'study_source_doi': row['study_source_doi'],
                'sample_label': row['sample_label'],
                'metric_type': row['metric_type'],
                'value': value,
                'unit': row.get('unit', ''),
                'notes': row.get('notes', ''),
            }
        )

    return _build_preview_response(
        batch_name=batch_name,
        import_type=import_type,
        file_name=file_name,
        required_columns=required_columns,
        valid_rows=valid_rows,
        errors=errors,
        duplicates=duplicates,
    )


def _build_beta_metric_preview(*, file_name, fieldnames, rows, batch_name, import_type):
    required_columns = ('study_source_doi', 'sample_1_label', 'sample_2_label', 'metric_type', 'value')
    missing_columns = [column for column in required_columns if column not in fieldnames]
    if missing_columns:
        return _missing_columns_preview(
            batch_name=batch_name,
            import_type=import_type,
            file_name=file_name,
            required_columns=required_columns,
            missing_columns=missing_columns,
        )

    existing_keys = set(
        BetaMetric.objects.filter(sample_a__study__source_doi__isnull=False).values_list(
            'sample_a__study__source_doi',
            'sample_a__label',
            'sample_b__label',
            'metric_type',
        )
    )
    seen_keys = set()
    valid_rows = []
    errors = []
    duplicates = []

    for row_number, raw_row in enumerate(rows, start=2):
        row = _cleaned_row(raw_row)
        if not row['study_source_doi'] or not row['sample_1_label'] or not row['sample_2_label'] or not row['metric_type']:
            errors.append({'row_number': row_number, 'message': 'study_source_doi, sample_1_label, sample_2_label, and metric_type are required.'})
            continue

        sample_1 = _resolve_sample(row['study_source_doi'], row['sample_1_label'])
        sample_2 = _resolve_sample(row['study_source_doi'], row['sample_2_label'])
        if not sample_1 or not sample_2:
            errors.append({'row_number': row_number, 'message': 'Both study/sample lookups must resolve to existing Sample rows.'})
            continue
        if sample_1.pk == sample_2.pk:
            errors.append({'row_number': row_number, 'message': 'BetaMetric self-pairs are not allowed.'})
            continue

        value, value_error = _parse_float(row.get('value', ''), 'value')
        if value_error:
            errors.append({'row_number': row_number, 'message': value_error})
            continue

        if sample_1.pk > sample_2.pk:
            sample_1, sample_2 = sample_2, sample_1

        duplicate_key = (
            row['study_source_doi'],
            sample_1.label,
            sample_2.label,
            row['metric_type'],
        )
        if duplicate_key in seen_keys:
            duplicates.append({'row_number': row_number, 'message': 'Duplicate beta metric row in uploaded file.'})
            continue
        if duplicate_key in existing_keys:
            duplicates.append({'row_number': row_number, 'message': 'BetaMetric already exists for this canonical sample pair and metric type.'})
            continue
        seen_keys.add(duplicate_key)

        valid_rows.append(
            {
                'row_number': row_number,
                'sample_a_id': sample_1.pk,
                'sample_b_id': sample_2.pk,
                'study_source_doi': row['study_source_doi'],
                'sample_1_label': sample_1.label,
                'sample_2_label': sample_2.label,
                'metric_type': row['metric_type'],
                'value': value,
                'unit': row.get('unit', ''),
                'notes': row.get('notes', ''),
            }
        )

    return _build_preview_response(
        batch_name=batch_name,
        import_type=import_type,
        file_name=file_name,
        required_columns=required_columns,
        valid_rows=valid_rows,
        errors=errors,
        duplicates=duplicates,
    )


def _run_organism_import(valid_rows, batch):
    created_organisms = []
    taxonomy_to_row = {row['ncbi_taxonomy_id']: row for row in valid_rows}
    for row in valid_rows:
        created_organisms.append(
            Organism.objects.create(
                ncbi_taxonomy_id=row['ncbi_taxonomy_id'],
                scientific_name=row['scientific_name'],
                taxonomic_rank=row['taxonomic_rank'],
                genus=row.get('genus', ''),
                species=row.get('species', ''),
                notes=row.get('notes', ''),
            )
        )

    # Parent organisms may appear later in the same CSV, so parent links are
    # resolved after the first pass creates all referenced rows.
    created_by_taxonomy = {organism.ncbi_taxonomy_id: organism for organism in created_organisms}
    parent_updates = []
    for organism in created_organisms:
        parent_taxonomy_id = taxonomy_to_row[organism.ncbi_taxonomy_id].get('parent_ncbi_taxonomy_id')
        if not parent_taxonomy_id:
            continue
        parent = created_by_taxonomy.get(parent_taxonomy_id) or Organism.objects.filter(
            ncbi_taxonomy_id=parent_taxonomy_id
        ).first()
        if parent:
            organism.parent_taxonomy = parent
            parent_updates.append(organism)
    if parent_updates:
        Organism.objects.bulk_update(parent_updates, ['parent_taxonomy'])
    return len(created_organisms)


def _run_study_import(valid_rows, batch):
    for row in valid_rows:
        Study.objects.create(
            source_doi=row['source_doi'],
            title=row['title'],
            country=row['country'],
            journal=row['journal'],
            publication_year=row['publication_year'],
            notes=row['notes'],
        )
    return len(valid_rows)


def _run_sample_import(valid_rows, batch):
    for row in valid_rows:
        Sample.objects.create(
            study_id=row['study_id'],
            label=row['label'],
            site=row['site'],
            method=row['method'],
            cohort=row['cohort'],
            sample_size=row['sample_size'],
            notes=row['notes'],
        )
    return len(valid_rows)


def _run_core_metadata_import(valid_rows, batch):
    for row in valid_rows:
        CoreMetadata.objects.create(
            sample_id=row['sample_id'],
            condition=row['condition'],
            male_percent=row['male_percent'],
            age_mean=row['age_mean'],
            age_sd=row['age_sd'],
            bmi_mean=row['bmi_mean'],
            bmi_sd=row['bmi_sd'],
            notes=row['notes'],
        )
    return len(valid_rows)


def _run_metadata_variable_import(valid_rows, batch):
    for row in valid_rows:
        MetadataVariable.objects.create(
            name=row['name'],
            display_name=row['display_name'],
            domain=row['domain'],
            value_type=row['value_type'],
            default_unit=row['default_unit'],
            description=row['description'],
            is_filterable=row['is_filterable'],
            allowed_values=row['allowed_values'],
        )
    return len(valid_rows)


def _run_metadata_value_import(valid_rows, batch):
    for row in valid_rows:
        MetadataValue.objects.create(
            sample_id=row['sample_id'],
            variable_id=row['variable_id'],
            value_float=row['value_float'],
            value_int=row['value_int'],
            value_text=row['value_text'],
            value_bool=row['value_bool'],
            unit=row['unit'],
            raw_value=row['raw_value'],
            variation=row['variation'],
            notes=row['notes'],
            import_batch=batch,
        )
    return len(valid_rows)


def _run_relative_association_import(valid_rows, batch):
    for row in valid_rows:
        RelativeAssociation.objects.create(
            sample_id=row['sample_id'],
            organism_1_id=row['organism_1_id'],
            organism_2_id=row['organism_2_id'],
            association_type=row['association_type'],
            value=row['value'],
            sign=row['sign'],
            p_value=row['p_value'],
            q_value=row['q_value'],
            method=row['method'],
            confidence=row['confidence'],
            notes=row['notes'],
            import_batch=batch,
        )
    return len(valid_rows)


def _run_alpha_metric_import(valid_rows, batch):
    for row in valid_rows:
        AlphaMetric.objects.create(
            sample_id=row['sample_id'],
            metric_type=row['metric_type'],
            value=row['value'],
            unit=row['unit'],
            notes=row['notes'],
            import_batch=batch,
        )
    return len(valid_rows)


def _run_beta_metric_import(valid_rows, batch):
    for row in valid_rows:
        BetaMetric.objects.create(
            sample_a_id=row['sample_a_id'],
            sample_b_id=row['sample_b_id'],
            metric_type=row['metric_type'],
            value=row['value'],
            unit=row['unit'],
            notes=row['notes'],
            import_batch=batch,
        )
    return len(valid_rows)


PREVIEW_BUILDERS = {
    'organism': _build_organism_preview,
    'study': _build_study_preview,
    'sample': _build_sample_preview,
    'core_metadata': _build_core_metadata_preview,
    'metadata_variable': _build_metadata_variable_preview,
    'metadata_value': _build_metadata_value_preview,
    'relative_association': _build_relative_association_preview,
    'alpha_metric': _build_alpha_metric_preview,
    'beta_metric': _build_beta_metric_preview,
}

# These registries are the extension points for new import types: add both a
# preview builder and an import runner to keep validation and writes aligned.
IMPORT_RUNNERS = {
    'organism': _run_organism_import,
    'study': _run_study_import,
    'sample': _run_sample_import,
    'core_metadata': _run_core_metadata_import,
    'metadata_variable': _run_metadata_variable_import,
    'metadata_value': _run_metadata_value_import,
    'relative_association': _run_relative_association_import,
    'alpha_metric': _run_alpha_metric_import,
    'beta_metric': _run_beta_metric_import,
}

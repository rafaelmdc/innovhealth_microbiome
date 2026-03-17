"""Workbook preview builders for extra metadata and metadata-derived sections."""

from database.models import MetadataVariable

from .helpers import cleaned_row, parse_float, parse_int, parse_optional_bool
from .workbook_common import build_section_preview, missing_columns_error


def collect_extra_metadata_rows(*, sheet, state):
    """Collect free-form extra metadata rows into the raw metadata staging list."""
    required_columns = ('paper_id', 'group_id', 'field_name', 'value_as_written')
    errors = []

    missing_columns = missing_columns_error(required_columns, sheet['fieldnames'])
    if missing_columns and sheet['rows']:
        errors.append({'row_number': None, 'message': missing_columns})
        return errors

    for row in sheet['rows']:
        row_number = row['row_number']
        data = cleaned_row(row['data'])
        paper_id = data.get('paper_id', '')

        if paper_id not in state['paper_status_by_id']:
            errors.append({'row_number': row_number, 'message': 'paper_id does not exist in the paper sheet.'})
            continue
        if state['paper_status_by_id'][paper_id] != 'complete':
            state['skipped_rows'].append(
                {
                    'section': 'extra_metadata',
                    'row_number': row_number,
                    'message': f'Skipped because paper {paper_id} is not complete.',
                }
            )
            continue

        group_ref = state['group_refs'].get(data.get('group_id', ''))
        if not group_ref:
            errors.append({'row_number': row_number, 'message': 'group_id does not resolve to a valid group.'})
            continue

        field_name = data.get('field_name', '')
        value_as_written = data.get('value_as_written', '')
        if not field_name:
            errors.append({'row_number': row_number, 'message': 'field_name is required.'})
            continue
        if not value_as_written:
            continue

        state['raw_metadata_values'].append(
            {
                'row_number': row_number,
                'study_doi': group_ref['study_doi'],
                'study_title': group_ref['study_title'],
                'group_name': group_ref['group_name'],
                'variable_name': field_name,
                'display_name': field_name.replace('_', ' ').title(),
                'preferred_value_type': MetadataVariable.ValueType.TEXT,
                'raw_value': value_as_written,
            }
        )

    return errors


def build_metadata_sections(*, batch_name, file_name, state, extra_metadata_errors):
    """Build metadata variable and metadata value sections from staged raw metadata rows."""
    required_columns = ('paper_id', 'group_id', 'field_name', 'value_as_written')
    existing_variables = {variable.name: variable for variable in MetadataVariable.objects.all()}
    metadata_variable_valid_rows = []
    planned_variable_names = set()
    metadata_variable_types = {}

    for metadata_row in state['raw_metadata_values']:
        variable_name = metadata_row['variable_name']
        if variable_name in metadata_variable_types:
            continue
        existing_variable = existing_variables.get(variable_name)
        if existing_variable:
            metadata_variable_types[variable_name] = existing_variable.value_type
        else:
            metadata_variable_types[variable_name] = metadata_row['preferred_value_type']
        if variable_name in planned_variable_names:
            continue
        planned_variable_names.add(variable_name)
        metadata_variable_valid_rows.append(
            {
                'row_number': metadata_row['row_number'],
                'name': variable_name,
                'display_name': metadata_row['display_name'],
                'value_type': metadata_variable_types[variable_name],
                'is_filterable': False,
            }
        )

    metadata_variable_section = build_section_preview(
        batch_name=batch_name,
        import_type='metadata_variable',
        file_name=file_name,
        required_columns=required_columns,
        valid_rows=metadata_variable_valid_rows,
        errors=extra_metadata_errors,
        duplicates=[],
        total_rows=len(metadata_variable_valid_rows),
    )

    metadata_value_valid_rows = []
    metadata_value_errors = []
    metadata_value_duplicates = []
    seen_metadata_value_keys = set()

    for metadata_row in state['raw_metadata_values']:
        variable_type = metadata_variable_types.get(
            metadata_row['variable_name'],
            metadata_row['preferred_value_type'],
        )
        typed_values, value_error = build_metadata_typed_values(
            variable_name=metadata_row['variable_name'],
            variable_type=variable_type,
            raw_value=metadata_row['raw_value'],
        )
        if value_error:
            metadata_value_errors.append(
                {
                    'row_number': metadata_row['row_number'],
                    'message': value_error,
                }
            )
            continue

        duplicate_key = (
            metadata_row['study_doi'] or '',
            metadata_row['study_title'],
            metadata_row['group_name'],
            metadata_row['variable_name'],
        )
        if duplicate_key in seen_metadata_value_keys:
            metadata_value_duplicates.append(
                {
                    'row_number': metadata_row['row_number'],
                    'message': 'Duplicate metadata value in workbook.',
                }
            )
            continue
        seen_metadata_value_keys.add(duplicate_key)

        metadata_value_valid_rows.append(
            {
                'row_number': metadata_row['row_number'],
                'study_doi': metadata_row['study_doi'],
                'study_title': metadata_row['study_title'],
                'group_name': metadata_row['group_name'],
                'variable_name': metadata_row['variable_name'],
                **typed_values,
            }
        )

    metadata_value_section = build_section_preview(
        batch_name=batch_name,
        import_type='metadata_value',
        file_name=file_name,
        required_columns=required_columns,
        valid_rows=metadata_value_valid_rows,
        errors=metadata_value_errors,
        duplicates=metadata_value_duplicates,
        total_rows=len(metadata_value_valid_rows) + len(metadata_value_errors) + len(metadata_value_duplicates),
    )
    return [metadata_variable_section, metadata_value_section]


def build_metadata_typed_values(*, variable_name, variable_type, raw_value):
    """Map a raw metadata value into the single typed field expected by `MetadataValue`."""
    typed_values = {
        'value_float': None,
        'value_int': None,
        'value_text': None,
        'value_bool': None,
    }
    if variable_type == MetadataVariable.ValueType.FLOAT:
        value_float, value_error = parse_float(raw_value, variable_name)
        if value_error:
            return typed_values, value_error
        typed_values['value_float'] = value_float
        return typed_values, None
    if variable_type == MetadataVariable.ValueType.INTEGER:
        value_int, value_error = parse_int(raw_value, variable_name)
        if value_error:
            return typed_values, value_error
        typed_values['value_int'] = value_int
        return typed_values, None
    if variable_type == MetadataVariable.ValueType.BOOLEAN:
        value_bool, value_error = parse_optional_bool(raw_value, variable_name)
        if value_error or value_bool is None:
            return typed_values, value_error or f'{variable_name} must be a boolean.'
        typed_values['value_bool'] = value_bool
        return typed_values, None

    typed_values['value_text'] = raw_value
    return typed_values, None

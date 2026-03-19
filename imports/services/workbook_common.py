"""Shared workbook preview helpers and state builders."""

from .types import ImportPreview


def build_workbook_state():
    """Return the mutable state shared across workbook sheet handlers."""
    return {
        'paper_status_by_id': {},
        'complete_paper_refs': {},
        'group_refs': {},
        'comparison_refs': {},
        'taxon_refs': {},
        'unresolved_taxon_ids': set(),
        'raw_metadata_values': [],
        'skipped_rows': [],
    }


def build_section_preview(*, batch_name, import_type, file_name, required_columns, valid_rows, errors, duplicates, total_rows):
    """Wrap a workbook section result in the same preview shape used by CSV imports."""
    return ImportPreview(
        batch_name=batch_name,
        import_type=import_type,
        required_columns=list(required_columns),
        file_name=file_name,
        total_rows=total_rows,
        valid_rows=valid_rows,
        errors=errors,
        duplicates=duplicates,
    ).to_dict()


def missing_columns_error(required_columns, fieldnames):
    """Return a formatted missing-columns message, or `None` when all are present."""
    missing_columns = [column for column in required_columns if column not in fieldnames]
    if not missing_columns:
        return None
    return f'Missing required columns: {", ".join(missing_columns)}'


def aggregate_workbook_issues(sections):
    """Flatten section-level errors and duplicates into workbook-level summaries."""
    aggregate_errors = []
    aggregate_duplicates = []
    for section in sections:
        for error in section['errors']:
            aggregate_errors.append(
                {
                    'section': section['import_type'],
                    'row_number': error['row_number'],
                    'message': error['message'],
                }
            )
        for duplicate in section['duplicates']:
            aggregate_duplicates.append(
                {
                    'section': section['import_type'],
                    'row_number': duplicate['row_number'],
                    'message': duplicate['message'],
                }
            )
    return aggregate_errors, aggregate_duplicates

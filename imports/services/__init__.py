"""Import service package.

Public entry points:
- `build_preview()` for preview/validation of CSV and workbook uploads
- `run_import()` for confirmed writes through `ImportBatch`

Internal layout:
- `constants.py`: supported import types and workbook-controlled values
- `helpers.py`: parsing, workbook loading, row cleaning, and object resolution
- `csv_preview.py`: CSV contract preview builders
- `workbook.py`: Excel workbook preview/import orchestration
- `runners.py`: database write runners
- `types.py`: preview dataclasses
"""

import csv
from io import StringIO

from django.db import transaction

from database.models import ImportBatch

from .constants import SUPPORTED_IMPORT_TYPES
from .csv_preview import PREVIEW_BUILDERS
from .runners import IMPORT_RUNNERS
from .workbook import build_workbook_preview, run_workbook_import


def build_preview(*, file_name, content, import_type, batch_name):
    """Build a preview payload for either a CSV contract file or the curator workbook."""
    if import_type not in SUPPORTED_IMPORT_TYPES:
        raise ValueError(f'Unsupported import type: {import_type}')

    if import_type == 'excel_workbook':
        return build_workbook_preview(
            file_name=file_name,
            content=content,
            batch_name=batch_name,
        )

    reader = csv.DictReader(StringIO(content))
    fieldnames = reader.fieldnames or []
    rows = list(reader)
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
    """Persist a previously confirmed preview payload and record the result in `ImportBatch`."""
    import_type = preview_data['import_type']
    if import_type == 'excel_workbook':
        return run_workbook_import(preview_data)

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

"""Workbook service façade.

This module keeps the stable workbook import entry points while delegating
preview construction and write execution to smaller modules.
"""

from .helpers import load_workbook_rows
from .types import WorkbookImportPreview
from .workbook_common import aggregate_workbook_issues, build_workbook_state
from .workbook_metadata import build_metadata_sections, collect_extra_metadata_rows
from .workbook_runners import WORKBOOK_IMPORT_RUNNERS, run_workbook_import as execute_workbook_import
from .workbook_sections import (
    build_comparison_section,
    build_diversity_sections,
    build_group_section,
    build_taxon_section,
    build_paper_section,
    build_qualitative_section,
    build_quantitative_section,
)


def build_workbook_preview(*, file_name, content, batch_name):
    """Parse the curator workbook and convert it into sectioned import previews."""
    sheets = load_workbook_rows(content)
    if 'paper' not in sheets:
        return WorkbookImportPreview(
            batch_name=batch_name,
            import_type='excel_workbook',
            required_columns=[],
            file_name=file_name,
            total_rows=0,
            valid_rows=[],
            errors=[{'section': 'paper', 'row_number': None, 'message': 'Workbook must include a "paper" sheet.'}],
            duplicates=[],
            sections=[],
            skipped_rows=[],
        )

    state = build_workbook_state()

    paper_section = build_paper_section(
        sheet=sheets.get('paper', {'fieldnames': [], 'rows': []}),
        batch_name=batch_name,
        file_name=file_name,
        state=state,
    )
    if paper_section is None:
        return WorkbookImportPreview(
            batch_name=batch_name,
            import_type='excel_workbook',
            required_columns=[],
            file_name=file_name,
            total_rows=0,
            valid_rows=[],
            errors=[{'section': 'paper', 'row_number': None, 'message': 'Workbook must include valid paper columns.'}],
            duplicates=[],
            sections=[],
            skipped_rows=[],
        )
    if paper_section.get('fatal_error'):
        return WorkbookImportPreview(
            batch_name=batch_name,
            import_type='excel_workbook',
            required_columns=[],
            file_name=file_name,
            total_rows=0,
            valid_rows=[],
            errors=[{'section': 'paper', 'row_number': None, 'message': paper_section['fatal_error']}],
            duplicates=[],
            sections=[],
            skipped_rows=[],
        )

    sections = [paper_section]
    sections.append(
        build_group_section(
            sheet=sheets.get('groups', {'fieldnames': [], 'rows': []}),
            batch_name=batch_name,
            file_name=file_name,
            state=state,
        )
    )
    sections.append(
        build_comparison_section(
            sheet=sheets.get('comparissons', {'fieldnames': [], 'rows': []}),
            batch_name=batch_name,
            file_name=file_name,
            state=state,
        )
    )
    sections.append(
        build_taxon_section(
            sheet=sheets.get('organisms', {'fieldnames': [], 'rows': []}),
            batch_name=batch_name,
            file_name=file_name,
            state=state,
        )
    )
    sections.append(
        build_qualitative_section(
            sheet=sheets.get('qualitative_findings', {'fieldnames': [], 'rows': []}),
            batch_name=batch_name,
            file_name=file_name,
            state=state,
        )
    )
    sections.append(
        build_quantitative_section(
            sheet=sheets.get('quantitative_findings', {'fieldnames': [], 'rows': []}),
            batch_name=batch_name,
            file_name=file_name,
            state=state,
        )
    )
    sections.extend(
        build_diversity_sections(
            sheet=sheets.get('diversity_metrics', {'fieldnames': [], 'rows': []}),
            batch_name=batch_name,
            file_name=file_name,
            state=state,
        )
    )
    extra_metadata_errors = collect_extra_metadata_rows(
        sheet=sheets.get('extra_metadata', {'fieldnames': [], 'rows': []}),
        state=state,
    )
    sections.extend(
        build_metadata_sections(
            batch_name=batch_name,
            file_name=file_name,
            state=state,
            extra_metadata_errors=extra_metadata_errors,
        )
    )

    aggregate_errors, aggregate_duplicates = aggregate_workbook_issues(sections)
    return WorkbookImportPreview(
        batch_name=batch_name,
        import_type='excel_workbook',
        required_columns=[],
        file_name=file_name,
        total_rows=sum(section['total_rows'] for section in sections),
        valid_rows=[],
        errors=aggregate_errors,
        duplicates=aggregate_duplicates,
        sections=sections,
        skipped_rows=state['skipped_rows'],
    )
def run_workbook_import(preview_data):
    """Persist a confirmed workbook preview by replaying each validated section runner."""
    return execute_workbook_import(preview_data, WORKBOOK_IMPORT_RUNNERS)

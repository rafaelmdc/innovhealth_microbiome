"""Workbook-specific preview and import orchestration."""

from django.db import transaction

from database.models import (
    AlphaMetric,
    BetaMetric,
    Comparison,
    Group,
    ImportBatch,
    MetadataValue,
    MetadataVariable,
    Organism,
    QualitativeFinding,
    QuantitativeFinding,
    Study,
)

from .constants import (
    COMPARISON_TYPE_ALLOWED_VALUES,
    GROUP_TYPE_ALLOWED_VALUES,
    PAPER_STATUS_ALLOWED_VALUES,
    WORKBOOK_DIRECTION_ALLOWED_VALUES,
    WORKBOOK_DIRECTION_MAP,
    WORKBOOK_DIVERSITY_ALLOWED_VALUES,
    WORKBOOK_FINDING_TYPE_ALLOWED_VALUES,
    WORKBOOK_METADATA_FIELD_DEFINITIONS,
    WORKBOOK_QUANTITATIVE_VALUE_TYPE_ALLOWED_VALUES,
)
from .helpers import (
    cleaned_row,
    combine_note_parts,
    labeled_note,
    load_workbook_rows,
    parse_float,
    parse_int,
    parse_optional_bool,
    parse_optional_int,
    resolve_comparison,
    resolve_group,
    resolve_organism,
    resolve_study,
)
from .types import ImportPreview, WorkbookImportPreview


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

    state = _build_workbook_state()

    paper_section = _build_paper_section(
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
        _build_group_section(
            sheet=sheets.get('groups', {'fieldnames': [], 'rows': []}),
            batch_name=batch_name,
            file_name=file_name,
            state=state,
        )
    )
    sections.append(
        _build_comparison_section(
            sheet=sheets.get('comparissons', {'fieldnames': [], 'rows': []}),
            batch_name=batch_name,
            file_name=file_name,
            state=state,
        )
    )
    sections.append(
        _build_organism_section(
            sheet=sheets.get('organisms', {'fieldnames': [], 'rows': []}),
            batch_name=batch_name,
            file_name=file_name,
            state=state,
        )
    )
    sections.append(
        _build_qualitative_section(
            sheet=sheets.get('qualitative_findings', {'fieldnames': [], 'rows': []}),
            batch_name=batch_name,
            file_name=file_name,
            state=state,
        )
    )
    sections.append(
        _build_quantitative_section(
            sheet=sheets.get('quantitative_findings', {'fieldnames': [], 'rows': []}),
            batch_name=batch_name,
            file_name=file_name,
            state=state,
        )
    )
    sections.extend(
        _build_diversity_sections(
            sheet=sheets.get('diversity_metrics', {'fieldnames': [], 'rows': []}),
            batch_name=batch_name,
            file_name=file_name,
            state=state,
        )
    )
    extra_metadata_errors = _collect_extra_metadata_rows(
        sheet=sheets.get('extra_metadata', {'fieldnames': [], 'rows': []}),
        state=state,
    )
    sections.extend(
        _build_metadata_sections(
            batch_name=batch_name,
            file_name=file_name,
            state=state,
            extra_metadata_errors=extra_metadata_errors,
        )
    )

    aggregate_errors, aggregate_duplicates = _aggregate_workbook_issues(sections)
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


def _build_workbook_state():
    """Return the mutable state shared across workbook sheet handlers."""
    return {
        'paper_status_by_id': {},
        'complete_paper_refs': {},
        'group_refs': {},
        'comparison_refs': {},
        'organism_refs': {},
        'raw_metadata_values': [],
        'skipped_rows': [],
    }


def _build_section_preview(*, batch_name, import_type, file_name, required_columns, valid_rows, errors, duplicates, total_rows):
    """Wrap a section result in the same preview shape used by CSV imports."""
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


def _missing_columns_error(required_columns, fieldnames):
    """Return a formatted missing-columns message, or `None` when all are present."""
    missing_columns = [column for column in required_columns if column not in fieldnames]
    if not missing_columns:
        return None
    return f'Missing required columns: {", ".join(missing_columns)}'


def _build_paper_section(*, sheet, batch_name, file_name, state):
    """Build the study preview section and seed workbook-level paper references."""
    required_columns = ('paper_id', 'title', 'status')
    fatal_error = _missing_columns_error(required_columns, sheet['fieldnames'])
    if fatal_error:
        return {'fatal_error': fatal_error}

    existing_study_dois = set(Study.objects.exclude(doi__isnull=True).exclude(doi='').values_list('doi', flat=True))
    existing_study_titles = {title.lower() for title in Study.objects.values_list('title', flat=True)}
    seen_study_keys = set()
    paper_ids_seen = set()
    valid_rows = []
    errors = []
    duplicates = []

    for row in sheet['rows']:
        row_number = row['row_number']
        data = cleaned_row(row['data'])
        paper_id = data.get('paper_id', '')
        title = data.get('title', '')
        status = data.get('status', '').lower()

        if not paper_id:
            errors.append({'row_number': row_number, 'message': 'paper_id is required.'})
            continue
        if paper_id in paper_ids_seen:
            errors.append({'row_number': row_number, 'message': 'Duplicate paper_id in workbook.'})
            continue
        paper_ids_seen.add(paper_id)
        state['paper_status_by_id'][paper_id] = status

        if not title:
            errors.append({'row_number': row_number, 'message': 'title is required.'})
            continue
        if status not in PAPER_STATUS_ALLOWED_VALUES:
            errors.append(
                {
                    'row_number': row_number,
                    'message': 'status must be one of: todo, in_progress, complete, needs_review.',
                }
            )
            continue
        if status != 'complete':
            state['skipped_rows'].append(
                {
                    'section': 'paper',
                    'row_number': row_number,
                    'message': f'Skipped because paper.status is "{status}".',
                }
            )
            continue

        year, year_error = parse_optional_int(data.get('year', ''), 'year')
        if year_error:
            errors.append({'row_number': row_number, 'message': year_error})
            continue

        doi = data.get('doi', '')
        study_key = ('doi', doi) if doi else ('title', title.lower())
        state['complete_paper_refs'][paper_id] = {
            'study_doi': doi,
            'study_title': title,
        }

        notes = combine_note_parts(
            data.get('notes', ''),
            labeled_note('Authors', data.get('authors', '')),
            labeled_note('Topic', data.get('topic', '')),
            labeled_note('Reviewer', data.get('reviwer', '')),
        )

        if study_key in seen_study_keys:
            duplicates.append({'row_number': row_number, 'message': 'Duplicate study in workbook.'})
            continue
        if (doi and doi in existing_study_dois) or (not doi and title.lower() in existing_study_titles):
            duplicates.append({'row_number': row_number, 'message': 'Study already exists.'})
            continue

        seen_study_keys.add(study_key)
        valid_rows.append(
            {
                'row_number': row_number,
                'doi': doi or None,
                'title': title,
                'country': data.get('country', ''),
                'journal': '',
                'year': year,
                'notes': notes,
            }
        )

    return _build_section_preview(
        batch_name=batch_name,
        import_type='study',
        file_name=file_name,
        required_columns=required_columns,
        valid_rows=valid_rows,
        errors=errors,
        duplicates=duplicates,
        total_rows=len(sheet['rows']),
    )


def _build_group_section(*, sheet, batch_name, file_name, state):
    """Build the group preview section and collect group-linked raw metadata rows."""
    required_columns = ('group_id', 'paper_id', 'group_name_as_written')
    valid_rows = []
    errors = []
    duplicates = []
    group_ids_seen = set()
    seen_group_keys = set()
    existing_group_keys = set(Group.objects.values_list('study_id', 'name'))

    missing_columns_error = _missing_columns_error(required_columns, sheet['fieldnames'])
    if missing_columns_error and sheet['rows']:
        errors.append({'row_number': None, 'message': missing_columns_error})
    else:
        for row in sheet['rows']:
            row_number = row['row_number']
            data = cleaned_row(row['data'])
            paper_id = data.get('paper_id', '')
            group_id = data.get('group_id', '')

            if not group_id:
                errors.append({'row_number': row_number, 'message': 'group_id is required.'})
                continue
            if group_id in group_ids_seen:
                errors.append({'row_number': row_number, 'message': 'Duplicate group_id in workbook.'})
                continue
            group_ids_seen.add(group_id)

            if paper_id not in state['paper_status_by_id']:
                errors.append({'row_number': row_number, 'message': 'paper_id does not exist in the paper sheet.'})
                continue
            if state['paper_status_by_id'][paper_id] != 'complete':
                state['skipped_rows'].append(
                    {
                        'section': 'groups',
                        'row_number': row_number,
                        'message': f'Skipped because paper {paper_id} is not complete.',
                    }
                )
                continue

            paper_ref = state['complete_paper_refs'].get(paper_id)
            if not paper_ref:
                errors.append({'row_number': row_number, 'message': 'paper_id does not resolve to a valid complete paper.'})
                continue

            group_name = data.get('group_name_as_written', '')
            if not group_name:
                errors.append({'row_number': row_number, 'message': 'group_name_as_written is required.'})
                continue

            group_type = data.get('group_type', '')
            if group_type and group_type not in GROUP_TYPE_ALLOWED_VALUES:
                errors.append(
                    {
                        'row_number': row_number,
                        'message': 'group_type must be one of: case, control, subtype, treatment, follow_up, responder, non_responder, other.',
                    }
                )
                continue

            sample_size, sample_size_error = parse_optional_int(data.get('sample_size', ''), 'sample_size')
            if sample_size_error:
                errors.append({'row_number': row_number, 'message': sample_size_error})
                continue

            existing_group = resolve_group(
                paper_ref['study_doi'],
                paper_ref['study_title'],
                group_name,
            )
            group_key = (
                paper_ref['study_doi'],
                paper_ref['study_title'],
                group_name,
            )
            state['group_refs'][group_id] = {
                'study_doi': paper_ref['study_doi'],
                'study_title': paper_ref['study_title'],
                'group_name': group_name,
            }

            notes = combine_note_parts(
                data.get('notes', ''),
                labeled_note('Where found', data.get('where_found', '')),
            )

            if group_key in seen_group_keys:
                duplicates.append({'row_number': row_number, 'message': 'Duplicate group in workbook.'})
                continue
            if existing_group and (existing_group.study_id, existing_group.name) in existing_group_keys:
                duplicates.append({'row_number': row_number, 'message': 'Group already exists.'})
                continue

            seen_group_keys.add(group_key)
            valid_rows.append(
                {
                    'row_number': row_number,
                    'study_doi': paper_ref['study_doi'],
                    'study_title': paper_ref['study_title'],
                    'name': group_name,
                    'condition': data.get('condition', ''),
                    'sample_size': sample_size,
                    'cohort': '',
                    'site': data.get('body_site', ''),
                    'notes': notes,
                }
            )

            _collect_group_metadata_rows(
                row_number=row_number,
                paper_ref=paper_ref,
                group_name=group_name,
                data=data,
                state=state,
            )

    return _build_section_preview(
        batch_name=batch_name,
        import_type='group',
        file_name=file_name,
        required_columns=required_columns,
        valid_rows=valid_rows,
        errors=errors,
        duplicates=duplicates,
        total_rows=len(sheet['rows']),
    )


def _collect_group_metadata_rows(*, row_number, paper_ref, group_name, data, state):
    """Extract predefined group-side workbook fields into raw metadata rows."""
    for metadata_name in ('group_type', 'age', 'women_percent', 'age2'):
        raw_value = data.get(metadata_name, '')
        if not raw_value:
            continue
        definition = WORKBOOK_METADATA_FIELD_DEFINITIONS[metadata_name]
        state['raw_metadata_values'].append(
            {
                'row_number': row_number,
                'study_doi': paper_ref['study_doi'],
                'study_title': paper_ref['study_title'],
                'group_name': group_name,
                'variable_name': metadata_name,
                'display_name': definition['display_name'],
                'preferred_value_type': definition['value_type'],
                'raw_value': raw_value,
            }
        )


def _build_comparison_section(*, sheet, batch_name, file_name, state):
    """Build the comparison preview section and seed workbook comparison references."""
    required_columns = ('comparison_id', 'paper_id', 'target_group_id', 'reference_group_id')
    valid_rows = []
    errors = []
    duplicates = []
    comparison_ids_seen = set()
    seen_comparison_keys = set()
    existing_comparison_keys = set(
        Comparison.objects.values_list('study_id', 'group_a_id', 'group_b_id', 'label')
    )

    missing_columns_error = _missing_columns_error(required_columns, sheet['fieldnames'])
    if missing_columns_error and sheet['rows']:
        errors.append({'row_number': None, 'message': missing_columns_error})
    else:
        for row in sheet['rows']:
            row_number = row['row_number']
            data = cleaned_row(row['data'])
            comparison_id = data.get('comparison_id', '')
            paper_id = data.get('paper_id', '')

            if not comparison_id:
                errors.append({'row_number': row_number, 'message': 'comparison_id is required.'})
                continue
            if comparison_id in comparison_ids_seen:
                errors.append({'row_number': row_number, 'message': 'Duplicate comparison_id in workbook.'})
                continue
            comparison_ids_seen.add(comparison_id)

            if paper_id not in state['paper_status_by_id']:
                errors.append({'row_number': row_number, 'message': 'paper_id does not exist in the paper sheet.'})
                continue
            if state['paper_status_by_id'][paper_id] != 'complete':
                state['skipped_rows'].append(
                    {
                        'section': 'comparissons',
                        'row_number': row_number,
                        'message': f'Skipped because paper {paper_id} is not complete.',
                    }
                )
                continue

            paper_ref = state['complete_paper_refs'].get(paper_id)
            if not paper_ref:
                errors.append({'row_number': row_number, 'message': 'paper_id does not resolve to a valid complete paper.'})
                continue

            target_group = state['group_refs'].get(data.get('target_group_id', ''))
            reference_group = state['group_refs'].get(data.get('reference_group_id', ''))
            if not target_group or not reference_group:
                errors.append({'row_number': row_number, 'message': 'target_group_id and reference_group_id must resolve to groups.'})
                continue
            if target_group['group_name'] == reference_group['group_name']:
                errors.append({'row_number': row_number, 'message': 'Comparison groups must be different.'})
                continue

            comparison_type = data.get('comparison_type', '')
            if comparison_type and comparison_type not in COMPARISON_TYPE_ALLOWED_VALUES:
                errors.append(
                    {
                        'row_number': row_number,
                        'message': 'comparison_type must be one of: case_vs_control, severity_vs_mild, responder_vs_non_responder, subtype_vs_subtype, treatment_vs_baseline, other.',
                    }
                )
                continue

            label = f"{target_group['group_name']} vs {reference_group['group_name']}"
            if comparison_type:
                label = f'{label} ({comparison_type})'

            state['comparison_refs'][comparison_id] = {
                'study_doi': paper_ref['study_doi'],
                'study_title': paper_ref['study_title'],
                'group_a_name': target_group['group_name'],
                'group_b_name': reference_group['group_name'],
                'comparison_label': label,
            }

            existing_comparison = resolve_comparison(
                paper_ref['study_doi'],
                paper_ref['study_title'],
                target_group['group_name'],
                reference_group['group_name'],
                label,
            )
            comparison_key = (
                paper_ref['study_doi'],
                paper_ref['study_title'],
                target_group['group_name'],
                reference_group['group_name'],
                label,
            )
            notes = combine_note_parts(
                data.get('notes', ''),
                labeled_note('Comparison type', comparison_type),
                labeled_note('Target condition', data.get('target_condition', '')),
                labeled_note('Reference condition', data.get('reference_condition', '')),
            )

            if comparison_key in seen_comparison_keys:
                duplicates.append({'row_number': row_number, 'message': 'Duplicate comparison in workbook.'})
                continue
            if existing_comparison and (
                existing_comparison.study_id,
                existing_comparison.group_a_id,
                existing_comparison.group_b_id,
                existing_comparison.label,
            ) in existing_comparison_keys:
                duplicates.append({'row_number': row_number, 'message': 'Comparison already exists.'})
                continue

            seen_comparison_keys.add(comparison_key)
            valid_rows.append(
                {
                    'row_number': row_number,
                    'study_doi': paper_ref['study_doi'],
                    'study_title': paper_ref['study_title'],
                    'group_a_name': target_group['group_name'],
                    'group_b_name': reference_group['group_name'],
                    'label': label,
                    'notes': notes,
                }
            )

    return _build_section_preview(
        batch_name=batch_name,
        import_type='comparison',
        file_name=file_name,
        required_columns=required_columns,
        valid_rows=valid_rows,
        errors=errors,
        duplicates=duplicates,
        total_rows=len(sheet['rows']),
    )


def _build_organism_section(*, sheet, batch_name, file_name, state):
    """Build the organism preview section and seed workbook organism references."""
    required_columns = ('organism_id', 'organism_as_written')
    valid_rows = []
    errors = []
    duplicates = []
    organism_ids_seen = set()
    seen_organism_names = set()
    seen_organism_taxonomy_ids = set()
    existing_taxonomy_ids = set(
        Organism.objects.exclude(ncbi_taxonomy_id__isnull=True).values_list('ncbi_taxonomy_id', flat=True)
    )
    existing_organism_names = {name.lower() for name in Organism.objects.values_list('scientific_name', flat=True)}

    missing_columns_error = _missing_columns_error(required_columns, sheet['fieldnames'])
    if missing_columns_error and sheet['rows']:
        errors.append({'row_number': None, 'message': missing_columns_error})
    else:
        for row in sheet['rows']:
            row_number = row['row_number']
            data = cleaned_row(row['data'])
            organism_id = data.get('organism_id', '')

            if not organism_id:
                errors.append({'row_number': row_number, 'message': 'organism_id is required.'})
                continue
            if organism_id in organism_ids_seen:
                errors.append({'row_number': row_number, 'message': 'Duplicate organism_id in workbook.'})
                continue
            organism_ids_seen.add(organism_id)

            scientific_name = data.get('organism_as_written', '')
            if not scientific_name:
                errors.append({'row_number': row_number, 'message': 'organism_as_written is required.'})
                continue

            ncbi_taxonomy_id, taxonomy_error = parse_optional_int(data.get('ncbi_id', ''), 'ncbi_id')
            if taxonomy_error:
                errors.append({'row_number': row_number, 'message': taxonomy_error})
                continue

            state['organism_refs'][organism_id] = {
                'scientific_name': scientific_name,
                'ncbi_taxonomy_id': ncbi_taxonomy_id,
            }

            notes = combine_note_parts(
                data.get('notes', ''),
                labeled_note('Suggested clean name', data.get('suggested_clean_name', '')),
                labeled_note('Resolved', data.get('resolved', '')),
            )

            duplicate_name_key = scientific_name.lower()
            if ncbi_taxonomy_id is not None:
                if ncbi_taxonomy_id in seen_organism_taxonomy_ids:
                    duplicates.append({'row_number': row_number, 'message': 'Duplicate ncbi_id in workbook.'})
                    continue
                if ncbi_taxonomy_id in existing_taxonomy_ids:
                    duplicates.append({'row_number': row_number, 'message': 'Organism already exists for this ncbi_id.'})
                    continue
                seen_organism_taxonomy_ids.add(ncbi_taxonomy_id)
            elif duplicate_name_key in seen_organism_names:
                duplicates.append({'row_number': row_number, 'message': 'Duplicate organism name in workbook.'})
                continue
            elif duplicate_name_key in existing_organism_names:
                duplicates.append({'row_number': row_number, 'message': 'Organism already exists.'})
                continue

            seen_organism_names.add(duplicate_name_key)
            valid_rows.append(
                {
                    'row_number': row_number,
                    'ncbi_taxonomy_id': ncbi_taxonomy_id,
                    'scientific_name': scientific_name,
                    'rank': data.get('rank_if_known', ''),
                    'notes': notes,
                }
            )

    return _build_section_preview(
        batch_name=batch_name,
        import_type='organism',
        file_name=file_name,
        required_columns=required_columns,
        valid_rows=valid_rows,
        errors=errors,
        duplicates=duplicates,
        total_rows=len(sheet['rows']),
    )


def _build_qualitative_section(*, sheet, batch_name, file_name, state):
    """Build the qualitative finding preview section from workbook comparison direction rows."""
    required_columns = ('paper_id', 'comparison_id', 'organism_id', 'direction')
    valid_rows = []
    errors = []
    duplicates = []
    seen_qualitative_keys = set()
    existing_qualitative_keys = set(
        QualitativeFinding.objects.values_list('comparison_id', 'organism_id', 'direction', 'source')
    )

    missing_columns_error = _missing_columns_error(required_columns, sheet['fieldnames'])
    if missing_columns_error and sheet['rows']:
        errors.append({'row_number': None, 'message': missing_columns_error})
    else:
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
                        'section': 'qualitative_findings',
                        'row_number': row_number,
                        'message': f'Skipped because paper {paper_id} is not complete.',
                    }
                )
                continue

            comparison_ref = state['comparison_refs'].get(data.get('comparison_id', ''))
            if not comparison_ref:
                errors.append({'row_number': row_number, 'message': 'comparison_id does not resolve to a valid comparison.'})
                continue

            organism_ref = state['organism_refs'].get(data.get('organism_id', ''))
            if not organism_ref:
                errors.append({'row_number': row_number, 'message': 'organism_id does not resolve to a valid organism.'})
                continue

            direction = data.get('direction', '')
            if direction not in WORKBOOK_DIRECTION_ALLOWED_VALUES:
                errors.append(
                    {
                        'row_number': row_number,
                        'message': 'direction must be one of: increased_in_target, decreased_in_target.',
                    }
                )
                continue

            finding_type = data.get('finding_type', '')
            if finding_type and finding_type not in WORKBOOK_FINDING_TYPE_ALLOWED_VALUES:
                errors.append({'row_number': row_number, 'message': 'finding_type must be relative_direction.'})
                continue

            existing_comparison = resolve_comparison(
                comparison_ref['study_doi'],
                comparison_ref['study_title'],
                comparison_ref['group_a_name'],
                comparison_ref['group_b_name'],
                comparison_ref['comparison_label'],
            )
            existing_organism = resolve_organism(
                organism_ref['scientific_name'],
                organism_ref['ncbi_taxonomy_id'],
            )
            duplicate_key = (
                comparison_ref['study_doi'],
                comparison_ref['study_title'],
                comparison_ref['group_a_name'],
                comparison_ref['group_b_name'],
                comparison_ref['comparison_label'],
                organism_ref['scientific_name'],
                WORKBOOK_DIRECTION_MAP[direction],
                data.get('where_found', ''),
            )
            if duplicate_key in seen_qualitative_keys:
                duplicates.append({'row_number': row_number, 'message': 'Duplicate qualitative finding in workbook.'})
                continue
            if existing_comparison and existing_organism and (
                existing_comparison.pk,
                existing_organism.pk,
                WORKBOOK_DIRECTION_MAP[direction],
                data.get('where_found', ''),
            ) in existing_qualitative_keys:
                duplicates.append({'row_number': row_number, 'message': 'Qualitative finding already exists.'})
                continue

            seen_qualitative_keys.add(duplicate_key)
            valid_rows.append(
                {
                    'row_number': row_number,
                    'study_doi': comparison_ref['study_doi'],
                    'study_title': comparison_ref['study_title'],
                    'group_a_name': comparison_ref['group_a_name'],
                    'group_b_name': comparison_ref['group_b_name'],
                    'comparison_label': comparison_ref['comparison_label'],
                    'organism_scientific_name': organism_ref['scientific_name'],
                    'organism_ncbi_taxonomy_id': organism_ref['ncbi_taxonomy_id'],
                    'direction': WORKBOOK_DIRECTION_MAP[direction],
                    'source': data.get('where_found', ''),
                    'notes': combine_note_parts(
                        data.get('notes', ''),
                        labeled_note('Finding type', finding_type),
                        labeled_note('Organism as written', data.get('organism_as_writiten', '')),
                    ),
                }
            )

    return _build_section_preview(
        batch_name=batch_name,
        import_type='qualitative_finding',
        file_name=file_name,
        required_columns=required_columns,
        valid_rows=valid_rows,
        errors=errors,
        duplicates=duplicates,
        total_rows=len(sheet['rows']),
    )


def _build_quantitative_section(*, sheet, batch_name, file_name, state):
    """Build the quantitative finding preview section from workbook numeric rows."""
    required_columns = ('paper_id', 'group_id', 'organism_id', 'value_type', 'value')
    valid_rows = []
    errors = []
    duplicates = []
    seen_quantitative_keys = set()
    existing_quantitative_keys = set(
        QuantitativeFinding.objects.values_list('group_id', 'organism_id', 'value_type', 'source')
    )

    missing_columns_error = _missing_columns_error(required_columns, sheet['fieldnames'])
    if missing_columns_error and sheet['rows']:
        errors.append({'row_number': None, 'message': missing_columns_error})
    else:
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
                        'section': 'quantitative_findings',
                        'row_number': row_number,
                        'message': f'Skipped because paper {paper_id} is not complete.',
                    }
                )
                continue

            group_ref = state['group_refs'].get(data.get('group_id', ''))
            if not group_ref:
                errors.append({'row_number': row_number, 'message': 'group_id does not resolve to a valid group.'})
                continue

            organism_ref = state['organism_refs'].get(data.get('organism_id', ''))
            if not organism_ref:
                errors.append({'row_number': row_number, 'message': 'organism_id does not resolve to a valid organism.'})
                continue

            value_type = data.get('value_type', '')
            if value_type not in WORKBOOK_QUANTITATIVE_VALUE_TYPE_ALLOWED_VALUES:
                errors.append({'row_number': row_number, 'message': 'value_type must be relative_abundance.'})
                continue

            value, value_error = parse_float(data.get('value', ''), 'value')
            if value_error:
                errors.append({'row_number': row_number, 'message': value_error})
                continue

            existing_group = resolve_group(
                group_ref['study_doi'],
                group_ref['study_title'],
                group_ref['group_name'],
            )
            existing_organism = resolve_organism(
                organism_ref['scientific_name'],
                organism_ref['ncbi_taxonomy_id'],
            )
            duplicate_key = (
                group_ref['study_doi'],
                group_ref['study_title'],
                group_ref['group_name'],
                organism_ref['scientific_name'],
                value_type,
                data.get('where_found', ''),
            )
            if duplicate_key in seen_quantitative_keys:
                duplicates.append({'row_number': row_number, 'message': 'Duplicate quantitative finding in workbook.'})
                continue
            if existing_group and existing_organism and (
                existing_group.pk,
                existing_organism.pk,
                value_type,
                data.get('where_found', ''),
            ) in existing_quantitative_keys:
                duplicates.append({'row_number': row_number, 'message': 'Quantitative finding already exists.'})
                continue

            seen_quantitative_keys.add(duplicate_key)
            valid_rows.append(
                {
                    'row_number': row_number,
                    'study_doi': group_ref['study_doi'],
                    'study_title': group_ref['study_title'],
                    'group_name': group_ref['group_name'],
                    'organism_scientific_name': organism_ref['scientific_name'],
                    'organism_ncbi_taxonomy_id': organism_ref['ncbi_taxonomy_id'],
                    'value_type': value_type,
                    'value': value,
                    'unit': data.get('unit', ''),
                    'source': data.get('where_found', ''),
                    'notes': data.get('notes', ''),
                }
            )

    return _build_section_preview(
        batch_name=batch_name,
        import_type='quantitative_finding',
        file_name=file_name,
        required_columns=required_columns,
        valid_rows=valid_rows,
        errors=errors,
        duplicates=duplicates,
        total_rows=len(sheet['rows']),
    )


def _build_diversity_sections(*, sheet, batch_name, file_name, state):
    """Build alpha and beta metric preview sections from the diversity sheet."""
    required_columns = ('paper_id', 'diversity_category', 'metric_as_written', 'value')
    alpha_valid_rows = []
    alpha_errors = []
    alpha_duplicates = []
    beta_valid_rows = []
    beta_errors = []
    beta_duplicates = []
    seen_alpha_keys = set()
    seen_beta_keys = set()
    existing_alpha_keys = set(AlphaMetric.objects.values_list('group_id', 'metric', 'source'))
    existing_beta_keys = set(BetaMetric.objects.values_list('comparison_id', 'metric', 'source'))

    missing_columns_error = _missing_columns_error(required_columns, sheet['fieldnames'])
    if missing_columns_error and sheet['rows']:
        alpha_errors.append({'row_number': None, 'message': missing_columns_error})
    else:
        for row in sheet['rows']:
            row_number = row['row_number']
            data = cleaned_row(row['data'])
            paper_id = data.get('paper_id', '')

            if paper_id not in state['paper_status_by_id']:
                alpha_errors.append({'row_number': row_number, 'message': 'paper_id does not exist in the paper sheet.'})
                continue
            if state['paper_status_by_id'][paper_id] != 'complete':
                state['skipped_rows'].append(
                    {
                        'section': 'diversity_metrics',
                        'row_number': row_number,
                        'message': f'Skipped because paper {paper_id} is not complete.',
                    }
                )
                continue

            category = data.get('diversity_category', '')
            if category not in WORKBOOK_DIVERSITY_ALLOWED_VALUES:
                alpha_errors.append({'row_number': row_number, 'message': 'diversity_category must be alpha or beta.'})
                continue

            value, value_error = parse_float(data.get('value', ''), 'value')
            if value_error:
                alpha_errors.append({'row_number': row_number, 'message': value_error})
                continue

            metric = data.get('metric_as_written', '')
            if not metric:
                alpha_errors.append({'row_number': row_number, 'message': 'metric_as_written is required.'})
                continue

            source = data.get('where_found', '')
            notes = data.get('notes', '')

            if category == 'alpha':
                _handle_alpha_diversity_row(
                    row_number=row_number,
                    data=data,
                    metric=metric,
                    value=value,
                    source=source,
                    notes=notes,
                    state=state,
                    valid_rows=alpha_valid_rows,
                    errors=alpha_errors,
                    duplicates=alpha_duplicates,
                    seen_keys=seen_alpha_keys,
                    existing_keys=existing_alpha_keys,
                )
                continue

            _handle_beta_diversity_row(
                row_number=row_number,
                data=data,
                metric=metric,
                value=value,
                source=source,
                notes=notes,
                state=state,
                valid_rows=beta_valid_rows,
                errors=beta_errors,
                duplicates=beta_duplicates,
                seen_keys=seen_beta_keys,
                existing_keys=existing_beta_keys,
            )

    alpha_section = _build_section_preview(
        batch_name=batch_name,
        import_type='alpha_metric',
        file_name=file_name,
        required_columns=required_columns,
        valid_rows=alpha_valid_rows,
        errors=alpha_errors,
        duplicates=alpha_duplicates,
        total_rows=len(alpha_valid_rows) + len(alpha_errors) + len(alpha_duplicates),
    )
    beta_section = _build_section_preview(
        batch_name=batch_name,
        import_type='beta_metric',
        file_name=file_name,
        required_columns=required_columns,
        valid_rows=beta_valid_rows,
        errors=beta_errors,
        duplicates=beta_duplicates,
        total_rows=len(beta_valid_rows) + len(beta_errors) + len(beta_duplicates),
    )
    return [alpha_section, beta_section]


def _handle_alpha_diversity_row(*, row_number, data, metric, value, source, notes, state, valid_rows, errors, duplicates, seen_keys, existing_keys):
    """Validate and append a single alpha diversity row to the preview payload."""
    group_ref = state['group_refs'].get(data.get('group_id', ''))
    if not group_ref:
        errors.append({'row_number': row_number, 'message': 'Alpha diversity rows require a valid group_id.'})
        return

    existing_group = resolve_group(
        group_ref['study_doi'],
        group_ref['study_title'],
        group_ref['group_name'],
    )
    duplicate_key = (
        group_ref['study_doi'],
        group_ref['study_title'],
        group_ref['group_name'],
        metric,
        source,
    )
    if duplicate_key in seen_keys:
        duplicates.append({'row_number': row_number, 'message': 'Duplicate alpha metric in workbook.'})
        return
    if existing_group and (existing_group.pk, metric, source) in existing_keys:
        duplicates.append({'row_number': row_number, 'message': 'Alpha metric already exists.'})
        return

    seen_keys.add(duplicate_key)
    valid_rows.append(
        {
            'row_number': row_number,
            'study_doi': group_ref['study_doi'],
            'study_title': group_ref['study_title'],
            'group_name': group_ref['group_name'],
            'metric': metric,
            'value': value,
            'source': source,
            'notes': notes,
        }
    )


def _handle_beta_diversity_row(*, row_number, data, metric, value, source, notes, state, valid_rows, errors, duplicates, seen_keys, existing_keys):
    """Validate and append a single beta diversity row to the preview payload."""
    comparison_ref = state['comparison_refs'].get(data.get('comparison_id', ''))
    if not comparison_ref:
        errors.append({'row_number': row_number, 'message': 'Beta diversity rows require a valid comparison_id.'})
        return

    existing_comparison = resolve_comparison(
        comparison_ref['study_doi'],
        comparison_ref['study_title'],
        comparison_ref['group_a_name'],
        comparison_ref['group_b_name'],
        comparison_ref['comparison_label'],
    )
    duplicate_key = (
        comparison_ref['study_doi'],
        comparison_ref['study_title'],
        comparison_ref['group_a_name'],
        comparison_ref['group_b_name'],
        comparison_ref['comparison_label'],
        metric,
        source,
    )
    if duplicate_key in seen_keys:
        duplicates.append({'row_number': row_number, 'message': 'Duplicate beta metric in workbook.'})
        return
    if existing_comparison and (existing_comparison.pk, metric, source) in existing_keys:
        duplicates.append({'row_number': row_number, 'message': 'Beta metric already exists.'})
        return

    seen_keys.add(duplicate_key)
    valid_rows.append(
        {
            'row_number': row_number,
            'study_doi': comparison_ref['study_doi'],
            'study_title': comparison_ref['study_title'],
            'group_a_name': comparison_ref['group_a_name'],
            'group_b_name': comparison_ref['group_b_name'],
            'comparison_label': comparison_ref['comparison_label'],
            'metric': metric,
            'value': value,
            'source': source,
            'notes': notes,
        }
    )


def _collect_extra_metadata_rows(*, sheet, state):
    """Collect free-form extra metadata rows into the raw metadata staging list."""
    required_columns = ('paper_id', 'group_id', 'field_name', 'value_as_written')
    errors = []

    missing_columns_error = _missing_columns_error(required_columns, sheet['fieldnames'])
    if missing_columns_error and sheet['rows']:
        errors.append({'row_number': None, 'message': missing_columns_error})
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


def _build_metadata_sections(*, batch_name, file_name, state, extra_metadata_errors):
    """Build metadata variable and metadata value sections from staged raw metadata rows."""
    required_columns = ('paper_id', 'group_id', 'field_name', 'value_as_written')
    existing_variables = {variable.name: variable for variable in MetadataVariable.objects.all()}
    metadata_variable_valid_rows = []
    metadata_variable_duplicates = []
    planned_variable_names = set()
    metadata_variable_types = {}

    for metadata_row in state['raw_metadata_values']:
        variable_name = metadata_row['variable_name']
        if variable_name in metadata_variable_types:
            continue
        existing_variable = existing_variables.get(variable_name)
        if existing_variable:
            metadata_variable_types[variable_name] = existing_variable.value_type
            metadata_variable_duplicates.append(
                {
                    'row_number': metadata_row['row_number'],
                    'message': f'Metadata variable "{variable_name}" already exists.',
                }
            )
            continue

        metadata_variable_types[variable_name] = metadata_row['preferred_value_type']
        if variable_name in planned_variable_names:
            continue
        planned_variable_names.add(variable_name)
        metadata_variable_valid_rows.append(
            {
                'row_number': metadata_row['row_number'],
                'name': variable_name,
                'display_name': metadata_row['display_name'],
                'value_type': metadata_row['preferred_value_type'],
                'is_filterable': False,
            }
        )

    metadata_variable_section = _build_section_preview(
        batch_name=batch_name,
        import_type='metadata_variable',
        file_name=file_name,
        required_columns=required_columns,
        valid_rows=metadata_variable_valid_rows,
        errors=extra_metadata_errors,
        duplicates=metadata_variable_duplicates,
        total_rows=len(metadata_variable_valid_rows) + len(metadata_variable_duplicates),
    )

    metadata_value_valid_rows = []
    metadata_value_errors = []
    metadata_value_duplicates = []
    seen_metadata_value_keys = set()
    existing_metadata_value_keys = set()
    for metadata_value in MetadataValue.objects.select_related('group', 'variable', 'group__study'):
        existing_metadata_value_keys.add(
            (
                metadata_value.group.study.doi or '',
                metadata_value.group.study.title,
                metadata_value.group.name,
                metadata_value.variable.name,
            )
        )

    for metadata_row in state['raw_metadata_values']:
        variable_type = metadata_variable_types.get(
            metadata_row['variable_name'],
            metadata_row['preferred_value_type'],
        )
        typed_values, value_error = _build_metadata_typed_values(
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
        if duplicate_key in existing_metadata_value_keys:
            metadata_value_duplicates.append(
                {
                    'row_number': metadata_row['row_number'],
                    'message': 'Metadata value already exists for this group and variable.',
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

    metadata_value_section = _build_section_preview(
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


def _build_metadata_typed_values(*, variable_name, variable_type, raw_value):
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


def _aggregate_workbook_issues(sections):
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


@transaction.atomic
def run_workbook_import(preview_data):
    """Persist a confirmed workbook preview by replaying each validated section runner."""
    batch = ImportBatch.objects.create(
        name=preview_data['batch_name'],
        import_type='excel_workbook',
        status=ImportBatch.Status.VALIDATED,
        source_file=preview_data.get('file_name', ''),
    )

    created_count = 0
    section_counts = {}
    for section in preview_data.get('sections', []):
        import_type = section['import_type']
        runner = WORKBOOK_IMPORT_RUNNERS.get(import_type)
        if not runner:
            continue
        section_created_count = runner(section.get('valid_rows', []), batch)
        section_counts[import_type] = section_created_count
        created_count += section_created_count

    duplicate_count = len(preview_data.get('duplicates', []))
    error_count = len(preview_data.get('errors', []))
    skipped_count = len(preview_data.get('skipped_rows', []))
    batch.success_count = created_count
    batch.error_count = duplicate_count + error_count
    batch.status = ImportBatch.Status.COMPLETED if error_count == 0 else ImportBatch.Status.FAILED
    section_summary = ', '.join(
        f'{import_type}: {count}'
        for import_type, count in section_counts.items()
        if count
    )
    batch.notes = (
        f'Imported {created_count} rows from Excel workbook. '
        f'Skipped {duplicate_count} duplicates. '
        f'Skipped {skipped_count} incomplete-paper rows. '
        f'Validation errors: {error_count}.'
    )
    if section_summary:
        batch.notes = f'{batch.notes} Created by section: {section_summary}.'
    batch.save(update_fields=['success_count', 'error_count', 'status', 'notes'])
    return batch


def run_workbook_study_import(valid_rows, batch):
    """Create missing studies from workbook preview rows."""
    created_count = 0
    for row in valid_rows:
        study = resolve_study(row.get('doi') or '', row['title'])
        if study:
            continue
        Study.objects.create(
            doi=row['doi'],
            title=row['title'],
            country=row['country'],
            journal=row['journal'],
            year=row['year'],
            notes=row['notes'],
        )
        created_count += 1
    return created_count


def run_workbook_group_import(valid_rows, batch):
    """Create missing groups from workbook preview rows."""
    created_count = 0
    for row in valid_rows:
        study = resolve_study(row.get('study_doi', ''), row.get('study_title', ''))
        if not study:
            continue
        group = Group.objects.filter(study=study, name=row['name']).first()
        if group:
            continue
        Group.objects.create(
            study=study,
            name=row['name'],
            condition=row['condition'],
            sample_size=row['sample_size'],
            cohort=row['cohort'],
            site=row['site'],
            notes=row['notes'],
        )
        created_count += 1
    return created_count


def run_workbook_comparison_import(valid_rows, batch):
    """Create missing comparisons from workbook preview rows."""
    created_count = 0
    for row in valid_rows:
        study = resolve_study(row.get('study_doi', ''), row.get('study_title', ''))
        group_a = resolve_group(row.get('study_doi', ''), row.get('study_title', ''), row['group_a_name'])
        group_b = resolve_group(row.get('study_doi', ''), row.get('study_title', ''), row['group_b_name'])
        if not study or not group_a or not group_b:
            continue
        comparison = Comparison.objects.filter(
            study=study,
            group_a=group_a,
            group_b=group_b,
            label=row['label'],
        ).first()
        if comparison:
            continue
        Comparison.objects.create(
            study=study,
            group_a=group_a,
            group_b=group_b,
            label=row['label'],
            notes=row['notes'],
        )
        created_count += 1
    return created_count


def run_workbook_organism_import(valid_rows, batch):
    """Create missing organisms from workbook preview rows."""
    created_count = 0
    for row in valid_rows:
        organism = resolve_organism(row['scientific_name'], row['ncbi_taxonomy_id'])
        if organism:
            continue
        Organism.objects.create(
            ncbi_taxonomy_id=row['ncbi_taxonomy_id'],
            scientific_name=row['scientific_name'],
            rank=row['rank'],
            notes=row['notes'],
        )
        created_count += 1
    return created_count


def run_workbook_metadata_variable_import(valid_rows, batch):
    """Create missing metadata variables from workbook preview rows."""
    created_count = 0
    for row in valid_rows:
        variable = MetadataVariable.objects.filter(name=row['name']).first()
        if variable:
            continue
        MetadataVariable.objects.create(
            name=row['name'],
            display_name=row['display_name'],
            value_type=row['value_type'],
            is_filterable=row['is_filterable'],
        )
        created_count += 1
    return created_count


def run_workbook_metadata_value_import(valid_rows, batch):
    """Create missing metadata values from workbook preview rows."""
    created_count = 0
    for row in valid_rows:
        group = resolve_group(row.get('study_doi', ''), row.get('study_title', ''), row['group_name'])
        variable = MetadataVariable.objects.filter(name=row['variable_name']).first()
        if not group or not variable:
            continue
        value = MetadataValue.objects.filter(group=group, variable=variable).first()
        if value:
            continue
        MetadataValue.objects.create(
            group=group,
            variable=variable,
            value_float=row.get('value_float'),
            value_int=row.get('value_int'),
            value_text=row.get('value_text'),
            value_bool=row.get('value_bool'),
        )
        created_count += 1
    return created_count


def run_workbook_qualitative_finding_import(valid_rows, batch):
    """Create qualitative findings from workbook preview rows."""
    created_count = 0
    for row in valid_rows:
        comparison = resolve_comparison(
            row.get('study_doi', ''),
            row.get('study_title', ''),
            row['group_a_name'],
            row['group_b_name'],
            row['comparison_label'],
        )
        organism = resolve_organism(
            row['organism_scientific_name'],
            row.get('organism_ncbi_taxonomy_id'),
        )
        if not comparison or not organism:
            continue
        finding = QualitativeFinding.objects.filter(
            comparison=comparison,
            organism=organism,
            direction=row['direction'],
            source=row['source'],
        ).first()
        if finding:
            continue
        QualitativeFinding.objects.create(
            comparison=comparison,
            organism=organism,
            direction=row['direction'],
            source=row['source'],
            notes=row['notes'],
            import_batch=batch,
        )
        created_count += 1
    return created_count


def run_workbook_quantitative_finding_import(valid_rows, batch):
    """Create quantitative findings from workbook preview rows."""
    created_count = 0
    for row in valid_rows:
        group = resolve_group(row.get('study_doi', ''), row.get('study_title', ''), row['group_name'])
        organism = resolve_organism(
            row['organism_scientific_name'],
            row.get('organism_ncbi_taxonomy_id'),
        )
        if not group or not organism:
            continue
        finding = QuantitativeFinding.objects.filter(
            group=group,
            organism=organism,
            value_type=row['value_type'],
            source=row['source'],
        ).first()
        if finding:
            continue
        QuantitativeFinding.objects.create(
            group=group,
            organism=organism,
            value_type=row['value_type'],
            value=row['value'],
            unit=row['unit'],
            source=row['source'],
            notes=row['notes'],
            import_batch=batch,
        )
        created_count += 1
    return created_count


def run_workbook_alpha_metric_import(valid_rows, batch):
    """Create alpha metrics from workbook preview rows."""
    created_count = 0
    for row in valid_rows:
        group = resolve_group(row.get('study_doi', ''), row.get('study_title', ''), row['group_name'])
        if not group:
            continue
        metric = AlphaMetric.objects.filter(group=group, metric=row['metric'], source=row['source']).first()
        if metric:
            continue
        AlphaMetric.objects.create(
            group=group,
            metric=row['metric'],
            value=row['value'],
            source=row['source'],
            notes=row['notes'],
            import_batch=batch,
        )
        created_count += 1
    return created_count


def run_workbook_beta_metric_import(valid_rows, batch):
    """Create beta metrics from workbook preview rows."""
    created_count = 0
    for row in valid_rows:
        comparison = resolve_comparison(
            row.get('study_doi', ''),
            row.get('study_title', ''),
            row['group_a_name'],
            row['group_b_name'],
            row['comparison_label'],
        )
        if not comparison:
            continue
        metric = BetaMetric.objects.filter(
            comparison=comparison,
            metric=row['metric'],
            source=row['source'],
        ).first()
        if metric:
            continue
        BetaMetric.objects.create(
            comparison=comparison,
            metric=row['metric'],
            value=row['value'],
            source=row['source'],
            notes=row['notes'],
            import_batch=batch,
        )
        created_count += 1
    return created_count


WORKBOOK_IMPORT_RUNNERS = {
    'study': run_workbook_study_import,
    'group': run_workbook_group_import,
    'comparison': run_workbook_comparison_import,
    'organism': run_workbook_organism_import,
    'metadata_variable': run_workbook_metadata_variable_import,
    'metadata_value': run_workbook_metadata_value_import,
    'qualitative_finding': run_workbook_qualitative_finding_import,
    'quantitative_finding': run_workbook_quantitative_finding_import,
    'alpha_metric': run_workbook_alpha_metric_import,
    'beta_metric': run_workbook_beta_metric_import,
}

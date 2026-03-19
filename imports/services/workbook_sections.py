"""Workbook preview builders for core sheets and diversity metrics."""

from .constants import (
    COMPARISON_TYPE_ALLOWED_VALUES,
    GROUP_TYPE_ALLOWED_VALUES,
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
    parse_float,
    parse_optional_bool,
    parse_optional_int,
    split_source_and_notes,
)
from .taxonomy import build_taxon_preview_payload
from .workbook_common import build_section_preview, missing_columns_error


def build_paper_section(*, sheet, batch_name, file_name, state):
    """Build the study preview section and seed workbook-level paper references."""
    required_columns = ('paper_id', 'title', 'status')
    fatal_error = missing_columns_error(required_columns, sheet['fieldnames'])
    if fatal_error:
        return {'fatal_error': fatal_error}

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

    return build_section_preview(
        batch_name=batch_name,
        import_type='study',
        file_name=file_name,
        required_columns=required_columns,
        valid_rows=valid_rows,
        errors=errors,
        duplicates=duplicates,
        total_rows=len(sheet['rows']),
    )


def build_group_section(*, sheet, batch_name, file_name, state):
    """Build the group preview section and collect group-linked raw metadata rows."""
    required_columns = ('group_id', 'paper_id', 'group_name_as_written')
    valid_rows = []
    errors = []
    duplicates = []
    group_ids_seen = set()
    seen_group_keys = set()

    missing_columns = missing_columns_error(required_columns, sheet['fieldnames'])
    if missing_columns and sheet['rows']:
        errors.append({'row_number': None, 'message': missing_columns})
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

            group_key = (paper_ref['study_doi'], paper_ref['study_title'], group_name)
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

            collect_group_metadata_rows(
                row_number=row_number,
                paper_ref=paper_ref,
                group_name=group_name,
                data=data,
                state=state,
            )

    return build_section_preview(
        batch_name=batch_name,
        import_type='group',
        file_name=file_name,
        required_columns=required_columns,
        valid_rows=valid_rows,
        errors=errors,
        duplicates=duplicates,
        total_rows=len(sheet['rows']),
    )


def collect_group_metadata_rows(*, row_number, paper_ref, group_name, data, state):
    """Extract predefined group-side workbook fields into raw metadata rows."""
    for metadata_name in ('group_type', 'age', 'women_percent', 'age2'):
        raw_value = data.get(metadata_name, '')
        if not raw_value and metadata_name in {'age', 'women_percent'}:
            raw_value = 'NA'
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


def build_comparison_section(*, sheet, batch_name, file_name, state):
    """Build the comparison preview section and seed workbook comparison references."""
    required_columns = ('comparison_id', 'paper_id', 'target_group_id', 'reference_group_id')
    valid_rows = []
    errors = []
    duplicates = []
    comparison_ids_seen = set()
    seen_comparison_keys = set()

    missing_columns = missing_columns_error(required_columns, sheet['fieldnames'])
    if missing_columns and sheet['rows']:
        errors.append({'row_number': None, 'message': missing_columns})
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

    return build_section_preview(
        batch_name=batch_name,
        import_type='comparison',
        file_name=file_name,
        required_columns=required_columns,
        valid_rows=valid_rows,
        errors=errors,
        duplicates=duplicates,
        total_rows=len(sheet['rows']),
    )


def build_taxon_section(*, sheet, batch_name, file_name, state):
    """Build the taxon preview section and seed workbook taxon references."""
    required_columns = ('organism_id', 'organism_as_written')
    valid_rows = []
    errors = []
    duplicates = []
    organism_ids_seen = set()
    seen_organism_names = set()
    seen_organism_taxonomy_ids = set()

    missing_columns = missing_columns_error(required_columns, sheet['fieldnames'])
    if missing_columns and sheet['rows']:
        errors.append({'row_number': None, 'message': missing_columns})
    else:
        for row in sheet['rows']:
            row_number = row['row_number']
            data = cleaned_row(row['data'])
            organism_id = data.get('organism_id', '')
            raw_name = data.get('organism_as_written', '')
            scientific_name = data.get('suggested_clean_name', '') or raw_name

            if not any(
                [
                    scientific_name,
                    data.get('suggested_clean_name', ''),
                    data.get('rank_if_known', ''),
                    data.get('notes', ''),
                    data.get('ncbi_id', ''),
                    data.get('resolved', ''),
                ]
            ):
                continue

            if not organism_id:
                errors.append({'row_number': row_number, 'message': 'organism_id is required.'})
                continue
            if organism_id in organism_ids_seen:
                errors.append({'row_number': row_number, 'message': 'Duplicate organism_id in workbook.'})
                continue
            organism_ids_seen.add(organism_id)

            if not raw_name:
                errors.append({'row_number': row_number, 'message': 'organism_as_written is required.'})
                continue

            ncbi_taxonomy_id, taxonomy_error = parse_optional_int(data.get('ncbi_id', ''), 'ncbi_id')
            if taxonomy_error:
                errors.append({'row_number': row_number, 'message': taxonomy_error})
                continue

            is_resolved, resolved_error = parse_optional_bool(data.get('resolved', ''), 'resolved')
            if resolved_error:
                errors.append({'row_number': row_number, 'message': resolved_error})
                continue
            if is_resolved is not True:
                state['unresolved_taxon_ids'].add(organism_id)
                state['skipped_rows'].append(
                    {
                        'section': 'organisms',
                        'row_number': row_number,
                        'message': f'Skipped because taxon {organism_id} is not resolved.',
                    }
                )
                continue

            notes = combine_note_parts(
                data.get('notes', ''),
                labeled_note('Imported as written', raw_name),
                labeled_note('Resolved', data.get('resolved', '')),
            )
            resolution = build_taxon_preview_payload(
                scientific_name=scientific_name,
                ncbi_taxonomy_id=ncbi_taxonomy_id,
                rank=data.get('rank_if_known', ''),
                notes=notes,
                aliases=[raw_name] if raw_name.lower() != scientific_name.lower() else [],
            )

            state['taxon_refs'][organism_id] = {
                'scientific_name': resolution['scientific_name'],
                'ncbi_taxonomy_id': resolution['ncbi_taxonomy_id'],
            }

            duplicate_name_key = scientific_name.lower()
            if ncbi_taxonomy_id is not None:
                if ncbi_taxonomy_id in seen_organism_taxonomy_ids:
                    duplicates.append({'row_number': row_number, 'message': 'Duplicate ncbi_id in workbook.'})
                    continue
                seen_organism_taxonomy_ids.add(ncbi_taxonomy_id)
            elif duplicate_name_key in seen_organism_names:
                duplicates.append({'row_number': row_number, 'message': 'Duplicate organism name in workbook.'})
                continue

            seen_organism_names.add(duplicate_name_key)
            valid_rows.append(
                {
                    'row_number': row_number,
                    'ncbi_taxonomy_id': resolution['ncbi_taxonomy_id'],
                    'scientific_name': resolution['scientific_name'],
                    'rank': resolution['rank'],
                    'notes': resolution['notes'],
                    'aliases': resolution['aliases'],
                    'lineage': resolution['lineage'],
                    'lineage_summary': resolution['lineage_summary'],
                    'resolution_status': resolution['resolution_status'],
                    'review_required': resolution['review_required'],
                    'resolver_source': resolution['resolver_source'],
                }
            )

    return build_section_preview(
        batch_name=batch_name,
        import_type='taxon',
        file_name=file_name,
        required_columns=required_columns,
        valid_rows=valid_rows,
        errors=errors,
        duplicates=duplicates,
        total_rows=len(sheet['rows']),
    )


def build_qualitative_section(*, sheet, batch_name, file_name, state):
    """Build the qualitative finding preview section from workbook comparison direction rows."""
    required_columns = ('paper_id', 'comparison_id', 'organism_id', 'direction')
    valid_rows = []
    errors = []
    duplicates = []
    seen_qualitative_keys = set()

    missing_columns = missing_columns_error(required_columns, sheet['fieldnames'])
    if missing_columns and sheet['rows']:
        errors.append({'row_number': None, 'message': missing_columns})
    else:
        for row in sheet['rows']:
            row_number = row['row_number']
            data = cleaned_row(row['data'])
            paper_id = data.get('paper_id', '')
            organism_id = data.get('organism_id', '')

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

            if organism_id in state['unresolved_taxon_ids']:
                state['skipped_rows'].append(
                    {
                        'section': 'qualitative_findings',
                        'row_number': row_number,
                        'message': f'Skipped because taxon {organism_id} is not resolved.',
                    }
                )
                continue

            comparison_ref = state['comparison_refs'].get(data.get('comparison_id', ''))
            if not comparison_ref:
                errors.append({'row_number': row_number, 'message': 'comparison_id does not resolve to a valid comparison.'})
                continue

            taxon_ref = state['taxon_refs'].get(organism_id)
            if not taxon_ref:
                errors.append({'row_number': row_number, 'message': 'organism_id does not resolve to a valid taxon.'})
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

            source, notes = split_source_and_notes(
                data.get('where_found', ''),
                data.get('notes', ''),
                labeled_note('Finding type', finding_type),
                labeled_note('Organism as written', data.get('organism_as_writiten', '')),
            )
            duplicate_key = (
                comparison_ref['study_doi'],
                comparison_ref['study_title'],
                comparison_ref['group_a_name'],
                comparison_ref['group_b_name'],
                comparison_ref['comparison_label'],
                taxon_ref['scientific_name'],
                WORKBOOK_DIRECTION_MAP[direction],
                source,
            )
            if duplicate_key in seen_qualitative_keys:
                duplicates.append({'row_number': row_number, 'message': 'Duplicate qualitative finding in workbook.'})
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
                    'taxon_scientific_name': taxon_ref['scientific_name'],
                    'taxon_ncbi_taxonomy_id': taxon_ref['ncbi_taxonomy_id'],
                    'direction': WORKBOOK_DIRECTION_MAP[direction],
                    'source': source,
                    'notes': notes,
                }
            )

    return build_section_preview(
        batch_name=batch_name,
        import_type='qualitative_finding',
        file_name=file_name,
        required_columns=required_columns,
        valid_rows=valid_rows,
        errors=errors,
        duplicates=duplicates,
        total_rows=len(sheet['rows']),
    )


def build_quantitative_section(*, sheet, batch_name, file_name, state):
    """Build the quantitative finding preview section from workbook numeric rows."""
    required_columns = ('paper_id', 'group_id', 'organism_id', 'value_type', 'value')
    valid_rows = []
    errors = []
    duplicates = []
    seen_quantitative_keys = set()

    missing_columns = missing_columns_error(required_columns, sheet['fieldnames'])
    if missing_columns and sheet['rows']:
        errors.append({'row_number': None, 'message': missing_columns})
    else:
        for row in sheet['rows']:
            row_number = row['row_number']
            data = cleaned_row(row['data'])
            paper_id = data.get('paper_id', '')
            organism_id = data.get('organism_id', '')

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

            if organism_id in state['unresolved_taxon_ids']:
                state['skipped_rows'].append(
                    {
                        'section': 'quantitative_findings',
                        'row_number': row_number,
                        'message': f'Skipped because taxon {organism_id} is not resolved.',
                    }
                )
                continue

            group_ref = state['group_refs'].get(data.get('group_id', ''))
            if not group_ref:
                errors.append({'row_number': row_number, 'message': 'group_id does not resolve to a valid group.'})
                continue

            taxon_ref = state['taxon_refs'].get(organism_id)
            if not taxon_ref:
                errors.append({'row_number': row_number, 'message': 'organism_id does not resolve to a valid taxon.'})
                continue

            value_type = data.get('value_type', '')
            if value_type not in WORKBOOK_QUANTITATIVE_VALUE_TYPE_ALLOWED_VALUES:
                errors.append({'row_number': row_number, 'message': 'value_type must be relative_abundance.'})
                continue

            value, value_error = parse_float(data.get('value', ''), 'value')
            if value_error:
                errors.append({'row_number': row_number, 'message': value_error})
                continue

            source, notes = split_source_and_notes(
                data.get('where_found', ''),
                data.get('notes', ''),
            )
            duplicate_key = (
                group_ref['study_doi'],
                group_ref['study_title'],
                group_ref['group_name'],
                taxon_ref['scientific_name'],
                value_type,
                source,
            )
            if duplicate_key in seen_quantitative_keys:
                duplicates.append({'row_number': row_number, 'message': 'Duplicate quantitative finding in workbook.'})
                continue
            seen_quantitative_keys.add(duplicate_key)
            valid_rows.append(
                {
                    'row_number': row_number,
                    'study_doi': group_ref['study_doi'],
                    'study_title': group_ref['study_title'],
                    'group_name': group_ref['group_name'],
                    'taxon_scientific_name': taxon_ref['scientific_name'],
                    'taxon_ncbi_taxonomy_id': taxon_ref['ncbi_taxonomy_id'],
                    'value_type': value_type,
                    'value': value,
                    'unit': data.get('unit', ''),
                    'source': source,
                    'notes': notes,
                }
            )

    return build_section_preview(
        batch_name=batch_name,
        import_type='quantitative_finding',
        file_name=file_name,
        required_columns=required_columns,
        valid_rows=valid_rows,
        errors=errors,
        duplicates=duplicates,
        total_rows=len(sheet['rows']),
    )


def build_diversity_sections(*, sheet, batch_name, file_name, state):
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

    missing_columns = missing_columns_error(required_columns, sheet['fieldnames'])
    if missing_columns and sheet['rows']:
        alpha_errors.append({'row_number': None, 'message': missing_columns})
    else:
        for row in sheet['rows']:
            row_number = row['row_number']
            data = cleaned_row(row['data'])
            if not any(
                [
                    data.get('paper_id', ''),
                    data.get('comparison_id', ''),
                    data.get('group_id', ''),
                    data.get('diversity_category', ''),
                    data.get('metric_as_written', ''),
                    data.get('value', ''),
                ]
            ):
                continue
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

            source, notes = split_source_and_notes(
                data.get('where_found', ''),
                data.get('notes', ''),
            )

            if category == 'alpha':
                handle_alpha_diversity_row(
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
                )
                continue

            handle_beta_diversity_row(
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
            )

    alpha_section = build_section_preview(
        batch_name=batch_name,
        import_type='alpha_metric',
        file_name=file_name,
        required_columns=required_columns,
        valid_rows=alpha_valid_rows,
        errors=alpha_errors,
        duplicates=alpha_duplicates,
        total_rows=len(alpha_valid_rows) + len(alpha_errors) + len(alpha_duplicates),
    )
    beta_section = build_section_preview(
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


def handle_alpha_diversity_row(*, row_number, data, metric, value, source, notes, state, valid_rows, errors, duplicates, seen_keys):
    """Validate and append a single alpha diversity row to the preview payload."""
    group_ref = state['group_refs'].get(data.get('group_id', ''))
    if not group_ref:
        errors.append({'row_number': row_number, 'message': 'Alpha diversity rows require a valid group_id.'})
        return

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


def handle_beta_diversity_row(*, row_number, data, metric, value, source, notes, state, valid_rows, errors, duplicates, seen_keys):
    """Validate and append a single beta diversity row to the preview payload."""
    comparison_ref = state['comparison_refs'].get(data.get('comparison_id', ''))
    if not comparison_ref:
        errors.append({'row_number': row_number, 'message': 'Beta diversity rows require a valid comparison_id.'})
        return

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

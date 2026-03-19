"""Workbook import execution runners."""

from django.db import transaction

from database.models import (
    AlphaMetric,
    BetaMetric,
    Comparison,
    Group,
    ImportBatch,
    MetadataValue,
    MetadataVariable,
    QualitativeFinding,
    QuantitativeFinding,
    Study,
)

from .helpers import resolve_comparison, resolve_group, resolve_study, resolve_taxon_reference
from .taxonomy import resolve_and_upsert_taxon, upsert_taxon_lineage


@transaction.atomic
def run_workbook_import(preview_data, workbook_import_runners):
    """Persist a confirmed workbook preview by replaying each validated section runner."""
    batch = ImportBatch.objects.create(
        name=preview_data['batch_name'],
        import_type='excel_workbook',
        status=ImportBatch.Status.VALIDATED,
        source_file=preview_data.get('file_name', ''),
    )

    applied_count = 0
    section_counts = {}
    for section in preview_data.get('sections', []):
        import_type = section['import_type']
        runner = workbook_import_runners.get(import_type)
        if not runner:
            continue
        section_applied_count = runner(section.get('valid_rows', []), batch)
        section_counts[import_type] = section_applied_count
        applied_count += section_applied_count

    duplicate_count = len(preview_data.get('duplicates', []))
    error_count = len(preview_data.get('errors', []))
    skipped_count = len(preview_data.get('skipped_rows', []))
    batch.success_count = applied_count
    batch.error_count = duplicate_count + error_count
    batch.status = ImportBatch.Status.COMPLETED if error_count == 0 else ImportBatch.Status.FAILED
    section_summary = ', '.join(
        f'{import_type}: {count}'
        for import_type, count in section_counts.items()
        if count
    )
    batch.notes = (
        f'Imported or updated {applied_count} rows from Excel workbook. '
        f'Skipped {duplicate_count} duplicates. '
        f'Skipped {skipped_count} workbook rows. '
        f'Validation errors: {error_count}.'
    )
    if section_summary:
        batch.notes = f'{batch.notes} Created by section: {section_summary}.'
    batch.save(update_fields=['success_count', 'error_count', 'status', 'notes'])
    return batch


def run_workbook_study_import(valid_rows, batch):
    """Upsert studies from workbook preview rows."""
    applied_count = 0
    for row in valid_rows:
        study = resolve_study(row.get('doi') or '', row['title'])
        if study:
            study.doi = row['doi']
            study.title = row['title']
            study.country = row['country']
            study.journal = row['journal']
            study.year = row['year']
            study.notes = row['notes']
            study.save(update_fields=['doi', 'title', 'country', 'journal', 'year', 'notes', 'updated_at'])
        else:
            Study.objects.create(
                doi=row['doi'],
                title=row['title'],
                country=row['country'],
                journal=row['journal'],
                year=row['year'],
                notes=row['notes'],
            )
        applied_count += 1
    return applied_count


def run_workbook_group_import(valid_rows, batch):
    """Upsert groups from workbook preview rows."""
    applied_count = 0
    for row in valid_rows:
        study = resolve_study(row.get('study_doi', ''), row.get('study_title', ''))
        if not study:
            continue
        Group.objects.update_or_create(
            study=study,
            name=row['name'],
            defaults={
                'condition': row['condition'],
                'sample_size': row['sample_size'],
                'cohort': row['cohort'],
                'site': row['site'],
                'notes': row['notes'],
            },
        )
        applied_count += 1
    return applied_count


def run_workbook_comparison_import(valid_rows, batch):
    """Upsert comparisons from workbook preview rows."""
    applied_count = 0
    for row in valid_rows:
        study = resolve_study(row.get('study_doi', ''), row.get('study_title', ''))
        group_a = resolve_group(row.get('study_doi', ''), row.get('study_title', ''), row['group_a_name'])
        group_b = resolve_group(row.get('study_doi', ''), row.get('study_title', ''), row['group_b_name'])
        if not study or not group_a or not group_b:
            continue
        Comparison.objects.update_or_create(
            study=study,
            group_a=group_a,
            group_b=group_b,
            label=row['label'],
            defaults={
                'notes': row['notes'],
            },
        )
        applied_count += 1
    return applied_count


def run_workbook_taxon_import(valid_rows, batch):
    """Upsert taxa from workbook preview rows."""
    applied_count = 0
    for row in valid_rows:
        if row.get('review_required'):
            continue
        if row.get('lineage'):
            upsert_taxon_lineage(
                row['lineage'],
                aliases=row.get('aliases', ()),
                leaf_notes=row.get('notes', ''),
            )
        else:
            resolve_and_upsert_taxon(
                scientific_name=row['scientific_name'],
                ncbi_taxonomy_id=row['ncbi_taxonomy_id'],
                rank=row['rank'],
                notes=row['notes'],
                aliases=row.get('aliases', ()),
            )
        applied_count += 1
    return applied_count


def run_workbook_metadata_variable_import(valid_rows, batch):
    """Upsert metadata variables from workbook preview rows."""
    applied_count = 0
    for row in valid_rows:
        MetadataVariable.objects.update_or_create(
            name=row['name'],
            defaults={
                'display_name': row['display_name'],
                'value_type': row['value_type'],
                'is_filterable': row['is_filterable'],
            },
        )
        applied_count += 1
    return applied_count


def run_workbook_metadata_value_import(valid_rows, batch):
    """Upsert metadata values from workbook preview rows."""
    applied_count = 0
    for row in valid_rows:
        group = resolve_group(row.get('study_doi', ''), row.get('study_title', ''), row['group_name'])
        variable = MetadataVariable.objects.filter(name=row['variable_name']).first()
        if not group or not variable:
            continue
        MetadataValue.objects.update_or_create(
            group=group,
            variable=variable,
            defaults={
                'value_float': row.get('value_float'),
                'value_int': row.get('value_int'),
                'value_text': row.get('value_text'),
                'value_bool': row.get('value_bool'),
            },
        )
        applied_count += 1
    return applied_count


def run_workbook_qualitative_finding_import(valid_rows, batch):
    """Upsert qualitative findings from workbook preview rows."""
    applied_count = 0
    for row in valid_rows:
        comparison = resolve_comparison(
            row.get('study_doi', ''),
            row.get('study_title', ''),
            row['group_a_name'],
            row['group_b_name'],
            row['comparison_label'],
        )
        taxon = resolve_taxon_reference(
            row['taxon_scientific_name'],
            row.get('taxon_ncbi_taxonomy_id'),
        )
        if not comparison or not taxon:
            continue
        QualitativeFinding.objects.update_or_create(
            comparison=comparison,
            taxon=taxon,
            direction=row['direction'],
            source=row['source'],
            defaults={
                'notes': row['notes'],
                'import_batch': batch,
            },
        )
        applied_count += 1
    return applied_count


def run_workbook_quantitative_finding_import(valid_rows, batch):
    """Upsert quantitative findings from workbook preview rows."""
    applied_count = 0
    for row in valid_rows:
        group = resolve_group(row.get('study_doi', ''), row.get('study_title', ''), row['group_name'])
        taxon = resolve_taxon_reference(
            row['taxon_scientific_name'],
            row.get('taxon_ncbi_taxonomy_id'),
        )
        if not group or not taxon:
            continue
        QuantitativeFinding.objects.update_or_create(
            group=group,
            taxon=taxon,
            value_type=row['value_type'],
            source=row['source'],
            defaults={
                'value': row['value'],
                'unit': row['unit'],
                'notes': row['notes'],
                'import_batch': batch,
            },
        )
        applied_count += 1
    return applied_count


def run_workbook_alpha_metric_import(valid_rows, batch):
    """Upsert alpha metrics from workbook preview rows."""
    applied_count = 0
    for row in valid_rows:
        group = resolve_group(row.get('study_doi', ''), row.get('study_title', ''), row['group_name'])
        if not group:
            continue
        AlphaMetric.objects.update_or_create(
            group=group,
            metric=row['metric'],
            source=row['source'],
            defaults={
                'value': row['value'],
                'notes': row['notes'],
                'import_batch': batch,
            },
        )
        applied_count += 1
    return applied_count


def run_workbook_beta_metric_import(valid_rows, batch):
    """Upsert beta metrics from workbook preview rows."""
    applied_count = 0
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
        BetaMetric.objects.update_or_create(
            comparison=comparison,
            metric=row['metric'],
            source=row['source'],
            defaults={
                'value': row['value'],
                'notes': row['notes'],
                'import_batch': batch,
            },
        )
        applied_count += 1
    return applied_count


WORKBOOK_IMPORT_RUNNERS = {
    'study': run_workbook_study_import,
    'group': run_workbook_group_import,
    'comparison': run_workbook_comparison_import,
    'taxon': run_workbook_taxon_import,
    'metadata_variable': run_workbook_metadata_variable_import,
    'metadata_value': run_workbook_metadata_value_import,
    'qualitative_finding': run_workbook_qualitative_finding_import,
    'quantitative_finding': run_workbook_quantitative_finding_import,
    'alpha_metric': run_workbook_alpha_metric_import,
    'beta_metric': run_workbook_beta_metric_import,
}

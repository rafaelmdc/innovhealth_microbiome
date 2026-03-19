"""Database write runners for validated CSV import previews."""

from database.models import (
    AlphaMetric,
    BetaMetric,
    Comparison,
    Group,
    MetadataValue,
    MetadataVariable,
    QualitativeFinding,
    QuantitativeFinding,
    Study,
)

from .taxonomy import resolve_and_upsert_taxon, upsert_taxon_lineage


def run_taxon_import(valid_rows, batch):
    """Create taxon records from validated CSV rows."""
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


def run_study_import(valid_rows, batch):
    """Create study records from validated CSV rows."""
    for row in valid_rows:
        Study.objects.create(
            doi=row['doi'],
            title=row['title'],
            country=row['country'],
            journal=row['journal'],
            year=row['year'],
            notes=row['notes'],
        )
    return len(valid_rows)


def run_group_import(valid_rows, batch):
    """Create group records from validated CSV rows."""
    for row in valid_rows:
        Group.objects.create(
            study_id=row['study_id'],
            name=row['name'],
            condition=row['condition'],
            sample_size=row['sample_size'],
            cohort=row['cohort'],
            site=row['site'],
            notes=row['notes'],
        )
    return len(valid_rows)


def run_comparison_import(valid_rows, batch):
    """Create comparison records from validated CSV rows."""
    for row in valid_rows:
        Comparison.objects.create(
            study_id=row['study_id'],
            group_a_id=row['group_a_id'],
            group_b_id=row['group_b_id'],
            label=row['label'],
            notes=row['notes'],
        )
    return len(valid_rows)


def run_metadata_variable_import(valid_rows, batch):
    """Create metadata variable records from validated CSV rows."""
    for row in valid_rows:
        MetadataVariable.objects.create(
            name=row['name'],
            display_name=row['display_name'],
            value_type=row['value_type'],
            is_filterable=row['is_filterable'],
        )
    return len(valid_rows)


def run_metadata_value_import(valid_rows, batch):
    """Create metadata value records from validated CSV rows."""
    for row in valid_rows:
        MetadataValue.objects.create(
            group_id=row['group_id'],
            variable_id=row['variable_id'],
            value_float=row['value_float'],
            value_int=row['value_int'],
            value_text=row['value_text'],
            value_bool=row['value_bool'],
        )
    return len(valid_rows)


def run_qualitative_finding_import(valid_rows, batch):
    """Create qualitative findings and link them to the import batch."""
    for row in valid_rows:
        QualitativeFinding.objects.create(
            comparison_id=row['comparison_id'],
            taxon_id=row['taxon_id'],
            direction=row['direction'],
            source=row['source'],
            notes=row['notes'],
            import_batch=batch,
        )
    return len(valid_rows)


def run_quantitative_finding_import(valid_rows, batch):
    """Create quantitative findings and link them to the import batch."""
    for row in valid_rows:
        QuantitativeFinding.objects.create(
            group_id=row['group_id'],
            taxon_id=row['taxon_id'],
            value_type=row['value_type'],
            value=row['value'],
            unit=row['unit'],
            source=row['source'],
            notes=row['notes'],
            import_batch=batch,
        )
    return len(valid_rows)


def run_alpha_metric_import(valid_rows, batch):
    """Create alpha metric records and link them to the import batch."""
    for row in valid_rows:
        AlphaMetric.objects.create(
            group_id=row['group_id'],
            metric=row['metric'],
            value=row['value'],
            source=row['source'],
            notes=row['notes'],
            import_batch=batch,
        )
    return len(valid_rows)


def run_beta_metric_import(valid_rows, batch):
    """Create beta metric records and link them to the import batch."""
    for row in valid_rows:
        BetaMetric.objects.create(
            comparison_id=row['comparison_id'],
            metric=row['metric'],
            value=row['value'],
            source=row['source'],
            notes=row['notes'],
            import_batch=batch,
        )
    return len(valid_rows)


IMPORT_RUNNERS = {
    'taxon': run_taxon_import,
    'study': run_study_import,
    'group': run_group_import,
    'comparison': run_comparison_import,
    'metadata_variable': run_metadata_variable_import,
    'metadata_value': run_metadata_value_import,
    'qualitative_finding': run_qualitative_finding_import,
    'quantitative_finding': run_quantitative_finding_import,
    'alpha_metric': run_alpha_metric_import,
    'beta_metric': run_beta_metric_import,
}

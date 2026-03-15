"""Database write runners for validated CSV import previews."""

from database.models import (
    AlphaMetric,
    BetaMetric,
    Comparison,
    Group,
    MetadataValue,
    MetadataVariable,
    Organism,
    QualitativeFinding,
    QuantitativeFinding,
    Study,
)


def run_organism_import(valid_rows, batch):
    """Create organism records from validated CSV rows."""
    for row in valid_rows:
        Organism.objects.create(
            ncbi_taxonomy_id=row['ncbi_taxonomy_id'],
            scientific_name=row['scientific_name'],
            rank=row['rank'],
            notes=row['notes'],
        )
    return len(valid_rows)


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
            organism_id=row['organism_id'],
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
            organism_id=row['organism_id'],
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
    'organism': run_organism_import,
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

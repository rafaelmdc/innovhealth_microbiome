"""Shared constants for importer validation and workbook mapping."""

from database.models import MetadataVariable, QualitativeFinding, QuantitativeFinding


SUPPORTED_IMPORT_TYPES = (
    'taxon',
    'study',
    'group',
    'comparison',
    'metadata_variable',
    'metadata_value',
    'qualitative_finding',
    'quantitative_finding',
    'alpha_metric',
    'beta_metric',
    'excel_workbook',
)

BOOLEAN_TRUE_VALUES = {'1', 'true', 'yes', 'on'}
BOOLEAN_FALSE_VALUES = {'0', 'false', 'no', 'off'}
WORKBOOK_SHEET_ORDER = (
    'paper',
    'groups',
    'comparissons',
    'qualitative_findings',
    'quantitative_findings',
    'diversity_metrics',
    'organisms',
    'extra_metadata',
)
WORKBOOK_SHEET_ALIASES = {
    'paper': 'paper',
    'papers': 'paper',
    'groups': 'groups',
    'comparisons': 'comparissons',
    'comparissons': 'comparissons',
    'qualitative_findings': 'qualitative_findings',
    'quantitative_findings': 'quantitative_findings',
    'quantitive_findings': 'quantitative_findings',
    'diversity_metrics': 'diversity_metrics',
    'organisms': 'organisms',
    'extra_metadata': 'extra_metadata',
}
PAPER_STATUS_ALLOWED_VALUES = {'todo', 'in_progress', 'complete', 'needs_review'}
GROUP_TYPE_ALLOWED_VALUES = {
    'case',
    'control',
    'subtype',
    'treatment',
    'follow_up',
    'responder',
    'non_responder',
    'other',
}
COMPARISON_TYPE_ALLOWED_VALUES = {
    'case_vs_control',
    'severity_vs_mild',
    'responder_vs_non_responder',
    'subtype_vs_subtype',
    'treatment_vs_baseline',
    'other',
}
WORKBOOK_DIRECTION_ALLOWED_VALUES = {'increased_in_target', 'decreased_in_target'}
WORKBOOK_DIRECTION_MAP = {
    'increased_in_target': QualitativeFinding.Direction.ENRICHED,
    'decreased_in_target': QualitativeFinding.Direction.DEPLETED,
}
WORKBOOK_FINDING_TYPE_ALLOWED_VALUES = {'relative_direction'}
WORKBOOK_QUANTITATIVE_VALUE_TYPE_ALLOWED_VALUES = {QuantitativeFinding.ValueType.RELATIVE_ABUNDANCE}
WORKBOOK_DIVERSITY_ALLOWED_VALUES = {'alpha', 'beta'}
WORKBOOK_METADATA_FIELD_DEFINITIONS = {
    'group_type': {
        'display_name': 'Group Type',
        'value_type': MetadataVariable.ValueType.TEXT,
    },
    'age': {
        'display_name': 'Age',
        'value_type': MetadataVariable.ValueType.TEXT,
    },
    'women_percent': {
        'display_name': 'Women Percent',
        'value_type': MetadataVariable.ValueType.TEXT,
    },
    'age2': {
        'display_name': 'Age 2',
        'value_type': MetadataVariable.ValueType.TEXT,
    },
}

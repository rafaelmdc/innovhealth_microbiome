from django import forms


class CsvImportUploadForm(forms.Form):
    IMPORT_TYPE_ORGANISM = 'organism'
    IMPORT_TYPE_STUDY = 'study'
    IMPORT_TYPE_SAMPLE = 'sample'
    IMPORT_TYPE_CORE_METADATA = 'core_metadata'
    IMPORT_TYPE_METADATA_VARIABLE = 'metadata_variable'
    IMPORT_TYPE_METADATA_VALUE = 'metadata_value'
    IMPORT_TYPE_RELATIVE_ASSOCIATION = 'relative_association'
    IMPORT_TYPE_ALPHA_METRIC = 'alpha_metric'
    IMPORT_TYPE_BETA_METRIC = 'beta_metric'
    IMPORT_TYPE_CHOICES = (
        (IMPORT_TYPE_ORGANISM, 'Organisms'),
        (IMPORT_TYPE_STUDY, 'Studies'),
        (IMPORT_TYPE_SAMPLE, 'Samples'),
        (IMPORT_TYPE_CORE_METADATA, 'Core Metadata'),
        (IMPORT_TYPE_METADATA_VARIABLE, 'Metadata Variables'),
        (IMPORT_TYPE_METADATA_VALUE, 'Metadata Values'),
        (IMPORT_TYPE_RELATIVE_ASSOCIATION, 'Relative Associations'),
        (IMPORT_TYPE_ALPHA_METRIC, 'Alpha Metrics'),
        (IMPORT_TYPE_BETA_METRIC, 'Beta Metrics'),
    )

    name = forms.CharField(max_length=255)
    import_type = forms.ChoiceField(choices=IMPORT_TYPE_CHOICES)
    csv_file = forms.FileField(help_text='Upload a CSV file for preview and validation.')

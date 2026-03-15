from django import forms


class CsvImportUploadForm(forms.Form):
    SOURCE_FORMAT_CSV = 'csv'
    SOURCE_FORMAT_WORKBOOK = 'excel_workbook'

    IMPORT_TYPE_ORGANISM = 'organism'
    IMPORT_TYPE_STUDY = 'study'
    IMPORT_TYPE_GROUP = 'group'
    IMPORT_TYPE_COMPARISON = 'comparison'
    IMPORT_TYPE_METADATA_VARIABLE = 'metadata_variable'
    IMPORT_TYPE_METADATA_VALUE = 'metadata_value'
    IMPORT_TYPE_QUALITATIVE_FINDING = 'qualitative_finding'
    IMPORT_TYPE_QUANTITATIVE_FINDING = 'quantitative_finding'
    IMPORT_TYPE_ALPHA_METRIC = 'alpha_metric'
    IMPORT_TYPE_BETA_METRIC = 'beta_metric'

    IMPORT_TYPE_CHOICES = (
        (IMPORT_TYPE_ORGANISM, 'Organisms'),
        (IMPORT_TYPE_STUDY, 'Studies'),
        (IMPORT_TYPE_GROUP, 'Groups'),
        (IMPORT_TYPE_COMPARISON, 'Comparisons'),
        (IMPORT_TYPE_METADATA_VARIABLE, 'Metadata Variables'),
        (IMPORT_TYPE_METADATA_VALUE, 'Metadata Values'),
        (IMPORT_TYPE_QUALITATIVE_FINDING, 'Qualitative Findings'),
        (IMPORT_TYPE_QUANTITATIVE_FINDING, 'Quantitative Findings'),
        (IMPORT_TYPE_ALPHA_METRIC, 'Alpha Metrics'),
        (IMPORT_TYPE_BETA_METRIC, 'Beta Metrics'),
    )

    SOURCE_FORMAT_CHOICES = (
        (SOURCE_FORMAT_CSV, 'CSV Contract File'),
        (SOURCE_FORMAT_WORKBOOK, 'Excel Workbook'),
    )

    name = forms.CharField(max_length=255)
    source_format = forms.ChoiceField(choices=SOURCE_FORMAT_CHOICES, initial=SOURCE_FORMAT_CSV)
    import_type = forms.ChoiceField(
        choices=(('', '---------'),) + IMPORT_TYPE_CHOICES,
        required=False,
        help_text='Required for CSV imports. Excel workbook imports use the workbook contract automatically.',
    )
    data_file = forms.FileField(help_text='Upload a CSV contract file or an Excel workbook for preview and validation.')

    def clean(self):
        cleaned_data = super().clean()
        source_format = cleaned_data.get('source_format')
        import_type = cleaned_data.get('import_type')
        data_file = cleaned_data.get('data_file')

        if source_format == self.SOURCE_FORMAT_CSV and not import_type:
            self.add_error('import_type', 'Select a CSV import type.')

        if data_file:
            file_name = data_file.name.lower()
            if source_format == self.SOURCE_FORMAT_CSV and not file_name.endswith('.csv'):
                self.add_error('data_file', 'CSV imports require a .csv file.')
            if source_format == self.SOURCE_FORMAT_WORKBOOK and not file_name.endswith(('.xlsx', '.xlsm')):
                self.add_error('data_file', 'Excel workbook imports require a .xlsx or .xlsm file.')

        return cleaned_data

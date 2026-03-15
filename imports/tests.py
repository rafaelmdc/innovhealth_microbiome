from io import BytesIO

from django.test import TestCase
from openpyxl import Workbook

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

from .services import build_preview, run_import


class ImportServiceTests(TestCase):
    def setUp(self):
        self.study = Study.objects.create(title='Study A', doi='10.1000/example')
        self.group_a = Group.objects.create(study=self.study, name='Case')
        self.group_b = Group.objects.create(study=self.study, name='Control')
        self.comparison = Comparison.objects.create(
            study=self.study,
            group_a=self.group_a,
            group_b=self.group_b,
            label='Case vs control',
        )
        self.organism = Organism.objects.create(
            ncbi_taxonomy_id=100,
            scientific_name='Organism A',
            rank='species',
        )
        self.metadata_variable = MetadataVariable.objects.create(
            name='smoking_status',
            display_name='Smoking Status',
            value_type=MetadataVariable.ValueType.TEXT,
        )

    def test_study_preview_reports_duplicate_doi(self):
        preview = build_preview(
            file_name='studies.csv',
            content='doi,title\n10.1000/example,Duplicate Study\n',
            import_type='study',
            batch_name='Study batch',
        )

        self.assertEqual(preview.valid_rows, [])
        self.assertEqual(len(preview.duplicates), 1)

    def test_group_preview_requires_existing_study(self):
        preview = build_preview(
            file_name='groups.csv',
            content='study_doi,study_title,name\n10.9999/missing,,Cohort X\n',
            import_type='group',
            batch_name='Group batch',
        )

        self.assertEqual(preview.valid_rows, [])
        self.assertEqual(len(preview.errors), 1)

    def test_comparison_import_creates_row(self):
        preview = build_preview(
            file_name='comparisons.csv',
            content=(
                'study_doi,study_title,group_a_name,group_b_name,label\n'
                '10.1000/example,,Case,Control,Case vs control import\n'
            ),
            import_type='comparison',
            batch_name='Comparison batch',
        ).to_dict()

        batch = run_import(preview)

        self.assertEqual(batch.status, ImportBatch.Status.COMPLETED)
        self.assertTrue(
            Comparison.objects.filter(
                study=self.study,
                group_a=self.group_a,
                group_b=self.group_b,
                label='Case vs control import',
            ).exists()
        )

    def test_metadata_value_import_creates_value(self):
        preview = build_preview(
            file_name='metadata_values.csv',
            content=(
                'study_doi,study_title,group_name,variable_name,value_text\n'
                '10.1000/example,,Case,smoking_status,never\n'
            ),
            import_type='metadata_value',
            batch_name='Metadata value batch',
        ).to_dict()

        batch = run_import(preview)
        metadata_value = MetadataValue.objects.get(group=self.group_a, variable=self.metadata_variable)

        self.assertEqual(batch.status, ImportBatch.Status.COMPLETED)
        self.assertEqual(metadata_value.value_text, 'never')

    def test_qualitative_finding_import_creates_batch_link(self):
        preview = build_preview(
            file_name='qualitative_findings.csv',
            content=(
                'study_doi,study_title,group_a_name,group_b_name,comparison_label,organism_scientific_name,direction,source\n'
                '10.1000/example,,Case,Control,Case vs control,Organism A,enriched,Table 2\n'
            ),
            import_type='qualitative_finding',
            batch_name='Qualitative batch',
        ).to_dict()

        batch = run_import(preview)
        finding = QualitativeFinding.objects.get(comparison=self.comparison, organism=self.organism)

        self.assertEqual(batch.status, ImportBatch.Status.COMPLETED)
        self.assertEqual(finding.import_batch, batch)
        self.assertEqual(finding.direction, QualitativeFinding.Direction.ENRICHED)

    def test_quantitative_finding_preview_requires_numeric_value(self):
        preview = build_preview(
            file_name='quantitative_findings.csv',
            content=(
                'study_doi,study_title,group_name,organism_scientific_name,value_type,value,source\n'
                '10.1000/example,,Case,Organism A,relative_abundance,not-a-number,Table 3\n'
            ),
            import_type='quantitative_finding',
            batch_name='Quantitative batch',
        )

        self.assertEqual(preview.valid_rows, [])
        self.assertEqual(len(preview.errors), 1)

    def test_quantitative_finding_import_creates_batch_link(self):
        preview = build_preview(
            file_name='quantitative_findings.csv',
            content=(
                'study_doi,study_title,group_name,organism_scientific_name,value_type,value,source\n'
                '10.1000/example,,Case,Organism A,relative_abundance,0.42,Table 3\n'
            ),
            import_type='quantitative_finding',
            batch_name='Quantitative batch',
        ).to_dict()

        batch = run_import(preview)
        finding = QuantitativeFinding.objects.get(group=self.group_a, organism=self.organism)

        self.assertEqual(batch.status, ImportBatch.Status.COMPLETED)
        self.assertEqual(finding.import_batch, batch)
        self.assertEqual(finding.value, 0.42)

    def test_organism_import_creates_import_batch_and_records(self):
        preview = build_preview(
            file_name='organisms.csv',
            content=(
                'ncbi_taxonomy_id,scientific_name,rank,notes\n'
                '101,Faecalibacterium prausnitzii,species,Important commensal\n'
            ),
            import_type='organism',
            batch_name='Organism batch',
        ).to_dict()

        batch = run_import(preview)

        self.assertEqual(ImportBatch.objects.count(), 1)
        self.assertEqual(batch.status, ImportBatch.Status.COMPLETED)
        self.assertEqual(batch.success_count, 1)
        self.assertEqual(batch.error_count, 0)
        self.assertTrue(
            Organism.objects.filter(
                ncbi_taxonomy_id=101,
                scientific_name='Faecalibacterium prausnitzii',
            ).exists()
        )

    def test_alpha_metric_import_sets_import_batch(self):
        preview = build_preview(
            file_name='alpha_metrics.csv',
            content=(
                'study_doi,study_title,group_name,metric,value,source\n'
                '10.1000/example,,Case,shannon,3.82,Table 4\n'
            ),
            import_type='alpha_metric',
            batch_name='Alpha metric batch',
        ).to_dict()

        batch = run_import(preview)
        metric = AlphaMetric.objects.get(group=self.group_a, metric='shannon')

        self.assertEqual(batch.status, ImportBatch.Status.COMPLETED)
        self.assertEqual(metric.import_batch, batch)
        self.assertEqual(metric.value, 3.82)

    def test_beta_metric_import_sets_import_batch(self):
        preview = build_preview(
            file_name='beta_metrics.csv',
            content=(
                'study_doi,study_title,group_a_name,group_b_name,comparison_label,metric,value,source\n'
                '10.1000/example,,Case,Control,Case vs control,bray_curtis,0.37,Figure 2\n'
            ),
            import_type='beta_metric',
            batch_name='Beta metric batch',
        ).to_dict()

        batch = run_import(preview)
        metric = BetaMetric.objects.get(comparison=self.comparison, metric='bray_curtis')

        self.assertEqual(batch.status, ImportBatch.Status.COMPLETED)
        self.assertEqual(metric.import_batch, batch)
        self.assertEqual(metric.value, 0.37)

    def _build_workbook_bytes(self):
        workbook = Workbook()
        paper_sheet = workbook.active
        paper_sheet.title = 'paper'
        paper_sheet.append(
            ['paper_id', 'doi', 'authors', 'year', 'title', 'country', 'topic', 'status', 'reviwer', 'notes']
        )
        paper_sheet.append(
            ['paper-1', '10.2000/workbook', 'A. Author, B. Author', 2024, 'Workbook Study', 'Portugal', 'IBD', 'complete', 'Rafael', 'Paper note']
        )
        paper_sheet.append(
            ['paper-2', '10.2000/skip', 'C. Author', 2023, 'Skipped Study', 'Spain', 'Control', 'needs_review', 'Rafael', 'Skip me']
        )

        group_sheet = workbook.create_sheet('groups')
        group_sheet.append(
            ['group_id', 'paper_id', 'group_name_as_written', 'condition', 'group_type', 'body_site', 'sample_size', 'age', 'women_percent', 'age2', 'where_found', 'notes']
        )
        group_sheet.append(['g1', 'paper-1', 'Cases', 'IBD', 'case', 'gut', 12, 40.5, 60, 'adult', 'Methods', 'Case group'])
        group_sheet.append(['g2', 'paper-1', 'Controls', 'Healthy', 'control', 'gut', 10, 38, 55, '', 'Methods', 'Control group'])
        group_sheet.append(['g3', 'paper-2', 'Skipped Group', 'Other', 'other', 'gut', 5, '', '', '', '', 'Should skip'])

        comparison_sheet = workbook.create_sheet('comparissons')
        comparison_sheet.append(
            ['comparison_id', 'paper_id', 'target_group_id', 'reference_group_id', 'target_condition', 'reference_condition', 'comparison_type', 'notes']
        )
        comparison_sheet.append(['c1', 'paper-1', 'g1', 'g2', 'IBD', 'Healthy', 'case_vs_control', 'Comparison note'])

        qualitative_sheet = workbook.create_sheet('qualitative_findings')
        qualitative_sheet.append(
            ['finding_id', 'paper_id', 'comparison_id', 'organism_id', 'organism_as_writiten', 'direction', 'finding_type', 'where_found', 'notes']
        )
        qualitative_sheet.append(['f1', 'paper-1', 'c1', 'o1', 'Blautia sp.', 'increased_in_target', 'relative_direction', 'Table 2', 'Finding note'])

        quantitative_sheet = workbook.create_sheet('quantitative_findings')
        quantitative_sheet.append(
            ['quant_finding_id', 'paper_id', 'group_id', 'organism_id', 'value_type', 'unit', 'value', 'where_found', 'notes']
        )
        quantitative_sheet.append(['q1', 'paper-1', 'g1', 'o1', 'relative_abundance', '%', 0.42, 'Table 3', 'Quant note'])

        diversity_sheet = workbook.create_sheet('diversity_metrics')
        diversity_sheet.append(
            ['diversity_id', 'paper_id', 'comparison_id', 'group_id', 'diversity_category', 'metric_as_written', 'value', 'unit', 'where_found', 'notes']
        )
        diversity_sheet.append(['d1', 'paper-1', '', 'g1', 'alpha', 'shannon', 3.4, '', 'Table 4', 'Alpha note'])
        diversity_sheet.append(['d2', 'paper-1', 'c1', '', 'beta', 'bray_curtis', 0.28, '', 'Figure 2', 'Beta note'])

        organism_sheet = workbook.create_sheet('organisms')
        organism_sheet.append(
            ['organism_id', 'organism_as_written', 'suggested_clean_name', 'rank_if_known', 'notes', 'ncbi_id', 'resolved']
        )
        organism_sheet.append(['o1', 'Blautia sp.', 'Blautia', 'genus', 'Organism note', 1234, 'false'])

        metadata_sheet = workbook.create_sheet('extra_metadata')
        metadata_sheet.append(['paper_id', 'group_id', 'field_name', 'value_as_written', 'unit', 'where_found', 'notes'])
        metadata_sheet.append(['paper-1', 'g1', 'bmi', '24.5', 'kg/m2', 'Table 1', 'BMI note'])

        output = BytesIO()
        workbook.save(output)
        return output.getvalue()

    def test_excel_workbook_preview_and_import_creates_related_records(self):
        preview = build_preview(
            file_name='curation.xlsx',
            content=self._build_workbook_bytes(),
            import_type='excel_workbook',
            batch_name='Workbook batch',
        )

        self.assertEqual(preview.import_type, 'excel_workbook')
        self.assertEqual(len(preview.errors), 0)
        self.assertEqual(len(preview.sections), 10)
        self.assertEqual(len(preview.skipped_rows), 2)

        batch = run_import(preview.to_dict())

        self.assertEqual(batch.status, ImportBatch.Status.COMPLETED)
        study = Study.objects.get(doi='10.2000/workbook')
        cases = Group.objects.get(study=study, name='Cases')
        controls = Group.objects.get(study=study, name='Controls')
        comparison = Comparison.objects.get(
            study=study,
            group_a=cases,
            group_b=controls,
            label='Cases vs Controls (case_vs_control)',
        )
        organism = Organism.objects.get(scientific_name='Blautia sp.')
        qualitative = QualitativeFinding.objects.get(comparison=comparison, organism=organism)
        quantitative = QuantitativeFinding.objects.get(group=cases, organism=organism)
        alpha = AlphaMetric.objects.get(group=cases, metric='shannon')
        beta = BetaMetric.objects.get(comparison=comparison, metric='bray_curtis')
        bmi_variable = MetadataVariable.objects.get(name='bmi')
        bmi_value = MetadataValue.objects.get(group=cases, variable=bmi_variable)
        age_variable = MetadataVariable.objects.get(name='age')
        age_value = MetadataValue.objects.get(group=cases, variable=age_variable)

        self.assertIn('Authors: A. Author, B. Author', study.notes)
        self.assertEqual(qualitative.direction, QualitativeFinding.Direction.ENRICHED)
        self.assertEqual(qualitative.import_batch, batch)
        self.assertEqual(quantitative.value, 0.42)
        self.assertEqual(alpha.import_batch, batch)
        self.assertEqual(beta.import_batch, batch)
        self.assertEqual(bmi_variable.value_type, MetadataVariable.ValueType.TEXT)
        self.assertEqual(bmi_value.value_text, '24.5')
        self.assertEqual(age_variable.value_type, MetadataVariable.ValueType.FLOAT)
        self.assertEqual(age_value.value_float, 40.5)
        self.assertFalse(Study.objects.filter(doi='10.2000/skip').exists())

    def test_excel_workbook_preview_reports_missing_group_reference(self):
        workbook = Workbook()
        paper_sheet = workbook.active
        paper_sheet.title = 'paper'
        paper_sheet.append(['paper_id', 'doi', 'authors', 'year', 'title', 'country', 'topic', 'status', 'reviwer', 'notes'])
        paper_sheet.append(['paper-1', '10.3000/error', '', 2024, 'Broken Workbook', '', '', 'complete', '', ''])

        comparison_sheet = workbook.create_sheet('comparissons')
        comparison_sheet.append(
            ['comparison_id', 'paper_id', 'target_group_id', 'reference_group_id', 'target_condition', 'reference_condition', 'comparison_type', 'notes']
        )
        comparison_sheet.append(['c1', 'paper-1', 'missing-a', 'missing-b', '', '', 'case_vs_control', ''])

        output = BytesIO()
        workbook.save(output)

        preview = build_preview(
            file_name='broken.xlsx',
            content=output.getvalue(),
            import_type='excel_workbook',
            batch_name='Broken workbook batch',
        )

        self.assertEqual(preview.import_type, 'excel_workbook')
        self.assertTrue(any(error['section'] == 'comparison' for error in preview.errors))
        self.assertFalse(any(section['valid_rows'] for section in preview.sections if section['import_type'] == 'comparison'))

from django.test import TestCase

from database.models import (
    AlphaMetric,
    BetaMetric,
    CoreMetadata,
    ImportBatch,
    MetadataValue,
    MetadataVariable,
    Organism,
    RelativeAssociation,
    Sample,
    Study,
)

from .services import build_preview, run_import


class ImportServiceTests(TestCase):
    def setUp(self):
        self.study = Study.objects.create(title='Study A', source_doi='10.1000/example')
        self.sample = Sample.objects.create(study=self.study, label='Cohort A')
        self.organism_a = Organism.objects.create(
            ncbi_taxonomy_id=100,
            scientific_name='Organism A',
            taxonomic_rank='species',
        )
        self.organism_b = Organism.objects.create(
            ncbi_taxonomy_id=200,
            scientific_name='Organism B',
            taxonomic_rank='species',
        )
        self.metadata_variable = MetadataVariable.objects.create(
            name='smoking_status',
            display_name='Smoking Status',
            value_type=MetadataVariable.ValueType.TEXT,
        )

    def test_study_preview_reports_duplicate_source_doi(self):
        preview = build_preview(
            file_name='studies.csv',
            content='source_doi,title\n10.1000/example,Duplicate Study\n',
            import_type='study',
            batch_name='Study batch',
        )

        self.assertEqual(preview.valid_rows, [])
        self.assertEqual(len(preview.duplicates), 1)

    def test_sample_preview_requires_existing_study(self):
        preview = build_preview(
            file_name='samples.csv',
            content='study_source_doi,label\n10.9999/missing,Cohort X\n',
            import_type='sample',
            batch_name='Sample batch',
        )

        self.assertEqual(preview.valid_rows, [])
        self.assertEqual(len(preview.errors), 1)

    def test_core_metadata_import_creates_row(self):
        preview = build_preview(
            file_name='core_metadata.csv',
            content=(
                'study_source_doi,sample_label,condition,male_percent,age_mean\n'
                '10.1000/example,Cohort A,Healthy,48.0,42.1\n'
            ),
            import_type='core_metadata',
            batch_name='Core metadata batch',
        ).to_dict()

        batch = run_import(preview)

        self.assertEqual(batch.status, ImportBatch.Status.COMPLETED)
        self.assertTrue(CoreMetadata.objects.filter(sample=self.sample, condition='Healthy').exists())

    def test_metadata_variable_preview_validates_allowed_values_json(self):
        preview = build_preview(
            file_name='metadata_variables.csv',
            content=(
                'name,display_name,value_type,allowed_values\n'
                'status,Status,text,not-json\n'
            ),
            import_type='metadata_variable',
            batch_name='Variable batch',
        )

        self.assertEqual(preview.valid_rows, [])
        self.assertEqual(len(preview.errors), 1)

    def test_metadata_value_import_sets_import_batch(self):
        preview = build_preview(
            file_name='metadata_values.csv',
            content=(
                'study_source_doi,sample_label,variable_name,value_text,raw_value\n'
                '10.1000/example,Cohort A,smoking_status,never,never\n'
            ),
            import_type='metadata_value',
            batch_name='Metadata value batch',
        ).to_dict()

        batch = run_import(preview)
        metadata_value = MetadataValue.objects.get(sample=self.sample, variable=self.metadata_variable)

        self.assertEqual(batch.status, ImportBatch.Status.COMPLETED)
        self.assertEqual(metadata_value.import_batch, batch)
        self.assertEqual(metadata_value.value_text, 'never')

    def test_relative_association_preview_canonicalizes_reverse_pairs(self):
        preview = build_preview(
            file_name='associations.csv',
            content=(
                'study_source_doi,sample_label,organism_1_taxonomy_id,organism_2_taxonomy_id,association_type,sign\n'
                '10.1000/example,Cohort A,200,100,correlation,positive\n'
            ),
            import_type='relative_association',
            batch_name='Association batch',
        )

        self.assertEqual(len(preview.valid_rows), 1)
        row = preview.valid_rows[0]
        self.assertEqual(row['organism_1_id'], self.organism_a.pk)
        self.assertEqual(row['organism_2_id'], self.organism_b.pk)

    def test_relative_association_import_creates_batch_link(self):
        preview = build_preview(
            file_name='associations.csv',
            content=(
                'study_source_doi,sample_label,organism_1_taxonomy_id,organism_2_taxonomy_id,association_type,value,sign\n'
                '10.1000/example,Cohort A,100,200,correlation,0.42,positive\n'
            ),
            import_type='relative_association',
            batch_name='Association batch',
        ).to_dict()

        batch = run_import(preview)
        association = RelativeAssociation.objects.get(sample=self.sample)

        self.assertEqual(batch.status, ImportBatch.Status.COMPLETED)
        self.assertEqual(association.import_batch, batch)
        self.assertEqual(association.organism_1, self.organism_a)

    def test_organism_import_creates_import_batch_and_records(self):
        preview = build_preview(
            file_name='organisms.csv',
            content=(
                'ncbi_taxonomy_id,scientific_name,taxonomic_rank,genus,species,notes\n'
                '101,Faecalibacterium prausnitzii,species,Faecalibacterium,prausnitzii,Important commensal\n'
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
                'study_source_doi,sample_label,metric_type,value,unit\n'
                '10.1000/example,Cohort A,shannon,3.82,\n'
            ),
            import_type='alpha_metric',
            batch_name='Alpha metric batch',
        ).to_dict()

        batch = run_import(preview)
        metric = AlphaMetric.objects.get(sample=self.sample, metric_type='shannon')

        self.assertEqual(batch.status, ImportBatch.Status.COMPLETED)
        self.assertEqual(metric.import_batch, batch)
        self.assertEqual(metric.value, 3.82)

    def test_beta_metric_preview_canonicalizes_reverse_pairs(self):
        sample_b = Sample.objects.create(study=self.study, label='Cohort B')

        preview = build_preview(
            file_name='beta_metrics.csv',
            content=(
                'study_source_doi,sample_1_label,sample_2_label,metric_type,value,unit\n'
                f'10.1000/example,{sample_b.label},{self.sample.label},bray_curtis,0.37,\n'
            ),
            import_type='beta_metric',
            batch_name='Beta metric batch',
        )

        self.assertEqual(len(preview.valid_rows), 1)
        row = preview.valid_rows[0]
        self.assertEqual(row['sample_a_id'], self.sample.pk)
        self.assertEqual(row['sample_b_id'], sample_b.pk)

    def test_beta_metric_import_sets_import_batch(self):
        sample_b = Sample.objects.create(study=self.study, label='Cohort B')

        preview = build_preview(
            file_name='beta_metrics.csv',
            content=(
                'study_source_doi,sample_1_label,sample_2_label,metric_type,value,unit\n'
                f'10.1000/example,{self.sample.label},{sample_b.label},bray_curtis,0.37,\n'
            ),
            import_type='beta_metric',
            batch_name='Beta metric batch',
        ).to_dict()

        batch = run_import(preview)
        metric = BetaMetric.objects.get(sample_a=self.sample, sample_b=sample_b, metric_type='bray_curtis')

        self.assertEqual(batch.status, ImportBatch.Status.COMPLETED)
        self.assertEqual(metric.import_batch, batch)
        self.assertEqual(metric.value, 0.37)

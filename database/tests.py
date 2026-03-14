from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse

from .models import AlphaMetric, BetaMetric, MetadataValue, MetadataVariable, Organism, RelativeAssociation, Sample, Study


class StudyModelTests(TestCase):
    def test_source_doi_must_be_unique_when_present(self):
        Study.objects.create(title='Study A', source_doi='10.1000/test')

        with self.assertRaises(IntegrityError):
            Study.objects.create(title='Study B', source_doi='10.1000/test')


class SampleModelTests(TestCase):
    def test_label_must_be_unique_within_study(self):
        study = Study.objects.create(title='Study A')
        Sample.objects.create(study=study, label='Cohort 1')

        with self.assertRaises(IntegrityError):
            Sample.objects.create(study=study, label='Cohort 1')


class RelativeAssociationModelTests(TestCase):
    def setUp(self):
        self.study = Study.objects.create(title='Study A')
        self.sample = Sample.objects.create(study=self.study, label='Cohort 1')
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

    def test_clean_rejects_self_pairs(self):
        association = RelativeAssociation(
            sample=self.sample,
            organism_1=self.organism_a,
            organism_2=self.organism_a,
            association_type='correlation',
        )

        with self.assertRaises(ValidationError):
            association.full_clean()

    def test_save_enforces_canonical_order(self):
        association = RelativeAssociation.objects.create(
            sample=self.sample,
            organism_1=self.organism_b,
            organism_2=self.organism_a,
            association_type='correlation',
        )

        self.assertEqual(association.organism_1, self.organism_a)
        self.assertEqual(association.organism_2, self.organism_b)


class MetadataValueModelTests(TestCase):
    def setUp(self):
        self.study = Study.objects.create(title='Study A')
        self.sample = Sample.objects.create(study=self.study, label='Cohort 1')

    def test_requires_exactly_one_typed_value(self):
        variable = MetadataVariable.objects.create(
            name='age',
            display_name='Age',
            value_type=MetadataVariable.ValueType.FLOAT,
        )
        metadata_value = MetadataValue(
            sample=self.sample,
            variable=variable,
            value_float=42.0,
            value_int=42,
        )

        with self.assertRaises(ValidationError):
            metadata_value.full_clean()

    def test_rejects_wrong_typed_field_for_variable(self):
        variable = MetadataVariable.objects.create(
            name='is_case',
            display_name='Is Case',
            value_type=MetadataVariable.ValueType.BOOLEAN,
        )
        metadata_value = MetadataValue(
            sample=self.sample,
            variable=variable,
            value_text='yes',
        )

        with self.assertRaises(ValidationError):
            metadata_value.full_clean()


class AlphaMetricModelTests(TestCase):
    def test_metric_type_must_be_unique_per_sample(self):
        study = Study.objects.create(title='Study A')
        sample = Sample.objects.create(study=study, label='Cohort 1')
        AlphaMetric.objects.create(sample=sample, metric_type='shannon', value=3.2)

        with self.assertRaises(IntegrityError):
            AlphaMetric.objects.create(sample=sample, metric_type='shannon', value=4.1)


class BetaMetricModelTests(TestCase):
    def setUp(self):
        self.study = Study.objects.create(title='Study A')
        self.sample_a = Sample.objects.create(study=self.study, label='Cohort 1')
        self.sample_b = Sample.objects.create(study=self.study, label='Cohort 2')

    def test_clean_rejects_self_pairs(self):
        metric = BetaMetric(
            sample_a=self.sample_a,
            sample_b=self.sample_a,
            metric_type='bray_curtis',
            value=0.3,
        )

        with self.assertRaises(ValidationError):
            metric.full_clean()

    def test_save_enforces_canonical_order(self):
        metric = BetaMetric.objects.create(
            sample_a=self.sample_b,
            sample_b=self.sample_a,
            metric_type='bray_curtis',
            value=0.3,
        )

        self.assertEqual(metric.sample_a, self.sample_a)
        self.assertEqual(metric.sample_b, self.sample_b)


class BrowserViewTests(TestCase):
    def setUp(self):
        self.study_a = Study.objects.create(
            title='Alpha Study',
            source_doi='10.1000/alpha',
            country='Portugal',
            publication_year=2023,
        )
        self.study_b = Study.objects.create(
            title='Beta Study',
            source_doi='10.1000/beta',
            country='Spain',
            publication_year=2024,
        )
        self.sample_a = Sample.objects.create(
            study=self.study_a,
            label='Cohort A',
            site='Gut',
            sample_size=40,
        )
        self.sample_b = Sample.objects.create(
            study=self.study_b,
            label='Cohort B',
            site='Oral',
            sample_size=10,
        )
        self.organism_a = Organism.objects.create(
            ncbi_taxonomy_id=111,
            scientific_name='Faecalibacterium prausnitzii',
            taxonomic_rank='species',
            genus='Faecalibacterium',
            species='prausnitzii',
        )
        self.organism_b = Organism.objects.create(
            ncbi_taxonomy_id=222,
            scientific_name='Bacteroides fragilis',
            taxonomic_rank='species',
            genus='Bacteroides',
            species='fragilis',
        )
        self.association = RelativeAssociation.objects.create(
            sample=self.sample_a,
            organism_1=self.organism_a,
            organism_2=self.organism_b,
            association_type='correlation',
            sign=RelativeAssociation.Sign.POSITIVE,
            value=0.62,
            p_value=0.01,
        )

    def test_browser_home_displays_counts(self):
        response = self.client.get(reverse('database:browser-home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Database Browser')
        self.assertContains(response, 'Relative Associations')

    def test_study_list_supports_search(self):
        response = self.client.get(reverse('database:study-list'), {'q': 'Alpha'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Alpha Study')
        self.assertNotContains(response, 'Beta Study')

    def test_sample_list_filters_by_study(self):
        response = self.client.get(reverse('database:sample-list'), {'study': self.study_a.pk})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Cohort A')
        self.assertNotContains(response, 'Cohort B')

    def test_organism_list_filters_by_rank(self):
        genus_organism = Organism.objects.create(
            ncbi_taxonomy_id=333,
            scientific_name='Bacteroides',
            taxonomic_rank='genus',
        )

        response = self.client.get(
            reverse('database:organism-list'),
            {'taxonomic_rank': 'species'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Faecalibacterium prausnitzii')
        self.assertNotContains(response, f'/browser/organisms/{genus_organism.pk}/')

    def test_association_list_filters_by_sign(self):
        RelativeAssociation.objects.create(
            sample=self.sample_b,
            organism_1=self.organism_a,
            organism_2=self.organism_b,
            association_type='correlation',
            sign=RelativeAssociation.Sign.NEGATIVE,
            value=-0.4,
        )

        response = self.client.get(
            reverse('database:relativeassociation-list'),
            {'sign': RelativeAssociation.Sign.POSITIVE},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '0.62')
        self.assertNotContains(response, '-0.4')

    def test_detail_views_render(self):
        urls = [
            reverse('database:study-detail', args=[self.study_a.pk]),
            reverse('database:sample-detail', args=[self.sample_a.pk]),
            reverse('database:organism-detail', args=[self.organism_a.pk]),
            reverse('database:relativeassociation-detail', args=[self.association.pk]),
        ]

        for url in urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)

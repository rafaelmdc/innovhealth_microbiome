from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse

from .models import Comparison, Group, MetadataValue, MetadataVariable, Taxon, QualitativeFinding, QuantitativeFinding, Study


class StudyModelTests(TestCase):
    def test_doi_must_be_unique_when_present(self):
        Study.objects.create(title='Study A', doi='10.1000/test')

        with self.assertRaises(IntegrityError):
            Study.objects.create(title='Study B', doi='10.1000/test')


class GroupModelTests(TestCase):
    def test_name_must_be_unique_within_study(self):
        study = Study.objects.create(title='Study A')
        Group.objects.create(study=study, name='Control')

        with self.assertRaises(IntegrityError):
            Group.objects.create(study=study, name='Control')


class ComparisonModelTests(TestCase):
    def setUp(self):
        self.study = Study.objects.create(title='Study A')
        self.group_a = Group.objects.create(study=self.study, name='Case')
        self.group_b = Group.objects.create(study=self.study, name='Control')

    def test_clean_rejects_identical_groups(self):
        comparison = Comparison(
            study=self.study,
            group_a=self.group_a,
            group_b=self.group_a,
            label='Case vs control',
        )

        with self.assertRaises(ValidationError):
            comparison.full_clean()

    def test_clean_rejects_groups_from_other_studies(self):
        other_study = Study.objects.create(title='Study B')
        other_group = Group.objects.create(study=other_study, name='External')
        comparison = Comparison(
            study=self.study,
            group_a=self.group_a,
            group_b=other_group,
            label='Mixed study comparison',
        )

        with self.assertRaises(ValidationError):
            comparison.full_clean()


class MetadataValueModelTests(TestCase):
    def setUp(self):
        self.study = Study.objects.create(title='Study A')
        self.group = Group.objects.create(study=self.study, name='Control')

    def test_requires_exactly_one_typed_value(self):
        variable = MetadataVariable.objects.create(
            name='age_mean',
            display_name='Age Mean',
            value_type=MetadataVariable.ValueType.FLOAT,
        )
        metadata_value = MetadataValue(
            group=self.group,
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
            group=self.group,
            variable=variable,
            value_text='yes',
        )

        with self.assertRaises(ValidationError):
            metadata_value.full_clean()


class BrowserViewTests(TestCase):
    def setUp(self):
        self.study_a = Study.objects.create(
            title='Alpha Study',
            doi='10.1000/alpha',
            country='Portugal',
            year=2023,
        )
        self.study_b = Study.objects.create(
            title='Beta Study',
            doi='10.1000/beta',
            country='Spain',
            year=2024,
        )
        self.group_a = Group.objects.create(
            study=self.study_a,
            name='Case',
            condition='Disease',
            site='Gut',
            sample_size=40,
        )
        self.group_b = Group.objects.create(
            study=self.study_b,
            name='Control',
            condition='Healthy',
            site='Oral',
            sample_size=10,
        )
        self.comparison = Comparison.objects.create(
            study=self.study_a,
            group_a=self.group_a,
            group_b=Group.objects.create(study=self.study_a, name='Reference'),
            label='Case vs reference',
        )
        self.taxon = Taxon.objects.create(
            ncbi_taxonomy_id=111,
            scientific_name='Faecalibacterium prausnitzii',
            rank='species',
        )
        self.qualitative_finding = QualitativeFinding.objects.create(
            comparison=self.comparison,
            taxon=self.taxon,
            direction=QualitativeFinding.Direction.ENRICHED,
            source='Table 2',
        )
        self.quantitative_finding = QuantitativeFinding.objects.create(
            group=self.group_a,
            taxon=self.taxon,
            value_type=QuantitativeFinding.ValueType.RELATIVE_ABUNDANCE,
            value=0.62,
            source='Table 3',
        )

    def test_browser_home_displays_new_cards(self):
        response = self.client.get(reverse('database:browser-home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Database Browser')
        self.assertContains(response, 'Groups')
        self.assertContains(response, 'Qualitative Findings')

    def test_study_list_supports_search(self):
        response = self.client.get(reverse('database:study-list'), {'q': 'Alpha'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Alpha Study')
        self.assertNotContains(response, 'Beta Study')

    def test_group_list_filters_by_study(self):
        response = self.client.get(reverse('database:group-list'), {'study': self.study_a.pk})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Case')
        self.assertNotContains(response, 'Control')

    def test_taxon_list_filters_by_rank(self):
        genus_taxon = Taxon.objects.create(
            scientific_name='Bacteroides',
            rank='genus',
        )

        response = self.client.get(
            reverse('database:taxon-list'),
            {'rank': 'species'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Faecalibacterium prausnitzii')
        self.assertNotContains(response, f'/browser/taxa/{genus_taxon.pk}/')

    def test_qualitative_finding_list_filters_by_direction(self):
        QualitativeFinding.objects.create(
            comparison=self.comparison,
            taxon=Taxon.objects.create(scientific_name='Roseburia intestinalis', rank='species'),
            direction=QualitativeFinding.Direction.DEPLETED,
            source='Supplementary Table S4',
        )

        response = self.client.get(
            reverse('database:qualitativefinding-list'),
            {'direction': QualitativeFinding.Direction.ENRICHED},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Faecalibacterium prausnitzii')
        self.assertNotContains(response, 'Roseburia intestinalis')

    def test_quantitative_finding_list_filters_by_value_type(self):
        response = self.client.get(
            reverse('database:quantitativefinding-list'),
            {'value_type': QuantitativeFinding.ValueType.RELATIVE_ABUNDANCE},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '0.62')

    def test_detail_views_render(self):
        urls = [
            reverse('database:study-detail', args=[self.study_a.pk]),
            reverse('database:group-detail', args=[self.group_a.pk]),
            reverse('database:comparison-detail', args=[self.comparison.pk]),
            reverse('database:taxon-detail', args=[self.taxon.pk]),
            reverse('database:qualitativefinding-detail', args=[self.qualitative_finding.pk]),
            reverse('database:quantitativefinding-detail', args=[self.quantitative_finding.pk]),
        ]

        for url in urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)

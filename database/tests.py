from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse

from .models import Comparison, Group, MetadataValue, MetadataVariable, Taxon, TaxonClosure, QualitativeFinding, QuantitativeFinding, Study


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

    def _attach_taxon_to_branch(self, branch, leaf, *, depth=1):
        TaxonClosure.objects.create(ancestor=branch, descendant=branch, depth=0)
        TaxonClosure.objects.create(ancestor=leaf, descendant=leaf, depth=0)
        TaxonClosure.objects.create(ancestor=branch, descendant=leaf, depth=depth)

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

    def test_comparison_list_filters_supporting_comparisons(self):
        branch = Taxon.objects.create(scientific_name='Faecalibacterium', rank='genus')
        self._attach_taxon_to_branch(branch, self.taxon)

        disease_group_b = Group.objects.create(
            study=self.study_a,
            name='Case B',
            condition='Disease',
        )
        disease_reference_b = Group.objects.create(study=self.study_a, name='Reference B')
        comparison_other_direction = Comparison.objects.create(
            study=self.study_a,
            group_a=disease_group_b,
            group_b=disease_reference_b,
            label='Case B vs reference',
        )
        QualitativeFinding.objects.create(
            comparison=comparison_other_direction,
            taxon=self.taxon,
            direction=QualitativeFinding.Direction.DEPLETED,
            source='Table 4',
        )

        outside_taxon = Taxon.objects.create(
            scientific_name='Bacteroides fragilis',
            rank='species',
        )
        TaxonClosure.objects.create(ancestor=outside_taxon, descendant=outside_taxon, depth=0)
        disease_group_c = Group.objects.create(
            study=self.study_a,
            name='Case C',
            condition='Disease',
        )
        disease_reference_c = Group.objects.create(study=self.study_a, name='Reference C')
        comparison_other_taxon = Comparison.objects.create(
            study=self.study_a,
            group_a=disease_group_c,
            group_b=disease_reference_c,
            label='Case C vs reference',
        )
        QualitativeFinding.objects.create(
            comparison=comparison_other_taxon,
            taxon=outside_taxon,
            direction=QualitativeFinding.Direction.ENRICHED,
            source='Table 5',
        )

        response = self.client.get(
            reverse('database:comparison-list'),
            {
                'disease_condition': 'Disease',
                'taxon_branch': branch.pk,
                'finding_direction': 'enriched',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Case vs reference')
        self.assertNotContains(response, 'Case B vs reference')
        self.assertNotContains(response, 'Case C vs reference')

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
        self.assertEqual(response.context['page_obj'].paginator.count, 1)
        self.assertEqual(
            [finding.taxon.scientific_name for finding in response.context['findings']],
            ['Faecalibacterium prausnitzii'],
        )

    def test_qualitative_finding_list_filters_supporting_findings(self):
        branch = Taxon.objects.create(scientific_name='Faecalibacterium', rank='genus')
        self._attach_taxon_to_branch(branch, self.taxon)

        disease_reference_b = Group.objects.create(study=self.study_a, name='Reference B')
        comparison_other_direction = Comparison.objects.create(
            study=self.study_a,
            group_a=self.group_a,
            group_b=disease_reference_b,
            label='Case vs reference B',
        )
        QualitativeFinding.objects.create(
            comparison=comparison_other_direction,
            taxon=self.taxon,
            direction=QualitativeFinding.Direction.DEPLETED,
            source='Table 4',
        )

        outside_taxon = Taxon.objects.create(
            scientific_name='Bacteroides fragilis',
            rank='species',
        )
        TaxonClosure.objects.create(ancestor=outside_taxon, descendant=outside_taxon, depth=0)
        disease_reference_c = Group.objects.create(study=self.study_a, name='Reference C')
        comparison_other_taxon = Comparison.objects.create(
            study=self.study_a,
            group_a=self.group_a,
            group_b=disease_reference_c,
            label='Case vs reference C',
        )
        QualitativeFinding.objects.create(
            comparison=comparison_other_taxon,
            taxon=outside_taxon,
            direction=QualitativeFinding.Direction.ENRICHED,
            source='Table 5',
        )

        response = self.client.get(
            reverse('database:qualitativefinding-list'),
            {
                'disease_condition': 'Disease',
                'branch': branch.pk,
                'finding_direction': 'enriched',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['page_obj'].paginator.count, 1)
        self.assertEqual(
            [finding.taxon.scientific_name for finding in response.context['findings']],
            ['Faecalibacterium prausnitzii'],
        )
        self.assertEqual(
            [finding.comparison.label for finding in response.context['findings']],
            ['Case vs reference'],
        )

    def test_quantitative_finding_list_filters_by_value_type(self):
        response = self.client.get(
            reverse('database:quantitativefinding-list'),
            {'value_type': QuantitativeFinding.ValueType.RELATIVE_ABUNDANCE},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '0.62')

    def test_qualitative_finding_list_filters_by_taxonomic_branch(self):
        branch = Taxon.objects.create(scientific_name='Firmicutes', rank='phylum')
        outside_taxon = Taxon.objects.create(scientific_name='Bacteroides fragilis', rank='species')
        self._attach_taxon_to_branch(branch, self.taxon)
        TaxonClosure.objects.create(ancestor=outside_taxon, descendant=outside_taxon, depth=0)
        QualitativeFinding.objects.create(
            comparison=self.comparison,
            taxon=outside_taxon,
            direction=QualitativeFinding.Direction.DEPLETED,
            source='Table 4',
        )

        response = self.client.get(
            reverse('database:qualitativefinding-list'),
            {'branch': branch.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['page_obj'].paginator.count, 1)
        self.assertEqual(
            [finding.taxon.scientific_name for finding in response.context['findings']],
            ['Faecalibacterium prausnitzii'],
        )

    def test_quantitative_finding_list_filters_by_taxonomic_branch(self):
        branch = Taxon.objects.create(scientific_name='Firmicutes', rank='phylum')
        outside_taxon = Taxon.objects.create(scientific_name='Bacteroides fragilis', rank='species')
        self._attach_taxon_to_branch(branch, self.taxon)
        TaxonClosure.objects.create(ancestor=outside_taxon, descendant=outside_taxon, depth=0)
        QuantitativeFinding.objects.create(
            group=self.group_a,
            taxon=outside_taxon,
            value_type=QuantitativeFinding.ValueType.RELATIVE_ABUNDANCE,
            value=0.12,
            source='Table 5',
        )

        response = self.client.get(
            reverse('database:quantitativefinding-list'),
            {'branch': branch.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['page_obj'].paginator.count, 1)
        self.assertEqual(
            [finding.taxon.scientific_name for finding in response.context['findings']],
            ['Faecalibacterium prausnitzii'],
        )

    def test_taxon_detail_shows_subtree_context(self):
        branch = Taxon.objects.create(
            scientific_name='Faecalibacterium',
            rank='genus',
        )
        child_taxon = Taxon.objects.create(
            scientific_name='Faecalibacterium prausnitzii',
            rank='species',
            parent=branch,
        )
        self._attach_taxon_to_branch(branch, child_taxon)

        response = self.client.get(reverse('database:taxon-detail', args=[branch.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Immediate Children')
        self.assertContains(response, 'Descendants')
        self.assertContains(response, 'Faecalibacterium prausnitzii')

    def test_taxon_detail_lineage_starts_at_cellular_root_when_present(self):
        root_taxon = Taxon.objects.create(
            scientific_name='root',
            rank='no rank',
        )
        cellular_root = Taxon.objects.create(
            scientific_name='cellular organisms',
            rank='cellular root',
            parent=root_taxon,
        )
        branch = Taxon.objects.create(
            scientific_name='Bacteria',
            rank='domain',
            parent=cellular_root,
        )
        self.taxon.parent = branch
        self.taxon.save(update_fields=['parent'])
        TaxonClosure.objects.create(ancestor=root_taxon, descendant=root_taxon, depth=0)
        TaxonClosure.objects.create(ancestor=cellular_root, descendant=cellular_root, depth=0)
        TaxonClosure.objects.create(ancestor=branch, descendant=branch, depth=0)
        TaxonClosure.objects.create(ancestor=self.taxon, descendant=self.taxon, depth=0)
        TaxonClosure.objects.create(ancestor=root_taxon, descendant=cellular_root, depth=1)
        TaxonClosure.objects.create(ancestor=root_taxon, descendant=branch, depth=2)
        TaxonClosure.objects.create(ancestor=root_taxon, descendant=self.taxon, depth=3)
        TaxonClosure.objects.create(ancestor=cellular_root, descendant=branch, depth=1)
        TaxonClosure.objects.create(ancestor=cellular_root, descendant=self.taxon, depth=2)
        TaxonClosure.objects.create(ancestor=branch, descendant=self.taxon, depth=1)

        response = self.client.get(reverse('database:taxon-detail', args=[self.taxon.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'cellular organisms')
        self.assertNotContains(response, '>root<', html=True)

    def test_taxon_list_shows_selected_branch_context(self):
        branch = Taxon.objects.create(
            scientific_name='Faecalibacterium',
            rank='genus',
        )
        child_taxon = Taxon.objects.create(
            scientific_name='Faecalibacterium duncaniae',
            rank='species',
            parent=branch,
        )
        self._attach_taxon_to_branch(branch, child_taxon)

        response = self.client.get(reverse('database:taxon-list'), {'branch': branch.pk})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Subtree View')
        self.assertContains(response, 'Branch detail')
        self.assertContains(response, 'Branch qualitative findings')
        self.assertContains(response, f'?branch={child_taxon.pk}')

    def test_taxon_detail_shows_subtree_navigation_and_branch_counts(self):
        branch = Taxon.objects.create(
            scientific_name='Faecalibacterium',
            rank='genus',
        )
        child_taxon = Taxon.objects.create(
            scientific_name='Faecalibacterium child',
            rank='species',
            parent=branch,
        )
        self.taxon.parent = branch
        self.taxon.save(update_fields=['parent'])
        self._attach_taxon_to_branch(branch, self.taxon)
        TaxonClosure.objects.create(ancestor=child_taxon, descendant=child_taxon, depth=0)
        TaxonClosure.objects.create(ancestor=branch, descendant=child_taxon, depth=1)

        response = self.client.get(reverse('database:taxon-detail', args=[self.taxon.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Explore Subtrees')
        self.assertContains(response, 'Parent subtree: Faecalibacterium')
        self.assertContains(response, 'Current subtree: Faecalibacterium prausnitzii')
        self.assertContains(response, 'Open subtree')
        self.assertContains(response, 'Branch qualitative findings (1)')
        self.assertContains(response, 'Branch quantitative findings (1)')

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

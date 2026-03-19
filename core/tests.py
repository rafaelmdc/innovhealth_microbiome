from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from database.models import Comparison, Group, QualitativeFinding, QuantitativeFinding, Study, Taxon, TaxonClosure


class HomeViewTests(TestCase):
    def setUp(self):
        study = Study.objects.create(title='Study A')
        group_a = Group.objects.create(study=study, name='Case')
        group_b = Group.objects.create(study=study, name='Control')
        taxon = Taxon.objects.create(
            ncbi_taxonomy_id=101,
            scientific_name='Taxon A',
            rank='species',
        )
        comparison = Comparison.objects.create(
            study=study,
            group_a=group_a,
            group_b=group_b,
            label='Case vs control',
        )
        QualitativeFinding.objects.create(
            comparison=comparison,
            taxon=taxon,
            direction=QualitativeFinding.Direction.ENRICHED,
            source='Results 3.2',
        )
        QuantitativeFinding.objects.create(
            group=group_a,
            taxon=taxon,
            value_type=QuantitativeFinding.ValueType.RELATIVE_ABUNDANCE,
            value=1.5,
            source='Table 2',
        )

    def test_home_page_renders_counts_and_navigation(self):
        response = self.client.get(reverse('core:home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Microbiome Interaction Network Database')
        self.assertContains(response, 'Groups')
        self.assertContains(response, 'Comparisons')
        self.assertContains(response, 'Qualitative')
        self.assertContains(response, reverse('database:browser-home'))
        self.assertContains(response, reverse('core:graph'))
        self.assertContains(response, reverse('core:staff-home'))


class GraphViewTests(TestCase):
    def setUp(self):
        self.study_a = Study.objects.create(title='Study A')
        self.study_b = Study.objects.create(title='Study B')
        self.group_a = Group.objects.create(study=self.study_a, name='Case')
        self.group_b = Group.objects.create(study=self.study_a, name='Control')
        self.group_c = Group.objects.create(study=self.study_b, name='Validation')
        self.group_d = Group.objects.create(study=self.study_b, name='Reference')
        self.comparison_a = Comparison.objects.create(
            study=self.study_a,
            group_a=self.group_a,
            group_b=self.group_b,
            label='Case vs control',
        )
        self.comparison_b = Comparison.objects.create(
            study=self.study_b,
            group_a=self.group_c,
            group_b=self.group_d,
            label='Validation vs reference',
        )
        self.organism_a = Taxon.objects.create(
            ncbi_taxonomy_id=101,
            scientific_name='Faecalibacterium prausnitzii',
            rank='species',
        )
        self.organism_a_genus = Taxon.objects.create(
            ncbi_taxonomy_id=100,
            scientific_name='Faecalibacterium',
            rank='genus',
        )
        self.organism_a.parent = self.organism_a_genus
        self.organism_a.save(update_fields=['parent'])
        self.organism_b = Taxon.objects.create(
            ncbi_taxonomy_id=202,
            scientific_name='Bacteroides fragilis',
            rank='species',
        )
        self.organism_b_genus = Taxon.objects.create(
            ncbi_taxonomy_id=200,
            scientific_name='Bacteroides',
            rank='genus',
        )
        self.organism_b.parent = self.organism_b_genus
        self.organism_b.save(update_fields=['parent'])
        self.organism_c = Taxon.objects.create(
            ncbi_taxonomy_id=303,
            scientific_name='Roseburia intestinalis',
            rank='species',
        )
        self.organism_c_genus = Taxon.objects.create(
            ncbi_taxonomy_id=300,
            scientific_name='Roseburia',
            rank='genus',
        )
        self.organism_c.parent = self.organism_c_genus
        self.organism_c.save(update_fields=['parent'])
        self.family = Taxon.objects.create(
            ncbi_taxonomy_id=999,
            scientific_name='Ruminococcaceae',
            rank='family',
        )
        self.organism_a_genus.parent = self.family
        self.organism_a_genus.save(update_fields=['parent'])
        self.organism_c_genus.parent = self.family
        self.organism_c_genus.save(update_fields=['parent'])
        self._attach_lineage(self.family, self.organism_a_genus, self.organism_a)
        self._attach_lineage(self.family, self.organism_c_genus, self.organism_c)
        self._attach_lineage(self.organism_b_genus, self.organism_b)
        QualitativeFinding.objects.create(
            comparison=self.comparison_a,
            taxon=self.organism_a,
            direction=QualitativeFinding.Direction.ENRICHED,
            source='Table 2',
        )
        QualitativeFinding.objects.create(
            comparison=self.comparison_a,
            taxon=self.organism_b,
            direction=QualitativeFinding.Direction.DEPLETED,
            source='Table 2',
        )
        QualitativeFinding.objects.create(
            comparison=self.comparison_b,
            taxon=self.organism_c,
            direction=QualitativeFinding.Direction.ENRICHED,
            source='Table 4',
        )

    def _attach_lineage(self, *taxa):
        for depth, ancestor in enumerate(reversed(taxa)):
            TaxonClosure.objects.get_or_create(
                ancestor=ancestor,
                descendant=taxa[-1],
                defaults={'depth': len(taxa) - depth - 1},
            )
        for taxon in taxa:
            TaxonClosure.objects.get_or_create(
                ancestor=taxon,
                descendant=taxon,
                defaults={'depth': 0},
            )
        for descendant_index, descendant in enumerate(taxa[1:], start=1):
            for ancestor_index, ancestor in enumerate(taxa[:descendant_index]):
                TaxonClosure.objects.get_or_create(
                    ancestor=ancestor,
                    descendant=descendant,
                    defaults={'depth': descendant_index - ancestor_index},
                )

    def test_graph_page_renders_summary(self):
        response = self.client.get(reverse('core:graph'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Disease Network')
        self.assertEqual(response.context['graph_data']['summary']['disease_count'], 2)
        self.assertEqual(response.context['graph_data']['summary']['taxon_count'], 3)
        self.assertEqual(response.context['graph_data']['summary']['enriched_taxon_count'], 2)
        self.assertEqual(response.context['graph_data']['summary']['depleted_taxon_count'], 1)
        self.assertEqual(response.context['graph_data']['summary']['edge_count'], 3)

    def test_graph_page_filters_by_direction(self):
        response = self.client.get(
            reverse('core:graph'),
            {'direction': QualitativeFinding.Direction.ENRICHED},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['graph_data']['summary']['edge_count'], 2)
        self.assertEqual(response.context['graph_data']['summary']['finding_count'], 2)
        self.assertEqual(response.context['graph_data']['summary']['enriched_taxon_count'], 2)
        self.assertEqual(response.context['graph_data']['summary']['depleted_taxon_count'], 0)

    def test_graph_page_groups_findings_by_rank(self):
        response = self.client.get(reverse('core:graph'), {'group_rank': 'genus'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['graph_data']['summary']['grouping_rank'], 'genus')
        self.assertEqual(response.context['graph_data']['summary']['taxon_count'], 3)
        node_labels = {node['data']['label'] for node in response.context['graph_data']['nodes'] if node['data']['node_type'] == 'taxon'}
        self.assertIn('Faecalibacterium', node_labels)
        self.assertIn('Bacteroides', node_labels)
        self.assertIn('Roseburia', node_labels)
        self.assertNotIn('Faecalibacterium prausnitzii', node_labels)

    def test_graph_page_filters_by_taxonomic_branch(self):
        response = self.client.get(reverse('core:graph'), {'branch': self.family.pk, 'group_rank': 'genus'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['graph_data']['summary']['edge_count'], 2)
        node_labels = {node['data']['label'] for node in response.context['graph_data']['nodes'] if node['data']['node_type'] == 'taxon'}
        self.assertIn('Faecalibacterium', node_labels)
        self.assertIn('Roseburia', node_labels)
        self.assertNotIn('Bacteroides', node_labels)

    def test_graph_page_reports_skipped_rollups_when_rank_is_missing(self):
        response = self.client.get(reverse('core:graph'), {'group_rank': 'phylum'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['graph_data']['summary']['skipped_rollup_count'], 3)
        self.assertContains(response, '3 findings omitted because no ancestor exists at the selected rank.')


class StaffHomeViewTests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()
        self.staff_user = self.user_model.objects.create_user(
            username='staff',
            password='testpass123',
            is_staff=True,
        )
        self.normal_user = self.user_model.objects.create_user(
            username='normal',
            password='testpass123',
            is_staff=False,
        )

    def test_staff_home_redirects_anonymous_users_to_login(self):
        response = self.client.get(reverse('core:staff-home'))

        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin/login/', response['Location'])

    def test_staff_home_renders_for_staff_user(self):
        self.client.login(username='staff', password='testpass123')

        response = self.client.get(reverse('core:staff-home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Staff Workspace')
        self.assertContains(response, reverse('imports:upload'))
        self.assertContains(response, reverse('admin:index'))
        self.assertContains(response, reverse('core:model-diagram'))

    def test_staff_home_is_not_available_to_non_staff_users(self):
        self.client.login(username='normal', password='testpass123')

        response = self.client.get(reverse('core:staff-home'))

        self.assertEqual(response.status_code, 404)

    def test_model_diagram_redirects_anonymous_users_to_login(self):
        response = self.client.get(reverse('core:model-diagram'))

        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin/login/', response['Location'])

    def test_model_diagram_renders_for_staff_user(self):
        self.client.login(username='staff', password='testpass123')

        response = self.client.get(reverse('core:model-diagram'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Model Diagram')

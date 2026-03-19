from django.db.models import Q
from django.views.generic import DetailView, ListView, TemplateView

from .models import (
    Comparison,
    Group,
    QualitativeFinding,
    QuantitativeFinding,
    Study,
    Taxon,
    TaxonClosure,
)


class BrowserListView(ListView):
    paginate_by = 20
    ordering_map = {}
    default_ordering = None
    search_fields = ()

    def get_search_query(self):
        return self.request.GET.get('q', '').strip()

    def get_ordering(self):
        requested_ordering = self.request.GET.get('order_by', '').strip()
        if requested_ordering in self.ordering_map:
            return self.ordering_map[requested_ordering]
        return self.default_ordering

    def apply_search(self, queryset):
        query = self.get_search_query()
        if not query or not self.search_fields:
            return queryset

        search_filter = Q()
        for field_name in self.search_fields:
            search_filter |= Q(**{f'{field_name}__icontains': query})
        return queryset.filter(search_filter)

    def apply_filters(self, queryset):
        return queryset

    def get_queryset(self):
        queryset = super().get_queryset()
        queryset = self.apply_search(queryset)
        queryset = self.apply_filters(queryset)
        ordering = self.get_ordering()
        if ordering:
            queryset = queryset.order_by(*ordering)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_query'] = self.get_search_query()
        context['current_order_by'] = self.request.GET.get('order_by', '').strip()
        context['ordering_options'] = self.ordering_map.items()
        return context


class BrowserHomeView(TemplateView):
    template_name = 'database/browser_home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['cards'] = [
            {
                'title': 'Studies',
                'count': Study.objects.count(),
                'description': 'Browse paper-level records and linked groups.',
                'url_name': 'database:study-list',
            },
            {
                'title': 'Groups',
                'count': Group.objects.count(),
                'description': 'Inspect study arms, cohorts, conditions, and metadata.',
                'url_name': 'database:group-list',
            },
            {
                'title': 'Comparisons',
                'count': Comparison.objects.count(),
                'description': 'Review directional study comparisons between groups.',
                'url_name': 'database:comparison-list',
            },
            {
                'title': 'Taxa',
                'count': Taxon.objects.count(),
                'description': 'Search taxa by name, rank, lineage branch, or taxonomy identifier.',
                'url_name': 'database:taxon-list',
            },
            {
                'title': 'Qualitative Findings',
                'count': QualitativeFinding.objects.count(),
                'description': 'Explore enriched and depleted taxa by comparison.',
                'url_name': 'database:qualitativefinding-list',
            },
            {
                'title': 'Quantitative Findings',
                'count': QuantitativeFinding.objects.count(),
                'description': 'Inspect per-group abundance values for individual taxa.',
                'url_name': 'database:quantitativefinding-list',
            },
        ]
        return context


class StudyListView(BrowserListView):
    model = Study
    template_name = 'database/study_list.html'
    context_object_name = 'studies'
    search_fields = ('title', 'doi', 'country', 'journal')
    ordering_map = {
        'title': ('title',),
        '-title': ('-title',),
        'year': ('year', 'title'),
        '-year': ('-year', 'title'),
        'created_at': ('created_at',),
        '-created_at': ('-created_at',),
    }
    default_ordering = ('title',)

    def apply_filters(self, queryset):
        country = self.request.GET.get('country', '').strip()
        year = self.request.GET.get('year', '').strip()
        if country:
            queryset = queryset.filter(country__icontains=country)
        if year:
            queryset = queryset.filter(year=year)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_country'] = self.request.GET.get('country', '').strip()
        context['current_year'] = self.request.GET.get('year', '').strip()
        context['years'] = [
            value
            for value in Study.objects.order_by('-year').values_list('year', flat=True).distinct()
            if value is not None
        ]
        return context


class StudyDetailView(DetailView):
    model = Study
    template_name = 'database/study_detail.html'
    context_object_name = 'study'

    def get_queryset(self):
        return Study.objects.prefetch_related('groups', 'comparisons__group_a', 'comparisons__group_b')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        study = self.object
        context['qualitative_count'] = QualitativeFinding.objects.filter(comparison__study=study).count()
        context['quantitative_count'] = QuantitativeFinding.objects.filter(group__study=study).count()
        return context


class GroupListView(BrowserListView):
    model = Group
    template_name = 'database/group_list.html'
    context_object_name = 'groups'
    search_fields = ('name', 'condition', 'cohort', 'site', 'study__title')
    ordering_map = {
        'name': ('name',),
        '-name': ('-name',),
        'study': ('study__title', 'name'),
        '-study': ('-study__title', 'name'),
        'sample_size': ('sample_size', 'name'),
        '-sample_size': ('-sample_size', 'name'),
        'created_at': ('created_at',),
        '-created_at': ('-created_at',),
    }
    default_ordering = ('study__title', 'name')

    def get_queryset(self):
        return super().get_queryset().select_related('study')

    def apply_filters(self, queryset):
        study_id = self.request.GET.get('study', '').strip()
        condition = self.request.GET.get('condition', '').strip()
        if study_id:
            queryset = queryset.filter(study_id=study_id)
        if condition:
            queryset = queryset.filter(condition__icontains=condition)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_study'] = self.request.GET.get('study', '').strip()
        context['current_condition'] = self.request.GET.get('condition', '').strip()
        context['studies'] = Study.objects.order_by('title')
        return context


class GroupDetailView(DetailView):
    model = Group
    template_name = 'database/group_detail.html'
    context_object_name = 'group'

    def get_queryset(self):
        return (
            Group.objects.select_related('study')
            .prefetch_related(
                'metadata_values__variable',
                'quantitative_findings__taxon',
                'alpha_metrics',
                'comparisons_as_a__group_b',
                'comparisons_as_b__group_a',
            )
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        group = self.object
        context['comparisons'] = (
            Comparison.objects.filter(Q(group_a=group) | Q(group_b=group))
            .select_related('group_a', 'group_b', 'study')
            .order_by('label')
        )
        return context


class ComparisonListView(BrowserListView):
    model = Comparison
    template_name = 'database/comparison_list.html'
    context_object_name = 'comparisons'
    search_fields = ('label', 'study__title', 'group_a__name', 'group_b__name')
    ordering_map = {
        'label': ('label',),
        '-label': ('-label',),
        'study': ('study__title', 'label'),
        '-study': ('-study__title', 'label'),
        'created_at': ('created_at',),
        '-created_at': ('-created_at',),
    }
    default_ordering = ('study__title', 'label')

    def get_queryset(self):
        return super().get_queryset().select_related('study', 'group_a', 'group_b')

    def apply_filters(self, queryset):
        study_id = self.request.GET.get('study', '').strip()
        if study_id:
            queryset = queryset.filter(study_id=study_id)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_study'] = self.request.GET.get('study', '').strip()
        context['studies'] = Study.objects.order_by('title')
        return context


class ComparisonDetailView(DetailView):
    model = Comparison
    template_name = 'database/comparison_detail.html'
    context_object_name = 'comparison'

    def get_queryset(self):
        return (
            Comparison.objects.select_related('study', 'group_a', 'group_b')
            .prefetch_related('qualitative_findings__taxon', 'beta_metrics')
        )


class TaxonListView(BrowserListView):
    model = Taxon
    template_name = 'database/organism_list.html'
    context_object_name = 'taxa'
    search_fields = ('scientific_name', 'rank')
    ordering_map = {
        'scientific_name': ('scientific_name',),
        '-scientific_name': ('-scientific_name',),
        'ncbi_taxonomy_id': ('ncbi_taxonomy_id',),
        '-ncbi_taxonomy_id': ('-ncbi_taxonomy_id',),
        'rank': ('rank', 'scientific_name'),
        '-rank': ('-rank', 'scientific_name'),
    }
    default_ordering = ('scientific_name',)

    def get_queryset(self):
        return super().get_queryset().select_related('parent')

    def apply_filters(self, queryset):
        rank = self.request.GET.get('rank', '').strip()
        branch_id = self.request.GET.get('branch', '').strip()
        if rank:
            queryset = queryset.filter(rank=rank)
        if branch_id:
            queryset = queryset.filter(
                closure_ancestors__ancestor_id=branch_id,
            ).distinct()
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        current_rank = self.request.GET.get('rank', '').strip()
        current_branch = self.request.GET.get('branch', '').strip()
        selected_branch = None
        selected_branch_lineage = []
        selected_branch_children = []
        selected_branch_descendant_count = 0

        if current_branch:
            selected_branch = Taxon.objects.select_related('parent').filter(pk=current_branch).first()
            if selected_branch:
                selected_branch_lineage = [
                    path.ancestor
                    for path in TaxonClosure.objects.filter(descendant=selected_branch)
                    .select_related('ancestor')
                    .order_by('-depth')
                ]
                selected_branch_children = list(selected_branch.children.order_by('rank', 'scientific_name')[:12])
                selected_branch_descendant_count = TaxonClosure.objects.filter(
                    ancestor=selected_branch,
                    depth__gt=0,
                ).count()

        context['current_rank'] = current_rank
        context['current_branch'] = current_branch
        context['ranks'] = Taxon.objects.order_by('rank').values_list('rank', flat=True).distinct()
        context['branch_taxa'] = Taxon.objects.order_by('scientific_name')[:200]
        context['selected_branch_taxon'] = selected_branch
        context['selected_branch_lineage'] = selected_branch_lineage
        context['selected_branch_children'] = selected_branch_children
        context['selected_branch_descendant_count'] = selected_branch_descendant_count
        return context


class TaxonDetailView(DetailView):
    model = Taxon
    template_name = 'database/organism_detail.html'
    context_object_name = 'taxon'

    @staticmethod
    def _trim_display_lineage(lineage_nodes):
        cellular_root_index = next(
            (
                index
                for index, node in enumerate(lineage_nodes)
                if node.scientific_name.lower() == 'cellular organisms'
            ),
            None,
        )
        if cellular_root_index is not None:
            return lineage_nodes[cellular_root_index:]
        if lineage_nodes and lineage_nodes[0].scientific_name.lower() == 'root':
            return lineage_nodes[1:]
        return lineage_nodes

    def get_queryset(self):
        return Taxon.objects.select_related('parent')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        taxon = self.object
        children = taxon.children.order_by('rank', 'scientific_name')
        qualitative = QualitativeFinding.objects.filter(taxon=taxon).select_related(
            'comparison__study',
            'comparison__group_a',
            'comparison__group_b',
        )
        quantitative = QuantitativeFinding.objects.filter(taxon=taxon).select_related('group__study')
        lineage = (
            TaxonClosure.objects.filter(descendant=taxon)
            .select_related('ancestor')
            .order_by('-depth')
        )
        study_ids = {
            finding.comparison.study_id
            for finding in qualitative
        } | {
            finding.group.study_id
            for finding in quantitative
        }
        lineage_nodes = [path.ancestor for path in lineage]
        context['qualitative_count'] = qualitative.count()
        context['quantitative_count'] = quantitative.count()
        context['study_count'] = len(study_ids)
        context['lineage'] = self._trim_display_lineage(lineage_nodes)
        context['child_taxa'] = children[:12]
        context['child_taxa_count'] = children.count()
        context['descendant_count'] = TaxonClosure.objects.filter(ancestor=taxon, depth__gt=0).count()
        context['branch_qualitative_count'] = (
            QualitativeFinding.objects.filter(taxon__closure_ancestors__ancestor=taxon).distinct().count()
        )
        context['branch_quantitative_count'] = (
            QuantitativeFinding.objects.filter(taxon__closure_ancestors__ancestor=taxon).distinct().count()
        )
        context['recent_qualitative_findings'] = qualitative.order_by('comparison__label', 'direction')[:10]
        context['recent_quantitative_findings'] = quantitative.order_by('group__name', 'value_type')[:10]
        return context


class QualitativeFindingListView(BrowserListView):
    model = QualitativeFinding
    template_name = 'database/qualitativefinding_list.html'
    context_object_name = 'findings'
    search_fields = (
        'comparison__label',
        'comparison__study__title',
        'comparison__group_a__name',
        'comparison__group_b__name',
        'taxon__scientific_name',
        'source',
    )
    ordering_map = {
        'comparison': ('comparison__label', 'taxon__scientific_name'),
        '-comparison': ('-comparison__label', 'taxon__scientific_name'),
        'direction': ('direction', 'taxon__scientific_name'),
        '-direction': ('-direction', 'taxon__scientific_name'),
        'taxon': ('taxon__scientific_name',),
        '-taxon': ('-taxon__scientific_name',),
        'created_at': ('created_at',),
        '-created_at': ('-created_at',),
    }
    default_ordering = ('comparison__study__title', 'comparison__label', 'taxon__scientific_name')

    def get_queryset(self):
        return super().get_queryset().select_related(
            'comparison',
            'comparison__study',
            'comparison__group_a',
            'comparison__group_b',
            'taxon',
            'import_batch',
        )

    def apply_filters(self, queryset):
        study_id = self.request.GET.get('study', '').strip()
        direction = self.request.GET.get('direction', '').strip()
        taxon_id = self.request.GET.get('taxon', '').strip()
        branch_id = self.request.GET.get('branch', '').strip()
        if study_id:
            queryset = queryset.filter(comparison__study_id=study_id)
        if direction:
            queryset = queryset.filter(direction=direction)
        if taxon_id:
            queryset = queryset.filter(taxon_id=taxon_id)
        if branch_id:
            queryset = queryset.filter(taxon__closure_ancestors__ancestor_id=branch_id).distinct()
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_study'] = self.request.GET.get('study', '').strip()
        context['current_direction'] = self.request.GET.get('direction', '').strip()
        context['current_taxon'] = self.request.GET.get('taxon', '').strip()
        context['current_branch'] = self.request.GET.get('branch', '').strip()
        context['studies'] = Study.objects.order_by('title')
        context['direction_choices'] = QualitativeFinding.Direction.choices
        context['taxa'] = Taxon.objects.order_by('scientific_name')[:200]
        context['branch_taxa'] = Taxon.objects.order_by('scientific_name')[:200]
        return context


class QualitativeFindingDetailView(DetailView):
    model = QualitativeFinding
    template_name = 'database/qualitativefinding_detail.html'
    context_object_name = 'finding'

    def get_queryset(self):
        return QualitativeFinding.objects.select_related(
            'comparison',
            'comparison__study',
            'comparison__group_a',
            'comparison__group_b',
            'taxon',
            'import_batch',
        )


class QuantitativeFindingListView(BrowserListView):
    model = QuantitativeFinding
    template_name = 'database/quantitativefinding_list.html'
    context_object_name = 'findings'
    search_fields = (
        'group__name',
        'group__study__title',
        'taxon__scientific_name',
        'source',
    )
    ordering_map = {
        'group': ('group__name', 'taxon__scientific_name'),
        '-group': ('-group__name', 'taxon__scientific_name'),
        'taxon': ('taxon__scientific_name',),
        '-taxon': ('-taxon__scientific_name',),
        'value': ('value', 'taxon__scientific_name'),
        '-value': ('-value', 'taxon__scientific_name'),
        'created_at': ('created_at',),
        '-created_at': ('-created_at',),
    }
    default_ordering = ('group__study__title', 'group__name', 'taxon__scientific_name')

    def get_queryset(self):
        return super().get_queryset().select_related('group', 'group__study', 'taxon', 'import_batch')

    def apply_filters(self, queryset):
        study_id = self.request.GET.get('study', '').strip()
        value_type = self.request.GET.get('value_type', '').strip()
        taxon_id = self.request.GET.get('taxon', '').strip()
        branch_id = self.request.GET.get('branch', '').strip()
        if study_id:
            queryset = queryset.filter(group__study_id=study_id)
        if value_type:
            queryset = queryset.filter(value_type=value_type)
        if taxon_id:
            queryset = queryset.filter(taxon_id=taxon_id)
        if branch_id:
            queryset = queryset.filter(taxon__closure_ancestors__ancestor_id=branch_id).distinct()
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_study'] = self.request.GET.get('study', '').strip()
        context['current_value_type'] = self.request.GET.get('value_type', '').strip()
        context['current_taxon'] = self.request.GET.get('taxon', '').strip()
        context['current_branch'] = self.request.GET.get('branch', '').strip()
        context['studies'] = Study.objects.order_by('title')
        context['value_type_choices'] = QuantitativeFinding.ValueType.choices
        context['taxa'] = Taxon.objects.order_by('scientific_name')[:200]
        context['branch_taxa'] = Taxon.objects.order_by('scientific_name')[:200]
        return context


class QuantitativeFindingDetailView(DetailView):
    model = QuantitativeFinding
    template_name = 'database/quantitativefinding_detail.html'
    context_object_name = 'finding'

    def get_queryset(self):
        return QuantitativeFinding.objects.select_related('group', 'group__study', 'taxon', 'import_batch')

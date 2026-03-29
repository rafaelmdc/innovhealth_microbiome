from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import Http404, HttpResponse
from django.utils.safestring import mark_safe
from django.views import View
from django.views.generic import TemplateView

from database.models import Comparison, Group, QualitativeFinding, QuantitativeFinding, Study, Taxon

from .graph_payloads import GRAPH_GROUPING_CHOICES, build_disease_graph, build_directional_taxon_network
from .graph_renderers import (
    DIRECTIONAL_LAYOUT_CONTROL_SPECS,
    GRAPH_ENGINE_CHOICES,
    build_directional_layout_settings,
    normalize_graph_engine,
)
from .model_diagram import MODEL_DIAGRAM_CONTENT_TYPES, render_model_diagram, render_model_diagram_svg


class HomeView(TemplateView):
    template_name = 'core/home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['stats'] = [
            {
                'label': 'Studies',
                'count': Study.objects.count(),
                'url_name': 'database:study-list',
            },
            {
                'label': 'Groups',
                'count': Group.objects.count(),
                'url_name': 'database:group-list',
            },
            {
                'label': 'Comparisons',
                'count': Comparison.objects.count(),
                'url_name': 'database:comparison-list',
            },
            {
                'label': 'Taxa',
                'count': Taxon.objects.count(),
                'url_name': 'database:taxon-list',
            },
            {
                'label': 'Qualitative',
                'count': QualitativeFinding.objects.count(),
                'url_name': 'database:qualitativefinding-list',
            },
            {
                'label': 'Quantitative',
                'count': QuantitativeFinding.objects.count(),
                'url_name': 'database:quantitativefinding-list',
            },
        ]
        return context


class StaffHomeView(LoginRequiredMixin, TemplateView):
    template_name = 'core/staff_home.html'
    login_url = '/admin/login/'

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if request.user.is_authenticated and not request.user.is_staff:
            raise Http404()
        return response


class ModelDiagramView(LoginRequiredMixin, TemplateView):
    template_name = 'core/model_diagram.html'
    login_url = '/admin/login/'

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if request.user.is_authenticated and not request.user.is_staff:
            raise Http404()
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            context['diagram_svg'] = mark_safe(render_model_diagram_svg())
            context['diagram_error'] = ''
        except Exception as exc:
            context['diagram_svg'] = ''
            context['diagram_error'] = str(exc)
        return context


class ModelDiagramDownloadView(LoginRequiredMixin, View):
    login_url = '/admin/login/'

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if request.user.is_authenticated and not request.user.is_staff:
            raise Http404()
        return response

    def get(self, request, *args, **kwargs):
        output_format = kwargs['output_format']
        if output_format not in MODEL_DIAGRAM_CONTENT_TYPES:
            raise Http404()

        diagram = render_model_diagram(output_format)
        response = HttpResponse(diagram, content_type=MODEL_DIAGRAM_CONTENT_TYPES[output_format])
        response['Content-Disposition'] = f'attachment; filename="mindb-schema.{output_format}"'
        return response


class GraphView(TemplateView):
    template_name = 'core/graph.html'

    def get_grouping_rank(self):
        grouping_rank = self.request.GET.get('group_rank', '').strip() or 'leaf'
        valid_ranks = {value for value, _label in GRAPH_GROUPING_CHOICES}
        return grouping_rank if grouping_rank in valid_ranks else 'leaf'

    def get_queryset(self):
        queryset = QualitativeFinding.objects.select_related(
            'comparison',
            'comparison__study',
            'comparison__group_a',
            'comparison__group_b',
            'taxon',
        )

        study_id = self.request.GET.get('study', '').strip()
        direction = self.request.GET.get('direction', '').strip()
        disease_query = self.request.GET.get('disease', '').strip() or self.request.GET.get('comparison', '').strip()
        taxon_query = self.request.GET.get('taxon', '').strip()
        branch_id = self.request.GET.get('branch', '').strip()

        if study_id:
            queryset = queryset.filter(comparison__study_id=study_id)
        if direction:
            queryset = queryset.filter(direction=direction)
        if disease_query:
            queryset = queryset.filter(
                Q(comparison__group_a__condition__icontains=disease_query)
                | Q(comparison__group_a__name__icontains=disease_query)
                | Q(comparison__label__icontains=disease_query)
            )
        if taxon_query:
            queryset = queryset.filter(
                Q(taxon__scientific_name__icontains=taxon_query)
                | Q(taxon__rank__icontains=taxon_query)
            )
        if branch_id:
            queryset = queryset.filter(taxon__closure_ancestors__ancestor_id=branch_id).distinct()

        return queryset.order_by('comparison__label', 'taxon__scientific_name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        grouping_rank = self.get_grouping_rank()
        graph_data = build_disease_graph(self.get_queryset(), grouping_rank=grouping_rank)
        branch_id = self.request.GET.get('branch', '').strip()
        context['graph_data'] = graph_data
        context['studies'] = Study.objects.order_by('title')
        context['direction_choices'] = QualitativeFinding.Direction.choices
        context['grouping_rank_choices'] = GRAPH_GROUPING_CHOICES
        context['engine_choices'] = GRAPH_ENGINE_CHOICES
        context['branch_taxa'] = Taxon.objects.order_by('scientific_name')[:200]
        context['current_engine'] = normalize_graph_engine(self.request.GET.get('engine', '').strip() or 'cytoscape')
        context['current_study'] = self.request.GET.get('study', '').strip()
        context['current_direction'] = self.request.GET.get('direction', '').strip()
        context['current_disease'] = self.request.GET.get('disease', '').strip() or self.request.GET.get('comparison', '').strip()
        context['current_taxon'] = self.request.GET.get('taxon', '').strip()
        context['current_branch'] = branch_id
        context['current_group_rank'] = grouping_rank
        context['current_branch_taxon'] = Taxon.objects.filter(pk=branch_id).first() if branch_id else None
        return context


class DirectionalTaxonNetworkView(TemplateView):
    template_name = 'core/directional_taxon_network.html'

    def get_grouping_rank(self):
        grouping_rank = self.request.GET.get('group_rank', '').strip() or 'leaf'
        valid_ranks = {value for value, _label in GRAPH_GROUPING_CHOICES}
        return grouping_rank if grouping_rank in valid_ranks else 'leaf'

    def get_minimum_support(self):
        minimum_support = self.request.GET.get('min_support', '').strip() or '1'
        try:
            return max(int(minimum_support), 1)
        except ValueError:
            return 1

    def get_pattern_filter(self):
        pattern_filter = self.request.GET.get('pattern', '').strip() or 'all'
        return pattern_filter if pattern_filter in {'all', 'same_direction', 'opposite_direction', 'mixed'} else 'all'

    def get_queryset(self):
        queryset = QualitativeFinding.objects.select_related(
            'comparison',
            'comparison__study',
            'comparison__group_a',
            'comparison__group_b',
            'taxon',
        )

        study_id = self.request.GET.get('study', '').strip()
        disease_query = self.request.GET.get('disease', '').strip() or self.request.GET.get('comparison', '').strip()
        taxon_query = self.request.GET.get('taxon', '').strip()
        branch_id = self.request.GET.get('branch', '').strip()

        if study_id:
            queryset = queryset.filter(comparison__study_id=study_id)
        if disease_query:
            queryset = queryset.filter(
                Q(comparison__group_a__condition__icontains=disease_query)
                | Q(comparison__group_a__name__icontains=disease_query)
                | Q(comparison__label__icontains=disease_query)
            )
        if taxon_query:
            queryset = queryset.filter(
                Q(taxon__scientific_name__icontains=taxon_query)
                | Q(taxon__rank__icontains=taxon_query)
            )
        if branch_id:
            queryset = queryset.filter(taxon__closure_ancestors__ancestor_id=branch_id).distinct()

        return queryset.order_by('comparison__label', 'taxon__scientific_name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        grouping_rank = self.get_grouping_rank()
        branch_id = self.request.GET.get('branch', '').strip()
        minimum_support = self.get_minimum_support()
        pattern_filter = self.get_pattern_filter()
        current_engine = normalize_graph_engine(self.request.GET.get('engine', '').strip() or 'cytoscape')
        layout_settings = build_directional_layout_settings(self.request.GET)
        graph_data = build_directional_taxon_network(
            self.get_queryset(),
            grouping_rank=grouping_rank,
            minimum_support=minimum_support,
            pattern_filter=pattern_filter,
        )
        context['graph_data'] = graph_data
        context['studies'] = Study.objects.order_by('title')
        context['grouping_rank_choices'] = GRAPH_GROUPING_CHOICES
        context['engine_choices'] = GRAPH_ENGINE_CHOICES
        context['active_layout_controls'] = [
            {
                **spec,
                'value': layout_settings[spec['name']],
            }
            for spec in DIRECTIONAL_LAYOUT_CONTROL_SPECS[current_engine]
        ]
        context['layout_settings'] = layout_settings
        context['branch_taxa'] = Taxon.objects.order_by('scientific_name')[:200]
        context['pattern_choices'] = (
            ('all', 'All patterns'),
            ('same_direction', 'Same direction'),
            ('opposite_direction', 'Opposite direction'),
            ('mixed', 'Mixed'),
        )
        context['current_engine'] = current_engine
        context['current_study'] = self.request.GET.get('study', '').strip()
        context['current_disease'] = self.request.GET.get('disease', '').strip() or self.request.GET.get('comparison', '').strip()
        context['current_taxon'] = self.request.GET.get('taxon', '').strip()
        context['current_branch'] = branch_id
        context['current_group_rank'] = grouping_rank
        context['current_min_support'] = minimum_support
        context['current_pattern'] = pattern_filter
        context['current_branch_taxon'] = Taxon.objects.filter(pk=branch_id).first() if branch_id else None
        return context

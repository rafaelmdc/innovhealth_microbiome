from django.contrib import admin

from .models import (
    AlphaMetric,
    BetaMetric,
    Comparison,
    Group,
    ImportBatch,
    MetadataValue,
    MetadataVariable,
    QualitativeFinding,
    QuantitativeFinding,
    Study,
    Taxon,
    TaxonClosure,
    TaxonName,
)

admin.site.site_header = 'Innov Health Microbiome Admin'
admin.site.site_title = 'Innov Health Microbiome Admin'
admin.site.index_title = 'Curation Workspace'


class GroupInline(admin.TabularInline):
    model = Group
    extra = 0
    fields = ('name', 'condition', 'cohort', 'site', 'sample_size')
    show_change_link = True


class ComparisonInline(admin.TabularInline):
    model = Comparison
    extra = 0
    autocomplete_fields = ('group_a', 'group_b')
    fields = ('label', 'group_a', 'group_b')
    show_change_link = True


class MetadataValueInline(admin.TabularInline):
    model = MetadataValue
    extra = 0
    autocomplete_fields = ('variable',)
    fields = ('variable', 'value_float', 'value_int', 'value_text', 'value_bool')


class QuantitativeFindingInline(admin.TabularInline):
    model = QuantitativeFinding
    extra = 0
    autocomplete_fields = ('taxon', 'import_batch')
    fields = ('taxon', 'value_type', 'value', 'unit', 'source', 'import_batch')


class AlphaMetricInline(admin.TabularInline):
    model = AlphaMetric
    extra = 0
    autocomplete_fields = ('import_batch',)
    fields = ('metric', 'value', 'source', 'import_batch')


class QualitativeFindingInline(admin.TabularInline):
    model = QualitativeFinding
    extra = 0
    autocomplete_fields = ('taxon', 'import_batch')
    fields = ('taxon', 'direction', 'source', 'import_batch')


class BetaMetricInline(admin.TabularInline):
    model = BetaMetric
    extra = 0
    autocomplete_fields = ('import_batch',)
    fields = ('metric', 'value', 'source', 'import_batch')


@admin.register(Study)
class StudyAdmin(admin.ModelAdmin):
    list_display = ('title', 'year', 'journal', 'country', 'doi')
    list_filter = ('year', 'country', 'journal')
    search_fields = ('title', 'doi', 'journal', 'country')
    inlines = (GroupInline, ComparisonInline)


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'study', 'condition', 'cohort', 'site', 'sample_size')
    list_filter = ('study', 'condition', 'site', 'cohort')
    search_fields = ('name', 'study__title', 'condition', 'cohort', 'site')
    autocomplete_fields = ('study',)
    list_select_related = ('study',)
    inlines = (MetadataValueInline, QuantitativeFindingInline, AlphaMetricInline)


@admin.register(Comparison)
class ComparisonAdmin(admin.ModelAdmin):
    list_display = ('label', 'study', 'group_a', 'group_b')
    list_filter = ('study',)
    search_fields = ('label', 'study__title', 'group_a__name', 'group_b__name')
    autocomplete_fields = ('study', 'group_a', 'group_b')
    list_select_related = ('study', 'group_a', 'group_b')
    inlines = (QualitativeFindingInline, BetaMetricInline)


class TaxonNameInline(admin.TabularInline):
    model = TaxonName
    extra = 0
    fields = ('name', 'name_class', 'source', 'is_preferred')


class TaxonClosureDescendantInline(admin.TabularInline):
    model = TaxonClosure
    fk_name = 'ancestor'
    extra = 0
    autocomplete_fields = ('descendant',)
    fields = ('descendant', 'depth')


@admin.register(Taxon)
class TaxonAdmin(admin.ModelAdmin):
    list_display = ('scientific_name', 'ncbi_taxonomy_id', 'rank', 'parent', 'is_active')
    list_filter = ('rank', 'is_active')
    search_fields = ('scientific_name', 'ncbi_taxonomy_id', 'rank', 'names__name')
    autocomplete_fields = ('parent',)
    inlines = (TaxonNameInline, TaxonClosureDescendantInline)


@admin.register(QualitativeFinding)
class QualitativeFindingAdmin(admin.ModelAdmin):
    list_display = ('taxon', 'comparison', 'direction', 'source', 'import_batch')
    list_filter = ('direction', 'comparison__study', 'import_batch')
    search_fields = (
        'taxon__scientific_name',
        'comparison__label',
        'comparison__study__title',
        'source',
        'notes',
    )
    list_select_related = ('taxon', 'comparison__study', 'comparison__group_a', 'comparison__group_b', 'import_batch')
    autocomplete_fields = ('comparison', 'taxon', 'import_batch')


@admin.register(QuantitativeFinding)
class QuantitativeFindingAdmin(admin.ModelAdmin):
    list_display = ('taxon', 'group', 'value_type', 'value', 'source', 'import_batch')
    list_filter = ('value_type', 'group__study', 'import_batch')
    search_fields = (
        'taxon__scientific_name',
        'group__name',
        'group__study__title',
        'source',
        'notes',
    )
    list_select_related = ('taxon', 'group__study', 'import_batch')
    autocomplete_fields = ('group', 'taxon', 'import_batch')


@admin.register(AlphaMetric)
class AlphaMetricAdmin(admin.ModelAdmin):
    list_display = ('group', 'metric', 'value', 'source', 'import_batch')
    list_filter = ('metric', 'group__study', 'import_batch')
    search_fields = ('group__name', 'group__study__title', 'metric', 'source', 'notes')
    list_select_related = ('group__study', 'import_batch')
    autocomplete_fields = ('group', 'import_batch')


@admin.register(BetaMetric)
class BetaMetricAdmin(admin.ModelAdmin):
    list_display = ('comparison', 'metric', 'value', 'source', 'import_batch')
    list_filter = ('metric', 'comparison__study', 'import_batch')
    search_fields = ('comparison__label', 'comparison__study__title', 'metric', 'source', 'notes')
    list_select_related = ('comparison__study', 'import_batch')
    autocomplete_fields = ('comparison', 'import_batch')


@admin.register(MetadataVariable)
class MetadataVariableAdmin(admin.ModelAdmin):
    list_display = ('name', 'display_name', 'value_type', 'is_filterable')
    list_filter = ('value_type', 'is_filterable')
    search_fields = ('name', 'display_name')


@admin.register(MetadataValue)
class MetadataValueAdmin(admin.ModelAdmin):
    list_display = ('group', 'variable', 'typed_value', 'created_at')
    list_filter = ('variable__value_type', 'group__study')
    search_fields = (
        'group__name',
        'group__study__title',
        'variable__name',
        'variable__display_name',
    )
    list_select_related = ('group__study', 'variable')
    autocomplete_fields = ('group', 'variable')


@admin.register(ImportBatch)
class ImportBatchAdmin(admin.ModelAdmin):
    list_display = ('name', 'import_type', 'status', 'created_at', 'success_count', 'error_count')
    list_filter = ('status', 'import_type', 'created_at')
    search_fields = ('name', 'source_file', 'notes')
    change_list_template = 'admin/database/importbatch/change_list.html'

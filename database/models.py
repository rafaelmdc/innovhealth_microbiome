from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Study(TimestampedModel):
    doi = models.CharField(max_length=255, blank=True, null=True)
    title = models.CharField(max_length=500)
    journal = models.CharField(max_length=255, blank=True)
    year = models.PositiveIntegerField(blank=True, null=True, db_index=True)
    country = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['title']
        constraints = [
            models.UniqueConstraint(
                fields=['doi'],
                condition=Q(doi__isnull=False) & ~Q(doi=''),
                name='study_unique_doi_when_present',
            ),
        ]

    def __str__(self):
        if self.year:
            return f'{self.title} ({self.year})'
        return self.title


class Group(TimestampedModel):
    study = models.ForeignKey(Study, on_delete=models.CASCADE, related_name='groups')
    name = models.CharField(max_length=255)
    condition = models.CharField(max_length=255, blank=True)
    sample_size = models.PositiveIntegerField(blank=True, null=True)
    cohort = models.CharField(max_length=255, blank=True)
    site = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['study__title', 'name']
        constraints = [
            models.UniqueConstraint(
                fields=['study', 'name'],
                name='group_unique_study_name',
            ),
        ]

    def __str__(self):
        return f'{self.study}: {self.name}'


class Comparison(TimestampedModel):
    study = models.ForeignKey(Study, on_delete=models.CASCADE, related_name='comparisons')
    group_a = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name='comparisons_as_a',
    )
    group_b = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name='comparisons_as_b',
    )
    label = models.CharField(max_length=255)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['study__title', 'label']
        constraints = [
            models.UniqueConstraint(
                fields=['study', 'group_a', 'group_b', 'label'],
                name='comparison_unique_study_groups_label',
            ),
            models.CheckConstraint(
                condition=~Q(group_a=models.F('group_b')),
                name='comparison_distinct_groups',
            ),
        ]

    def __str__(self):
        return self.label

    def clean(self):
        super().clean()
        if self.group_a_id and self.group_b_id and self.group_a_id == self.group_b_id:
            raise ValidationError('Comparison groups must be different.')
        if self.study_id and self.group_a_id and self.group_a.study_id != self.study_id:
            raise ValidationError('group_a must belong to the selected study.')
        if self.study_id and self.group_b_id and self.group_b.study_id != self.study_id:
            raise ValidationError('group_b must belong to the selected study.')


class Taxon(TimestampedModel):
    scientific_name = models.CharField(max_length=255, db_index=True)
    rank = models.CharField(max_length=64, blank=True, db_index=True)
    ncbi_taxonomy_id = models.PositiveBigIntegerField(blank=True, null=True)
    parent = models.ForeignKey(
        'self',
        on_delete=models.PROTECT,
        related_name='children',
        blank=True,
        null=True,
    )
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['scientific_name']
        constraints = [
            models.UniqueConstraint(
                fields=['ncbi_taxonomy_id'],
                condition=Q(ncbi_taxonomy_id__isnull=False),
                name='taxon_unique_ncbi_taxonomy_id_when_present',
            ),
        ]
        indexes = [
            models.Index(fields=['rank', 'scientific_name'], name='taxon_rank_name_idx'),
        ]

    def __str__(self):
        return self.scientific_name


class TaxonClosure(models.Model):
    ancestor = models.ForeignKey(
        Taxon,
        on_delete=models.CASCADE,
        related_name='closure_descendants',
    )
    descendant = models.ForeignKey(
        Taxon,
        on_delete=models.CASCADE,
        related_name='closure_ancestors',
    )
    depth = models.PositiveIntegerField()

    class Meta:
        ordering = ['ancestor__scientific_name', 'depth', 'descendant__scientific_name']
        constraints = [
            models.UniqueConstraint(
                fields=['ancestor', 'descendant'],
                name='taxon_closure_unique_ancestor_descendant',
            ),
            models.CheckConstraint(
                condition=Q(depth__gte=0),
                name='taxon_closure_depth_gte_zero',
            ),
        ]
        indexes = [
            models.Index(fields=['ancestor', 'depth', 'descendant'], name='taxon_closure_anc_idx'),
            models.Index(fields=['descendant', 'depth', 'ancestor'], name='taxon_closure_desc_idx'),
        ]

    def __str__(self):
        return f'{self.ancestor} -> {self.descendant} ({self.depth})'


class TaxonName(TimestampedModel):
    class NameClass(models.TextChoices):
        SCIENTIFIC = 'scientific', 'Scientific'
        SYNONYM = 'synonym', 'Synonym'
        ALIAS = 'alias', 'Alias'
        IMPORTED_AS_WRITTEN = 'imported_as_written', 'Imported As Written'

    taxon = models.ForeignKey(
        Taxon,
        on_delete=models.CASCADE,
        related_name='names',
    )
    name = models.CharField(max_length=255, db_index=True)
    name_class = models.CharField(max_length=50, choices=NameClass.choices)
    source = models.CharField(max_length=255, blank=True)
    is_preferred = models.BooleanField(default=False)

    class Meta:
        ordering = ['name', 'taxon__scientific_name']
        constraints = [
            models.UniqueConstraint(
                fields=['taxon', 'name', 'name_class'],
                name='taxon_name_unique_taxon_name_class',
            ),
        ]
        indexes = [
            models.Index(fields=['name_class', 'name'], name='taxon_name_class_name_idx'),
        ]

    def __str__(self):
        return self.name


class ImportBatch(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        VALIDATED = 'validated', 'Validated'
        COMPLETED = 'completed', 'Completed'
        FAILED = 'failed', 'Failed'

    name = models.CharField(max_length=255)
    source_file = models.CharField(max_length=500, blank=True)
    import_type = models.CharField(max_length=100, db_index=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)
    success_count = models.PositiveIntegerField(default=0)
    error_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class QualitativeFinding(TimestampedModel):
    class Direction(models.TextChoices):
        ENRICHED = 'enriched', 'Enriched'
        DEPLETED = 'depleted', 'Depleted'
        INCREASED = 'increased', 'Increased'
        DECREASED = 'decreased', 'Decreased'

    comparison = models.ForeignKey(
        Comparison,
        on_delete=models.CASCADE,
        related_name='qualitative_findings',
    )
    taxon = models.ForeignKey(
        Taxon,
        on_delete=models.CASCADE,
        related_name='qualitative_findings',
    )
    direction = models.CharField(max_length=20, choices=Direction.choices)
    source = models.CharField(max_length=255)
    import_batch = models.ForeignKey(
        ImportBatch,
        on_delete=models.SET_NULL,
        related_name='qualitative_findings',
        blank=True,
        null=True,
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['comparison__study__title', 'comparison__label', 'taxon__scientific_name']
        constraints = [
            models.UniqueConstraint(
                fields=['comparison', 'taxon', 'direction', 'source'],
                name='qualitative_finding_unique_comparison_taxon_direction_source',
            ),
        ]

    def __str__(self):
        return f'{self.comparison} | {self.taxon} ({self.direction})'


class QuantitativeFinding(TimestampedModel):
    class ValueType(models.TextChoices):
        RELATIVE_ABUNDANCE = 'relative_abundance', 'Relative abundance'

    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name='quantitative_findings',
    )
    taxon = models.ForeignKey(
        Taxon,
        on_delete=models.CASCADE,
        related_name='quantitative_findings',
    )
    value_type = models.CharField(max_length=50, choices=ValueType.choices)
    value = models.FloatField()
    unit = models.CharField(max_length=50, blank=True)
    source = models.CharField(max_length=255)
    import_batch = models.ForeignKey(
        ImportBatch,
        on_delete=models.SET_NULL,
        related_name='quantitative_findings',
        blank=True,
        null=True,
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['group__study__title', 'group__name', 'taxon__scientific_name']
        constraints = [
            models.UniqueConstraint(
                fields=['group', 'taxon', 'value_type', 'source'],
                name='quantitative_finding_unique_group_taxon_type_source',
            ),
        ]

    def __str__(self):
        return f'{self.group} | {self.taxon} ({self.value_type})'


class AlphaMetric(TimestampedModel):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='alpha_metrics')
    metric = models.CharField(max_length=100)
    value = models.FloatField()
    source = models.CharField(max_length=255)
    import_batch = models.ForeignKey(
        ImportBatch,
        on_delete=models.SET_NULL,
        related_name='alpha_metrics',
        blank=True,
        null=True,
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['group__study__title', 'group__name', 'metric']
        constraints = [
            models.UniqueConstraint(
                fields=['group', 'metric', 'source'],
                name='alpha_metric_unique_group_metric_source',
            ),
        ]

    def __str__(self):
        return f'{self.group} | {self.metric}'


class BetaMetric(TimestampedModel):
    comparison = models.ForeignKey(
        Comparison,
        on_delete=models.CASCADE,
        related_name='beta_metrics',
    )
    metric = models.CharField(max_length=100)
    value = models.FloatField()
    source = models.CharField(max_length=255)
    import_batch = models.ForeignKey(
        ImportBatch,
        on_delete=models.SET_NULL,
        related_name='beta_metrics',
        blank=True,
        null=True,
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['comparison__study__title', 'comparison__label', 'metric']
        constraints = [
            models.UniqueConstraint(
                fields=['comparison', 'metric', 'source'],
                name='beta_metric_unique_comparison_metric_source',
            ),
        ]

    def __str__(self):
        return f'{self.comparison} | {self.metric}'


class MetadataVariable(TimestampedModel):
    class ValueType(models.TextChoices):
        FLOAT = 'float', 'Float'
        INTEGER = 'int', 'Integer'
        TEXT = 'text', 'Text'
        BOOLEAN = 'bool', 'Boolean'

    name = models.CharField(max_length=100, unique=True)
    value_type = models.CharField(max_length=10, choices=ValueType.choices)
    display_name = models.CharField(max_length=255, blank=True)
    is_filterable = models.BooleanField(default=False)

    class Meta:
        ordering = ['display_name', 'name']

    def __str__(self):
        return self.display_name or self.name


class MetadataValue(TimestampedModel):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='metadata_values')
    variable = models.ForeignKey(
        MetadataVariable,
        on_delete=models.CASCADE,
        related_name='metadata_values',
    )
    value_text = models.TextField(blank=True, null=True)
    value_float = models.FloatField(blank=True, null=True)
    value_int = models.IntegerField(blank=True, null=True)
    value_bool = models.BooleanField(blank=True, null=True)

    class Meta:
        ordering = ['group__study__title', 'group__name', 'variable__name']
        constraints = [
            models.UniqueConstraint(
                fields=['group', 'variable'],
                name='metadata_value_unique_group_variable',
            ),
            models.CheckConstraint(
                condition=(
                    Q(value_float__isnull=False, value_int__isnull=True, value_text__isnull=True, value_bool__isnull=True)
                    | Q(value_float__isnull=True, value_int__isnull=False, value_text__isnull=True, value_bool__isnull=True)
                    | Q(value_float__isnull=True, value_int__isnull=True, value_text__isnull=False, value_bool__isnull=True)
                    | Q(value_float__isnull=True, value_int__isnull=True, value_text__isnull=True, value_bool__isnull=False)
                ),
                name='metadata_value_exactly_one_typed_value',
            ),
        ]

    def __str__(self):
        return f'{self.group} | {self.variable}'

    def typed_value(self):
        for value in (self.value_float, self.value_int, self.value_text, self.value_bool):
            if value is not None:
                return value
        return ''

    def clean(self):
        super().clean()
        if self.value_text == '':
            self.value_text = None

        typed_values = {
            'value_float': self.value_float is not None,
            'value_int': self.value_int is not None,
            'value_text': self.value_text not in (None, ''),
            'value_bool': self.value_bool is not None,
        }
        if sum(typed_values.values()) != 1:
            raise ValidationError('MetadataValue requires exactly one typed value field.')

        expected_field_by_type = {
            MetadataVariable.ValueType.FLOAT: 'value_float',
            MetadataVariable.ValueType.INTEGER: 'value_int',
            MetadataVariable.ValueType.TEXT: 'value_text',
            MetadataVariable.ValueType.BOOLEAN: 'value_bool',
        }
        if self.variable_id:
            expected_field = expected_field_by_type[self.variable.value_type]
            populated_field = next(field_name for field_name, is_populated in typed_values.items() if is_populated)
            if expected_field != populated_field:
                raise ValidationError(
                    f'MetadataValue for variable type "{self.variable.value_type}" '
                    f'must use {expected_field}.'
                )

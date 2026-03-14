from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Study(TimestampedModel):
    source_doi = models.CharField(max_length=255, blank=True, null=True)
    title = models.CharField(max_length=500)
    country = models.CharField(max_length=255, blank=True)
    journal = models.CharField(max_length=255, blank=True)
    publication_year = models.PositiveIntegerField(blank=True, null=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['title']
        constraints = [
            models.UniqueConstraint(
                fields=['source_doi'],
                condition=Q(source_doi__isnull=False) & ~Q(source_doi=''),
                name='study_unique_source_doi_when_present',
            ),
        ]

    def __str__(self):
        if self.publication_year:
            return f'{self.title} ({self.publication_year})'
        return self.title


class Sample(TimestampedModel):
    study = models.ForeignKey(Study, on_delete=models.CASCADE, related_name='samples')
    label = models.CharField(max_length=255)
    site = models.CharField(max_length=255, blank=True)
    method = models.CharField(max_length=255, blank=True)
    cohort = models.CharField(max_length=255, blank=True)
    sample_size = models.PositiveIntegerField(blank=True, null=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['study__title', 'label']
        constraints = [
            models.UniqueConstraint(
                fields=['study', 'label'],
                name='sample_unique_study_label',
            ),
        ]

    def __str__(self):
        return f'{self.study}: {self.label}'


class Organism(models.Model):
    ncbi_taxonomy_id = models.PositiveIntegerField(unique=True, db_index=True)
    scientific_name = models.CharField(max_length=255)
    taxonomic_rank = models.CharField(max_length=64)
    parent_taxonomy = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        related_name='children',
        blank=True,
        null=True,
    )
    genus = models.CharField(max_length=255, blank=True)
    species = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['scientific_name']

    def __str__(self):
        return self.scientific_name


class ImportBatch(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        VALIDATED = 'validated', 'Validated'
        COMPLETED = 'completed', 'Completed'
        FAILED = 'failed', 'Failed'

    name = models.CharField(max_length=255)
    source_file = models.CharField(max_length=500, blank=True)
    import_type = models.CharField(max_length=100)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)
    success_count = models.PositiveIntegerField(default=0)
    error_count = models.PositiveIntegerField(default=0)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return self.name


class RelativeAssociation(TimestampedModel):
    class Sign(models.TextChoices):
        POSITIVE = 'positive', 'Positive'
        NEGATIVE = 'negative', 'Negative'
        NEUTRAL = 'neutral', 'Neutral'

    sample = models.ForeignKey(Sample, on_delete=models.CASCADE, related_name='relative_associations')
    organism_1 = models.ForeignKey(
        Organism,
        on_delete=models.CASCADE,
        related_name='relative_associations_as_first',
    )
    organism_2 = models.ForeignKey(
        Organism,
        on_delete=models.CASCADE,
        related_name='relative_associations_as_second',
    )
    association_type = models.CharField(max_length=100)
    value = models.FloatField(blank=True, null=True)
    sign = models.CharField(max_length=20, choices=Sign.choices, blank=True)
    p_value = models.FloatField(blank=True, null=True)
    q_value = models.FloatField(blank=True, null=True)
    method = models.CharField(max_length=255, blank=True)
    confidence = models.FloatField(blank=True, null=True)
    notes = models.TextField(blank=True)
    import_batch = models.ForeignKey(
        ImportBatch,
        on_delete=models.SET_NULL,
        related_name='relative_associations',
        blank=True,
        null=True,
    )

    class Meta:
        ordering = ['sample', 'organism_1', 'organism_2', 'association_type']
        constraints = [
            models.UniqueConstraint(
                fields=['sample', 'organism_1', 'organism_2', 'association_type'],
                name='relative_association_unique_sample_pair_type',
            ),
            models.CheckConstraint(
                condition=Q(organism_1__lt=F('organism_2')),
                name='relative_association_canonical_organism_order',
            ),
        ]

    def __str__(self):
        return (
            f'{self.sample} | {self.organism_1} - {self.organism_2} '
            f'({self.association_type})'
        )

    def clean(self):
        super().clean()
        if self.organism_1_id and self.organism_2_id and self.organism_1_id == self.organism_2_id:
            raise ValidationError('RelativeAssociation cannot reference the same organism twice.')

    def save(self, *args, **kwargs):
        if (
            self.organism_1_id
            and self.organism_2_id
            and self.organism_1_id > self.organism_2_id
        ):
            self.organism_1_id, self.organism_2_id = self.organism_2_id, self.organism_1_id
        super().save(*args, **kwargs)


class AlphaMetric(models.Model):
    sample = models.ForeignKey(Sample, on_delete=models.CASCADE, related_name='alpha_metrics')
    metric_type = models.CharField(max_length=100)
    value = models.FloatField()
    unit = models.CharField(max_length=50, blank=True)
    notes = models.TextField(blank=True)
    import_batch = models.ForeignKey(
        ImportBatch,
        on_delete=models.SET_NULL,
        related_name='alpha_metrics',
        blank=True,
        null=True,
    )

    class Meta:
        ordering = ['sample', 'metric_type']
        constraints = [
            models.UniqueConstraint(
                fields=['sample', 'metric_type'],
                name='alpha_metric_unique_sample_metric_type',
            ),
        ]

    def __str__(self):
        return f'{self.sample} | {self.metric_type}'


class BetaMetric(models.Model):
    sample_a = models.ForeignKey(
        Sample,
        on_delete=models.CASCADE,
        related_name='beta_metrics_as_first',
    )
    sample_b = models.ForeignKey(
        Sample,
        on_delete=models.CASCADE,
        related_name='beta_metrics_as_second',
    )
    metric_type = models.CharField(max_length=100)
    value = models.FloatField()
    unit = models.CharField(max_length=50, blank=True)
    notes = models.TextField(blank=True)
    import_batch = models.ForeignKey(
        ImportBatch,
        on_delete=models.SET_NULL,
        related_name='beta_metrics',
        blank=True,
        null=True,
    )

    class Meta:
        ordering = ['sample_a', 'sample_b', 'metric_type']
        constraints = [
            models.UniqueConstraint(
                fields=['sample_a', 'sample_b', 'metric_type'],
                name='beta_metric_unique_sample_pair_metric_type',
            ),
            models.CheckConstraint(
                condition=Q(sample_a__lt=F('sample_b')),
                name='beta_metric_canonical_sample_order',
            ),
        ]

    def __str__(self):
        return f'{self.sample_a} | {self.sample_b} ({self.metric_type})'

    def clean(self):
        super().clean()
        if self.sample_a_id and self.sample_b_id and self.sample_a_id == self.sample_b_id:
            raise ValidationError('BetaMetric cannot reference the same sample twice.')

    def save(self, *args, **kwargs):
        if self.sample_a_id and self.sample_b_id and self.sample_a_id > self.sample_b_id:
            self.sample_a_id, self.sample_b_id = self.sample_b_id, self.sample_a_id
        super().save(*args, **kwargs)


class CoreMetadata(models.Model):
    sample = models.OneToOneField(
        Sample,
        on_delete=models.CASCADE,
        related_name='core_metadata',
        primary_key=True,
    )
    condition = models.CharField(max_length=255, blank=True)
    male_percent = models.FloatField(blank=True, null=True)
    age_mean = models.FloatField(blank=True, null=True)
    age_sd = models.FloatField(blank=True, null=True)
    bmi_mean = models.FloatField(blank=True, null=True)
    bmi_sd = models.FloatField(blank=True, null=True)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f'Core metadata for {self.sample}'


class MetadataVariable(TimestampedModel):
    class ValueType(models.TextChoices):
        FLOAT = 'float', 'Float'
        INTEGER = 'int', 'Integer'
        TEXT = 'text', 'Text'
        BOOLEAN = 'bool', 'Boolean'

    name = models.CharField(max_length=100, unique=True)
    display_name = models.CharField(max_length=255)
    domain = models.CharField(max_length=100, blank=True)
    value_type = models.CharField(max_length=10, choices=ValueType.choices)
    default_unit = models.CharField(max_length=50, blank=True)
    description = models.TextField(blank=True)
    is_filterable = models.BooleanField(default=False)
    allowed_values = models.JSONField(blank=True, default=list)

    class Meta:
        ordering = ['display_name']

    def __str__(self):
        return self.display_name


class MetadataValue(models.Model):
    sample = models.ForeignKey(Sample, on_delete=models.CASCADE, related_name='metadata_values')
    variable = models.ForeignKey(
        MetadataVariable,
        on_delete=models.CASCADE,
        related_name='metadata_values',
    )
    value_float = models.FloatField(blank=True, null=True)
    value_int = models.IntegerField(blank=True, null=True)
    value_text = models.TextField(blank=True, null=True)
    value_bool = models.BooleanField(blank=True, null=True)
    unit = models.CharField(max_length=50, blank=True)
    raw_value = models.CharField(max_length=255, blank=True)
    variation = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    import_batch = models.ForeignKey(
        ImportBatch,
        on_delete=models.SET_NULL,
        related_name='metadata_values',
        blank=True,
        null=True,
    )

    class Meta:
        ordering = ['sample', 'variable']
        constraints = [
            models.UniqueConstraint(
                fields=['sample', 'variable'],
                name='metadata_value_unique_sample_variable',
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
        return f'{self.sample} | {self.variable}'

    def clean(self):
        super().clean()
        if self.value_text == '':
            self.value_text = None
        typed_values = [
            self.value_float is not None,
            self.value_int is not None,
            self.value_text not in (None, ''),
            self.value_bool is not None,
        ]
        if sum(typed_values) != 1:
            raise ValidationError('MetadataValue requires exactly one typed value field.')

        expected_field_by_type = {
            MetadataVariable.ValueType.FLOAT: 'value_float',
            MetadataVariable.ValueType.INTEGER: 'value_int',
            MetadataVariable.ValueType.TEXT: 'value_text',
            MetadataVariable.ValueType.BOOLEAN: 'value_bool',
        }
        if self.variable_id:
            expected_field = expected_field_by_type.get(self.variable.value_type)
            populated_field = next(
                field_name
                for field_name, is_populated in {
                    'value_float': self.value_float is not None,
                    'value_int': self.value_int is not None,
                    'value_text': self.value_text not in (None, ''),
                    'value_bool': self.value_bool is not None,
                }.items()
                if is_populated
            )
            if expected_field != populated_field:
                raise ValidationError(
                    f'MetadataValue for variable type "{self.variable.value_type}" '
                    f'must use {expected_field}.'
                )

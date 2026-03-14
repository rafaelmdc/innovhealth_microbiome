# AlphaMetric CSV Contract

## Purpose

Import within-sample diversity metrics into `AlphaMetric`.

## Required columns

- `study_source_doi`
- `sample_label`
- `metric_type`
- `value`

## Optional columns

- `unit`
- `notes`

## CSV shape

```csv
study_source_doi,sample_label,metric_type,value,unit,notes
10.1000/example,Cohort A,shannon,3.82,,Reported by study
```

## Lookup rules

- resolve the sample using `(study_source_doi, sample_label)`

## Validation rules

- target sample must resolve successfully
- `value` must parse as a float

## Import behavior

- create-only
- valid rows should be attributed to the generated `ImportBatch`

## Notes

- imports are create-only and duplicate rows are skipped during preview/import

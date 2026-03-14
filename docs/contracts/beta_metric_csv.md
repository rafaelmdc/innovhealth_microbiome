# BetaMetric CSV Contract

## Purpose

Import pairwise between-sample or between-group diversity metrics into `BetaMetric`.

## Required columns

- `study_source_doi`
- `sample_1_label`
- `sample_2_label`
- `metric_type`
- `value`

## Optional columns

- `unit`
- `notes`

## CSV shape

```csv
study_source_doi,sample_1_label,sample_2_label,metric_type,value,unit,notes
10.1000/example,Cohort A,Cohort B,bray_curtis,0.37,,Reported by study
```

## Lookup rules

- resolve both samples within the same study using `(study_source_doi, sample_label)`
- internal IDs should not be used in CSV input

## Pairwise rules

- self-pairs are invalid
- canonical sample ordering should be enforced during validation/import
- reverse duplicates should not create separate rows

## Validation rules

- both samples must resolve successfully
- `value` must parse as a float

## Import behavior

- create-only
- valid rows should be attributed to the generated `ImportBatch`

## Notes

- imports are create-only and duplicate rows are skipped during preview/import

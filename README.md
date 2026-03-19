# Microbiome Literature Database

A Django-based database and browser for curated microbiome study evidence, centered on study groups, explicit comparisons, qualitative taxon findings, and quantitative taxon values.

## Project goal

This project centralizes curated microbiome findings from published studies in a reproducible and queryable format.

The database is designed to support:

- study-level paper records
- group or cohort records within each study
- explicit comparisons between groups
- lineage-aware taxon records
- qualitative findings such as enriched or depleted taxa
- quantitative findings such as per-group relative abundance values
- slim flexible metadata storage
- CSV-based ingestion workflows
- interactive browsing and graph exploration

## Core schema

Primary models:

- `Study`
- `Group`
- `Comparison`
- `Taxon`
- `TaxonClosure`
- `TaxonName`
- `QualitativeFinding`
- `QuantitativeFinding`
- `MetadataVariable`
- `MetadataValue`
- `ImportBatch`

Optional models:

- `AlphaMetric`
- `BetaMetric`

## Website features

- Home page describing the project and data model
- Server-rendered browser for studies, groups, comparisons, taxa, and findings
- Comparison-to-taxon qualitative graph
- Admin-friendly manual CRUD
- Admin-only CSV import workflow with preview and validation

## Stack

- Django
- PostgreSQL
- Bootstrap 5
- Django templates
- Django admin
- `networkx`
- Cytoscape.js

## Notes

- The old `RelativeAssociation`-centered data model has been removed from the main codebase.
- Quantitative abundance is modeled as one taxon in one group, not taxon A relative to taxon B.
- Qualitative direction-of-change is modeled as one taxon in one comparison.
- Taxonomy is now centered on `Taxon` with a closure table for lineage-aware filtering and rollup.

See [docs/schema.md](/home/rafael/Documents/GitHub/innovhealth_microbiome/docs/schema.md) for the schema and [docs/migration_note_2026-03-15.md](/home/rafael/Documents/GitHub/innovhealth_microbiome/docs/migration_note_2026-03-15.md) for breaking changes.

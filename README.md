# Microbiome Literature Database

A Django-based database and browser for curated microbiome study evidence, centered on study groups, explicit comparisons, qualitative taxon findings, quantitative taxon values, and server-rendered graph exploration.

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
- preview-first CSV and workbook ingestion workflows
- interactive disease and co-abundance graph exploration

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
- `Disease Network` view at `/graph/disease/`
- `Co-abundance Taxon Network` view at `/graph/co-abundance/`
- Cytoscape and ECharts renderers with per-engine layout controls
- Admin-friendly manual CRUD
- Admin-only CSV and workbook import workflow with preview, validation, and provenance-aware writes

## Stack

- Django
- PostgreSQL
- Bootstrap 5
- Django templates
- Django admin
- `networkx`
- Cytoscape.js
- ECharts

## Notes

- The old `RelativeAssociation`-centered data model has been removed from the main codebase.
- Quantitative abundance is modeled as one taxon in one group, not taxon A relative to taxon B.
- Qualitative direction-of-change is modeled as one taxon in one comparison.
- Taxonomy is centered on `Taxon` with a closure table for lineage-aware filtering and rollup.
- The disease graph is comparison-centered and columnar.
- The co-abundance graph is a derived taxon-pair pattern view built from shared qualitative comparison context.
- Taxon preview uses resolver-backed lineage metadata when available and falls back to curated local taxonomy when an exact local match already exists.
- Taxa that still require resolver review are reported in preview and skipped on confirm, along with dependent workbook findings.

## Documentation

- [Schema](docs/schema.md)
- [Graph Overview](docs/graph.md)
- [Disease Graph](docs/disease_graph.md)
- [Co-abundance Graph](docs/co_abundance_graph.md)
- [Import Pipeline](docs/import_pipeline.md)
- [Roadmap](docs/roadmap.md)

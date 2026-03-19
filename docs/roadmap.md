# Roadmap

## Goal

Build a small Django application for curated microbiome literature data with:

- a clear home page
- a database browser
- a qualitative comparison graph
- admin-driven curation
- CSV-based bulk imports

## Current schema direction

The application now centers on:

- `Study`
- `Group`
- `Comparison`
- `Taxon`
- `TaxonClosure`
- `TaxonName`
- `QualitativeFinding`
- `QuantitativeFinding`

Optional extensions remain:

- `AlphaMetric`
- `BetaMetric`

## Implementation order

1. project setup
2. schema and migrations
3. admin usability
4. import workflow
5. browser views and templates
6. home page
7. comparison graph
8. refinement and tests

## Current prototype status

Implemented:

- taxonomy-first schema centered on `Taxon`, `TaxonClosure`, and `TaxonName`
- preview-first CSV and workbook imports
- resolver-backed taxon preview with lineage payloads
- skip-and-report handling for taxon rows that still require review
- lineage-aware browser filters for taxa and findings
- lineage-aware qualitative graph with branch filtering and rank rollups

Current priority:

- keep the main curation/import/graph path reliable
- add only targeted stabilization where the prototype is already exercising real complexity

## Browser scope

The browser should support:

- studies
- groups
- comparisons
- taxa
- qualitative findings
- quantitative findings

## Import scope

Supported CSV imports:

- taxon
- study
- group
- comparison
- metadata_variable
- metadata_value
- qualitative_finding
- quantitative_finding
- alpha_metric
- beta_metric

# Roadmap

This roadmap reflects the current codebase state and the next practical steps for the project.

## Completed foundation

- schema reset around `Study`, `Group`, `Comparison`, `Taxon`, `QualitativeFinding`, and `QuantitativeFinding`
- lineage-aware taxonomy with `TaxonClosure` and `TaxonName`
- server-rendered browser for studies, groups, comparisons, taxa, qualitative findings, and quantitative findings
- home page and staff entry points
- preview-first CSV and workbook import flow with `ImportBatch` provenance
- disease graph with Cytoscape and ECharts renderers
- co-abundance taxon network with pattern filtering and support thresholds

## Current priorities

1. Keep documentation aligned with the shipped graph and import features.
2. Tighten browser-to-graph navigation so supporting evidence is easy to open from graph context.
3. Continue refining taxonomy-aware filtering and rollup behavior.
4. Preserve admin usability and import traceability as workbook coverage grows.

## Next likely implementation work

- right click to see list of values / show calculations in a user friendly way in co-occurance edges
- print current graph selection
- open taxa (in browser) highlighted in graph, via filter would be the easiest route
- pages instead of listing all listings involved in graphs
- change echarts rendering, so one can highlight a specific organism when clicking on it, mimicking cytoscape

## Constraints

- keep Django-first, server-rendered architecture
- avoid reintroducing old pairwise abundance modeling
- avoid unnecessary frontend complexity
- prefer small, explicit changes over broad refactors

# Graph Overview

This project currently exposes two server-rendered graph views built from curated `QualitativeFinding` data:

- `Disease Network` at `/graph/disease/`
- `Co-abundance Taxon Network` at `/graph/co-abundance/`

`QuantitativeFinding` remains supporting evidence for the browser and future analysis work. It is not the primary edge source for either current graph.

## Shared architecture

Both graph pages follow the same high-level flow:

1. `core.views` loads filtered `QualitativeFinding` rows with the required `Comparison`, `Group`, `Study`, and `Taxon` joins.
2. `core.graph_payloads` converts those rows into JSON-ready node and edge payloads.
3. The payload is embedded in the template with `json_script`.
4. The page renders the graph with either Cytoscape or ECharts, selected by the user.

The graph layer is intentionally derived at request time. There are no stored graph tables or background graph materialization jobs in the current implementation.

## Shared controls

Both graph pages support:

- study filter
- disease text query
- taxon text query
- taxonomic branch filter
- grouping rank selector:
  - `leaf`
  - `species`
  - `genus`
  - `family`
  - `order`
  - `class`
  - `phylum`
- renderer selector:
  - `cytoscape`
  - `echarts`

Both pages also expose per-engine layout controls. Cytoscape and ECharts use different parameter sets and defaults, so the visible sliders change when the engine changes.

## Disease graph

The disease graph is a comparison-centered qualitative network.

- diseases are derived from `Comparison.group_a.condition`, falling back to `Comparison.group_a.name`
- enriched taxa are rendered as one taxon role column
- depleted taxa are rendered as a separate taxon role column
- edges aggregate leaf-level findings into the selected grouping rank

Canonical documentation:

- [Disease Graph](disease_graph.md)

## Co-abundance graph

The co-abundance graph is a derived taxon-pair pattern view.

- pairs are generated from findings that appear in the same `Comparison`
- qualitative directions are normalized into positive vs negative buckets
- pair support is tracked as `same_direction`, `opposite_direction`, or `mixed`
- edges are aggregated across comparisons and optionally filtered by minimum support

Canonical documentation:

- [Co-abundance Graph](co_abundance_graph.md)

## Shared caveats

- Both views are exploratory and should not be presented as causal or mechanistic evidence.
- Rank rollup can omit findings when no ancestor exists at the selected rank. The UI reports those skipped counts.
- The browser remains the source of truth for row-level inspection. The graph pages are derived summaries with context-menu shortcuts into the underlying browser views.

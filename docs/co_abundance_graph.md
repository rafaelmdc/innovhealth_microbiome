# Co-abundance Graph

## Purpose

The co-abundance graph at `/graph/co-abundance/` is a derived taxon-pair pattern view built from shared qualitative comparison context.

It helps users explore questions like:

- which taxa are repeatedly reported in the same direction within the same comparison
- which taxa are repeatedly reported in opposite directions
- which taxon pairs have mixed literature support
- how pair patterns change after lineage rollup or branch filtering

This page is exploratory. It summarizes repeated co-patterns in the curated literature and should not be interpreted as proof of direct biological interaction.

## Data source

Primary source:

- `QualitativeFinding`

Required joins:

- `QualitativeFinding.comparison`
- `Comparison.study`
- `Comparison.group_a`
- `Comparison.group_b`
- `QualitativeFinding.taxon`

Taxonomic rollup support:

- `TaxonClosure`

## Pair generation logic

The current implementation derives edges at request time.

1. Load filtered qualitative findings.
2. Roll each finding up to the selected grouping rank when requested.
3. Normalize directions into two buckets:
   - positive:
     `enriched`, `increased`
   - negative:
     `depleted`, `decreased`
4. Within each `Comparison`, deduplicate local items by grouped taxon plus normalized direction.
5. Generate unordered grouped-taxon pairs inside that comparison.
6. Classify each local pair as:
   - `same_direction`
   - `opposite_direction`
7. Aggregate those pair observations across comparisons and studies.

The payload stores a stable `source` and `target` order for rendering and table output, but the graph meaning is a taxon-pair relationship, not a causal directional statement.

## Filters and controls

The page supports:

- `study`
- `disease`
- `taxon`
- `branch`
- `group_rank`
- `pattern`
- `min_support`
- `engine`

Pattern choices:

- `all`
- `same_direction`
- `opposite_direction`
- `mixed`

Supported grouping ranks:

- `leaf`
- `species`
- `genus`
- `family`
- `order`
- `class`
- `phylum`

Supported renderers:

- `cytoscape`
- `echarts`

As with the disease graph, the visible layout sliders are renderer-specific.

## Node semantics

Each node represents one grouped taxon at the selected rank.

Node payload includes:

- taxon label
- taxon primary key
- rank
- taxonomy id
- grouping rank
- degree
- study count
- contributing leaf taxon count

## Edge semantics

Each edge represents repeated pair support between two grouped taxa across filtered comparisons.

Edge payload includes:

- `dominant_pattern`
- `same_direction_count`
- `opposite_direction_count`
- `total_support`
- `comparison_count`
- `study_count`
- `source_count`
- contributing comparison labels
- contributing disease labels
- contributing leaf taxon count

Dominant pattern rules:

- `same_direction` when same-direction support is greater
- `opposite_direction` when opposite-direction support is greater
- `mixed` when both support types exist and are tied

The `min_support` filter is applied to total support after aggregation.

## Summary cards

The page reports:

- taxon count
- edge count
- total support events
- study count
- same-direction edge count
- opposite-direction edge count
- mixed edge count

As in the disease graph, skipped rollups are surfaced when selected taxa do not have an ancestor at the chosen rank.

## Browser integrations

The current co-abundance graph context menu exposes:

- taxon node -> taxon detail page

The browser remains the intended place for detailed row-level inspection once a taxon pair of interest has been identified.

## Caveats

- This graph is derived from shared comparison context, not from abundance correlation matrices.
- It is not causal, mechanistic, or temporal.
- It is not currently built from `QuantitativeFinding`.
- Edge classification is comparison-aware and aggregation-based, so the graph should be read as a repeated literature pattern view.

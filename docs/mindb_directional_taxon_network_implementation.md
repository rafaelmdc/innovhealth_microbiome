# MINdb — Directional Taxon Network Implementation Details

## Purpose

This document turns the directional taxon network concept into a practical implementation plan that fits the current MINdb codebase.

The implementation should:

- derive taxon-taxon edges from curated `QualitativeFinding` records
- preserve the current schema as the source of truth
- stay server-rendered and Django-first
- reuse the existing graph architecture style where possible
- remain explicit and easy to validate

This feature should be implemented as a derived view over existing data, not as a new primary storage model.

---

## Core principle

The directional taxon network is computed from findings that appear inside the same `Comparison`.

For one comparison:

- taxa reported in the same direction contribute to a `same_direction` relationship
- taxa reported in opposite directions contribute to an `opposite_direction` relationship

Across many comparisons:

- repeated same-direction co-occurrence increases same-direction support
- repeated opposite-direction co-occurrence increases opposite-direction support
- mixed evidence remains visible as mixed evidence rather than being forced into a false certainty

The graph is therefore an aggregated literature-pattern network built from repeated comparison-local co-patterns.

---

## Data source

### Primary table

- `QualitativeFinding`

### Required joins

- `QualitativeFinding.comparison`
- `Comparison.study`
- `Comparison.group_a`
- `Comparison.group_b`
- `QualitativeFinding.taxon`

### Optional taxonomy support

- `TaxonClosure` for rank rollup
- `Taxon.parent` for lineage-aware labeling where needed

No new database table is required for the first version.

---

## V1 scope

The first implementation should stay narrow.

### Included

- taxon-taxon network derived from `QualitativeFinding`
- disease or condition filtering
- study filtering
- taxonomic branch filtering
- grouping by one rank at a time:
  - `leaf`
  - `genus`
  - `family`
  - `order`
  - `class`
  - `phylum`
- edge summary based on repeated same-direction and opposite-direction evidence
- Cytoscape rendering in the browser

### Excluded for V1

- quantitative edge derivation from `QuantitativeFinding`
- time-series logic
- effect size weighting
- confidence scoring beyond simple counts
- precomputed materialized graph tables
- cross-study ontology normalization beyond existing study/group fields

---

## Direction normalization

The current qualitative directions should be normalized into two buckets before pair generation.

### Positive-direction bucket

- `enriched`
- `increased`

### Negative-direction bucket

- `depleted`
- `decreased`

If new directional terms are added later, they should map into the same two buckets or be excluded until explicitly handled.

This keeps pair classification simple and consistent.

---

## Pair generation logic

### Step 1: load findings

Query the filtered `QualitativeFinding` rows with `select_related` for:

- `comparison`
- `comparison__study`
- `comparison__group_a`
- `comparison__group_b`
- `taxon`

Apply filters before pair generation so the network only reflects the requested scope.

### Step 2: resolve grouped taxon

For each finding:

- if `group_rank = leaf`, keep the original `taxon`
- otherwise map the leaf taxon to the nearest ancestor at the selected rank using `TaxonClosure`
- if no ancestor exists at that rank, omit the finding and count it as skipped

This should match the rollup behavior already used in the current qualitative graph.

### Step 3: group findings by comparison

After rollup, group findings by `comparison_id`.

Each comparison becomes one local context for taxon-taxon pair derivation.

### Step 4: deduplicate within comparison

Before generating pairs, collapse duplicate repeated rows inside one comparison for the same grouped taxon and normalized direction.

Recommended local key:

- `(comparison_id, grouped_taxon_id, normalized_direction)`

This prevents one comparison from over-weighting the network due to duplicate source rows for the same taxon-direction signal.

### Step 5: generate unordered taxon pairs

For each comparison:

1. collect the unique grouped taxon-direction items
2. generate all unordered taxon pairs
3. classify each pair:
   - `same_direction` if both normalized directions match
   - `opposite_direction` if the normalized directions differ

Recommended canonical pair key:

- `(min(taxon_a_id, taxon_b_id), max(taxon_a_id, taxon_b_id))`

Self-pairs should never be created.

### Step 6: aggregate across comparisons

For each canonical pair, track:

- `same_direction_count`
- `opposite_direction_count`
- `comparison_count`
- `study_count`
- `source_count`
- contributing comparison labels
- contributing disease or condition labels
- contributing leaf taxon ids

The counts should be comparison-aware. One comparison should contribute at most one same-direction observation or one opposite-direction observation for one grouped pair.

---

## Edge classification

Each aggregated pair should expose both raw counts and a dominant label.

### Raw counts

- `same_direction_count`
- `opposite_direction_count`
- `total_support = same_direction_count + opposite_direction_count`

### Dominant label

- `same_direction` if only same-direction evidence exists
- `opposite_direction` if only opposite-direction evidence exists
- `same_direction` if same-direction evidence clearly exceeds opposite-direction evidence
- `opposite_direction` if opposite-direction evidence clearly exceeds same-direction evidence
- `mixed` if both exist without a clear dominant pattern

For V1, the simplest rule is:

- `mixed` when both counts are non-zero and equal
- otherwise choose the larger count

If later needed, the threshold can become stricter.

---

## Node semantics

Each node represents one grouped taxon at the selected rank.

Recommended node data:

- `id`
- `label`
- `rank`
- `taxonomy_id`
- `grouping_rank`
- `leaf_taxon_count`
- `degree`
- `study_count`

Optional later metrics:

- connected component id
- weighted degree
- centrality

These later metrics can be computed with `networkx` if the UI needs them.

---

## Edge semantics

Each edge represents repeated directional co-pattern evidence between two taxa across filtered comparisons.

Recommended edge data:

- `id`
- `source`
- `target`
- `dominant_pattern`
- `same_direction_count`
- `opposite_direction_count`
- `total_support`
- `comparison_count`
- `study_count`
- `source_count`
- `comparison_labels`
- `disease_labels`
- `leaf_taxon_count`

Recommended tooltip summary:

- dominant pattern
- same vs opposite counts
- number of contributing comparisons
- number of contributing studies

---

## Disease and condition labeling

The disease-oriented default should follow the same logic already used in the current graph view.

Recommended default disease label source:

1. `Comparison.group_a.condition` when present
2. otherwise `Comparison.group_a.name`

This keeps the feature aligned with the current comparison-centered interpretation.

The network itself is taxon-to-taxon, but the selected disease or condition filter should be shown prominently in the page summary.

---

## Filtering

The directional taxon network should reuse the same filtering style as the current qualitative graph where practical.

### Recommended filters

- study
- disease or condition text
- taxon text
- taxonomic branch
- grouping rank
- minimum support threshold
- edge pattern:
  - `all`
  - `same_direction`
  - `opposite_direction`
  - `mixed`

### Recommended first default

- disease-focused view
- `group_rank = genus` or `leaf`
- minimum support threshold of `2`

`genus` is often the most interpretable rank for exploratory use, but the UI can still default to `leaf` for consistency with the existing graph if desired.

---

## Backend structure

The implementation should follow the current codebase pattern.

### Suggested files

- `core/views.py`
  Add one new `TemplateView` for the directional taxon network page.
- `core/urls.py`
  Add one route for the new graph page.
- `core/graph.py`
  Either:
  - add a new builder function such as `build_directional_taxon_network(...)`, or
  - move graph builders into a small module split if the file becomes too crowded
- `templates/core/`
  Add one template for the new graph page.

### Suggested function shape

```python
def build_directional_taxon_network(
    findings,
    *,
    grouping_rank='leaf',
    minimum_support=1,
    pattern_filter='all',
):
    ...
```

This should return serialized node and edge payloads plus summary metadata, matching the style of the current graph builder.

---

## Role of NetworkX

The project stack allows `networkx`, but V1 should use it lightly.

Recommended approach:

1. aggregate nodes and edges explicitly in Python dictionaries
2. serialize those results directly for Cytoscape
3. optionally construct a lightweight `networkx.Graph` after aggregation if one or two extra metrics are actually useful

This avoids overengineering while staying compatible with the documented graph direction.

V1 does not need advanced graph algorithms to be useful.

---

## Frontend behavior

The page should remain server-rendered and use Cytoscape.js for interactive display.

### Recommended layout

- page intro explaining what the network means
- filter form above the graph
- summary row with:
  - node count
  - edge count
  - total support count
  - selected rank
  - skipped rollup count
- main Cytoscape canvas
- caveat text below the graph

### Visual encoding

- node size by degree or weighted support
- edge color by dominant pattern:
  - same-direction: teal or green family
  - opposite-direction: amber or red family
  - mixed: neutral gray
- edge width by `total_support`

### Interaction

- hover tooltip for node and edge details
- click node to highlight neighbors
- click edge to show supporting counts and comparison labels

Avoid heavy client-side state management. The page should refresh from query parameters in the same way as the current graph page.

---

## Summary metrics

Recommended page summary:

- total nodes
- total edges
- total comparison-supported pair observations
- total unique studies
- selected grouping rank
- skipped rollup count
- dominant pattern breakdown:
  - same-direction edge count
  - opposite-direction edge count
  - mixed edge count

These numbers help users understand what they are looking at before interpreting the graph visually.

---

## Validation and safeguards

The implementation should be careful about misleading inflation.

### Important safeguards

- deduplicate same taxon-direction entries within one comparison before pair generation
- ensure one comparison does not contribute repeated duplicate evidence to the same grouped pair
- use unordered canonical pair keys
- never create self-edges
- track skipped rollup counts explicitly
- keep caveat text visible in the UI

### Interpretation safeguard

Do not label edges as:

- interaction
- association strength
- co-occurrence frequency in samples

The edge meaning is repeated directional co-pattern within comparison-level literature findings.

---

## Performance expectations

The initial implementation can compute the network on demand.

That is reasonable if:

- the filtered dataset remains moderate
- pair generation happens after query filtering
- taxonomy rollup queries are prefetched efficiently

If performance later becomes an issue, the first optimization steps should be:

1. reduce loaded fields
2. cache ancestor lookup maps for the current result set
3. add cheap result caching for repeated filter combinations
4. only consider precomputed edge tables if real usage justifies them

Precomputation should not be the default starting point.

---

## Testing

Recommended test coverage:

- anonymous users are redirected if the page is staff-only
- staff users can load the page
- same-direction pairs aggregate correctly
- opposite-direction pairs aggregate correctly
- mixed evidence is labeled correctly
- duplicate rows within one comparison do not inflate counts
- rank rollup maps descendant taxa correctly
- findings without an ancestor at the selected rank are skipped and counted
- disease filters constrain the graph correctly
- branch filters constrain the graph correctly

Prefer focused builder-level tests first, then one or two view-level integration tests.

---

## Suggested rollout order

1. implement the backend builder for pair aggregation
2. add builder-level tests for pair generation and rollup behavior
3. add the new Django view and URL
4. add the template and Cytoscape rendering
5. add page summary and caveat text
6. refine filters and edge styling

This keeps the risky logic isolated before UI work expands.

---

## Open decisions

These decisions can stay lightweight, but should be made explicitly during implementation.

### Default rank

- `leaf` is consistent with the current graph
- `genus` may be more interpretable for users

### Minimum support default

- `1` is complete but noisy
- `2` is usually a better exploratory default

### Mixed threshold

- simple tie-based `mixed` is easiest for V1
- stricter ambiguity thresholds can wait until real usage feedback exists

---

## Recommended first implementation stance

The first implementation should be:

- comparison-derived
- qualitative-only
- disease-filterable
- rank-aware
- count-based
- explicit about caveats

It should not try to infer biology beyond the curated directional patterns already present in the database.

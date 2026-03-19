# Graph Design

## Purpose

The graph view represents qualitative microbiome findings derived from curated `QualitativeFinding` records.

Its purpose is to let users visually explore:

- which taxa are reported as enriched for a disease
- which taxa are reported as depleted for a disease
- how many supporting findings exist for each disease-taxon connection
- how those findings change when taxa are rolled up to genus, family, order, class, or phylum
- how evidence changes inside one selected taxonomic branch

## Source data

Primary source model:

- `QualitativeFinding`

Supporting models:

- `Comparison`
- `Group`
- `Study`
- `Taxon`

## Graph semantics

Current graph controls:

- study filter
- direction filter
- disease text query
- taxon text query
- taxonomic branch filter
- grouping rank selector:
  - `leaf`
  - `genus`
  - `family`
  - `order`
  - `class`
  - `phylum`

### Node meaning

- one node type represents a disease-like target condition derived from `Comparison.group_a`
- taxon nodes are split by directional role:
  - enriched taxa appear in the left column
  - depleted taxa appear in the right column
  - the same taxon label may appear on both sides when evidence exists in both directions
- when grouping rank is not `leaf`, one taxon node represents the nearest ancestor at the selected rank for one or more leaf findings

### Edge meaning

An edge represents one or more qualitative findings linking a taxon role node to a disease node.

Edges are aggregated at query time from leaf-level `QualitativeFinding` records.

### Edge attributes

- dominant direction
- number of supporting findings
- number of contributing leaf taxa
- number of unique sources
- contributing comparison labels

### Rollup behavior

- leaf findings stay stored at the reported `Taxon`
- graph grouping maps each finding leaf taxon to its nearest ancestor at the selected rank
- if no ancestor exists at the selected rank, that finding is omitted from the grouped graph
- the UI reports how many findings were omitted for that reason

## Notes

- `QuantitativeFinding` is supporting evidence, not the primary graph edge type.
- The old organism-organism `RelativeAssociation` graph has been removed.
- The current web layout is intentionally columnar:
  - left: enriched taxa
  - center: diseases
  - right: depleted taxa

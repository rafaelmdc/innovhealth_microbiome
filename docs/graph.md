# Graph Design

## Purpose

The graph view represents qualitative microbiome findings derived from curated `QualitativeFinding` records.

Its purpose is to let users visually explore:

- which taxa are reported as enriched for a disease
- which taxa are reported as depleted for a disease
- how many supporting findings exist for each disease-taxon connection

## Source data

Primary source model:

- `QualitativeFinding`

Supporting models:

- `Comparison`
- `Group`
- `Study`
- `Taxon`

## Graph semantics

### Node meaning

- one node type represents a disease-like target condition derived from `Comparison.group_a`
- taxon nodes are split by directional role:
  - enriched taxa appear in the left column
  - depleted taxa appear in the right column
  - the same taxon label may appear on both sides when evidence exists in both directions

### Edge meaning

An edge represents one or more qualitative findings linking a taxon role node to a disease node.

### Edge attributes

- dominant direction
- number of supporting findings
- number of unique sources
- contributing comparison labels

## Notes

- `QuantitativeFinding` is supporting evidence, not the primary graph edge type.
- The old organism-organism `RelativeAssociation` graph has been removed.
- lineage-aware grouping should map leaf findings to ancestor taxa at the requested rank before aggregation.
- The current web layout is intentionally columnar:
  - left: enriched taxa
  - center: diseases
  - right: depleted taxa

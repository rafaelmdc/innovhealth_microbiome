# Taxonomy Redesign Plan

## Current Status

Implemented in the current prototype:

- Phase 1: flat taxonomy replaced by `Taxon`, `TaxonClosure`, and `TaxonName`
- Phase 2: findings and admin repointed from `organism` to `taxon`
- Phase 3: taxonomy import helpers and resolver integration added
- Phase 4: preview-first CSV/workbook taxon resolution added
- Phase 5: lineage-aware browser filtering and taxon detail lineage views added
- Phase 6: graph branch filtering and grouping-rank rollups added

Prototype stabilization already applied:

- review-required taxon rows are reported in preview and skipped on confirm
- dependent workbook findings that reference those taxon IDs are skipped during preview
- exact matches against existing local curated taxa are accepted as local taxonomy resolutions for repeated workbook upserts
- grouped graph views report how many findings were omitted because no ancestor exists at the selected rank

Current focus is no longer “implement Phase 1 first.” The core taxonomy redesign is already active in the codebase.

## Goal

Redesign the taxonomy layer so the database can:

- store the full NCBI lineage for imported taxa
- keep findings linked to the most specific reported taxon
- filter findings by taxonomic branch
- roll findings up to genus, family, order, class, or phylum
- build network graphs grouped by a chosen rank

This plan assumes the database can be wiped and rebuilt. The design therefore optimizes for the clean long-term schema, not backward compatibility.

## Assessment Of The Current Schema

The current schema is not sufficient for lineage-aware taxonomy.

Current limitations:

- `Organism` is a flat record with `scientific_name`, `rank`, and optional `ncbi_taxonomy_id`.
- There is no parent-child tree structure.
- There is no stored lineage or ancestor/descendant relationship table.
- Imports resolve and save only the reported organism row.
- `QualitativeFinding` and `QuantitativeFinding` link directly to that flat row.
- Graph generation works directly from the reported organism row and cannot natively roll up by rank.

Practical consequence:

- the current model can store reported taxa
- it cannot represent taxonomy as a real hierarchy
- it cannot efficiently support branch filtering, lineage traversal, or graph aggregation by rank

## Recommended Architecture

Use a real taxonomy tree centered on `Taxon`, with a closure table for traversal and aggregation.

Recommended core models:

- `Taxon`
- `TaxonClosure`
- `TaxonName` optional but recommended

Recommended design choice:

- use `Taxon.parent` for the immediate tree
- use `TaxonClosure` for ancestor/descendant traversal
- keep findings linked to the reported leaf taxon
- derive rollups and grouped graph nodes from lineage joins

## Rename `Organism` To `Taxon`

`Organism` should be replaced by `Taxon`.

Reason:

- the redesigned table will contain species, genera, families, orders, classes, phyla, and higher nodes
- those are taxa, not organisms
- keeping `Organism` would preserve the old flat mental model in code and UI

Rule after the redesign:

- one canonical row per resolved taxon in `Taxon`
- findings point to `Taxon`
- higher-rank behavior is derived from taxonomy, not stored as duplicated findings

## Why Parent Plus Closure Table

The recommended tree pattern is `parent + closure table`.

Use:

- `Taxon.parent` as the source of truth for direct hierarchy
- `TaxonClosure` as derived relational support for reads

Do not use parent-only as the main design:

- repeated ancestor climbing is awkward for ORM-backed filtering and aggregation
- branch filtering and rank rollups become recursive application logic
- graph grouping becomes harder and less reliable

Do not use nested sets or MPTT as the primary design:

- the main project operations are ancestor lookup, descendant filtering, and rank rollup
- closure tables match those operations more directly

## Recommended Models

### Taxon

Canonical taxonomy node.

Recommended fields:

- `ncbi_taxonomy_id`
- `scientific_name`
- `rank`
- `parent`
- `is_active`
- `notes`
- `created_at`
- `updated_at`

Recommended notes:

- `ncbi_taxonomy_id` should be the canonical unique identifier
- `parent` should be a self-referential foreign key
- `rank` should be validated and normalized
- `on_delete=PROTECT` on `parent` is preferred to avoid accidental subtree damage

### TaxonClosure

Ancestor/descendant traversal table.

Recommended fields:

- `ancestor`
- `descendant`
- `depth`

Recommended semantics:

- one row per ancestor/descendant pair
- include self rows where `ancestor = descendant` and `depth = 0`

### TaxonName

Optional but recommended alias table for name resolution and provenance.

Recommended fields:

- `taxon`
- `name`
- `name_class`
- `source`
- `is_preferred`
- timestamps

Suggested `name_class` values:

- `scientific`
- `synonym`
- `alias`
- `imported_as_written`

`TaxonName` should be used for:

- synonyms
- imported names from workbook rows
- cleaned names used during resolution

It should not replace the canonical `Taxon.scientific_name`.

## Recommended Constraints And Indexes

### Taxon

Recommended constraints:

- unique `ncbi_taxonomy_id`

Recommended indexes:

- index on `scientific_name`
- index on `rank`
- index on `parent`
- composite index on `(rank, scientific_name)`

Optional denormalized caches:

- `genus_id`
- `family_id`
- `order_id`
- `class_id`
- `phylum_id`
- lineage cache fields such as JSON arrays or display lineage strings

These are optional accelerators only. The primary structure should remain `Taxon + TaxonClosure`.

### TaxonClosure

Recommended constraints:

- unique `(ancestor, descendant)`
- check `depth >= 0`

Recommended indexes:

- composite index on `(ancestor, depth, descendant)`
- composite index on `(descendant, depth, ancestor)`

### Findings

Update findings to use `taxon` instead of `organism`.

Keep current uniqueness rules, replacing `organism` with `taxon`.

## Finding Relationships After The Redesign

### QualitativeFinding

- `comparison -> Comparison`
- `taxon -> Taxon`
- `direction`
- `source`
- `import_batch`

### QuantitativeFinding

- `group -> Group`
- `taxon -> Taxon`
- `value_type`
- `value`
- `unit`
- `source`
- `import_batch`

Important rule:

- findings must link to the most specific reported resolved taxon
- do not pre-store duplicate rolled-up finding rows at genus/family/order/class/phylum

This preserves evidence fidelity while still enabling grouped views through taxonomy joins.

## Query Strategy

All lineage-aware reads should run through `TaxonClosure`.

### Upward Traversal

Given a leaf taxon:

- join `TaxonClosure` on `descendant_id = leaf_id`
- join ancestor `Taxon`
- order by `depth`

Use this for:

- lineage display
- ancestor lookup
- finding the nearest genus/family/order/class/phylum ancestor

### Downward Traversal

Given a branch taxon:

- join `TaxonClosure` on `ancestor_id = branch_id`

Use this for:

- subtree browsing
- branch filtering
- counting descendant taxa

### Rank Rollup

To roll a finding up to a chosen rank:

- start from the finding leaf `taxon_id`
- join closure rows where `descendant_id = taxon_id`
- join ancestor `Taxon`
- filter ancestor rank to the selected rank
- choose the nearest ancestor by smallest `depth`

Recommended behavior:

- default to strict rank grouping
- if no ancestor exists at the selected rank, exclude that finding from the grouped result rather than silently inventing a fallback

## Importer Strategy

The importer must resolve the full lineage before writing findings.

Recommended import flow:

1. read the reported taxon name from the source row
2. normalize the string for resolution
3. resolve the taxon against NCBI taxonomy
4. fetch the full lineage for the resolved leaf taxon
5. upsert each lineage node into `Taxon`
6. set `parent` links for each node
7. upsert closure rows for that lineage
8. optionally store source names and aliases in `TaxonName`
9. attach the finding to the resolved reported leaf `Taxon`

Recommended importer behavior:

- resolution should prefer NCBI identifiers when available
- unresolved or ambiguous names should remain staged for curator review
- do not create ad hoc canonical taxa from uncertain name matches
- canonical taxonomy belongs in `Taxon`
- imported-as-written labels belong in `TaxonName` or import notes

## Graph Grouping By Rank

Graphs should be built from leaf-level findings and grouped at query time.

Recommended backend flow:

1. query `QualitativeFinding` as the primary evidence table
2. apply study, direction, disease, and other normal filters
3. optionally apply a taxonomy branch filter using `TaxonClosure`
4. decide the grouping rank:
   - no grouping rank: use the leaf taxon
   - grouping rank present: map each leaf to its nearest ancestor at that rank
5. aggregate grouped findings into graph nodes and edges
6. shape the result into the JSON expected by Cytoscape.js

Recommended edge aggregation fields:

- finding count
- unique study count
- unique source count
- contributing comparison labels
- contributing leaf taxon count

Recommended node metadata:

- grouped rank
- grouped NCBI taxonomy ID
- unique contributing leaf taxon count
- supporting study count

Important rule:

- grouped graph nodes are derived views over stored findings
- do not materialize separate graph-specific rolled-up findings as primary data

## Opinionated Implementation Decisions

Choose these defaults:

- rename `Organism` to `Taxon`
- keep findings linked to the most specific reported taxon
- use `Taxon.parent` plus `TaxonClosure`
- add `TaxonName` for aliases and imported names
- use closure joins for branch filters and rank rollups
- keep graph grouping as query-time aggregation

## Phased Roadmap

### Phase 1: Replace The Flat Taxonomy Model

- remove the old `Organism` model
- add `Taxon`
- add `TaxonClosure`
- add `TaxonName`
- update model diagram and schema docs if needed

Deliverable:

- a clean taxonomy-first schema with no flat organism design remaining

### Phase 2: Repoint Findings And Admin

- rename finding foreign keys from `organism` to `taxon`
- update admin list displays, filters, and search
- expose parent and rank in admin editing where useful
- keep the finding models otherwise unchanged

Deliverable:

- findings linked to canonical `Taxon` rows

### Phase 3: Build Taxonomy Import Services

- add resolver service for NCBI-backed taxon resolution
- add lineage upsert service
- add closure rebuild logic for inserted lineage nodes
- add alias persistence in `TaxonName`
- keep unresolved rows in preview rather than writing partial taxonomy

Deliverable:

- imports that store full lineage, not only the reported leaf

### Phase 4: Update CSV And Workbook Import Paths

- replace organism resolution helpers with taxon resolution helpers
- update preview validation to resolve taxa through the new pipeline
- update workbook import logic to persist full taxonomy before findings
- revise import column naming where appropriate from `organism_*` to `taxon_*`

Deliverable:

- preview and confirm workflow operating on the new taxonomy layer

### Phase 5: Add Lineage-Aware Browser Features

- replace organism list/detail pages with taxon list/detail pages
- add lineage display on the taxon detail page
- add branch-aware filtering for findings
- add optional rank filters and subtree views

Deliverable:

- server-rendered taxonomy browsing that understands hierarchy

### Phase 6: Rebuild Graph Aggregation On Top Of Taxonomy

- add grouping-rank controls to the graph view
- add optional branch filter controls
- map findings to grouped ancestor taxa in backend query logic
- expose grouped node and edge metadata in graph JSON

Deliverable:

- network graphs that can switch between leaf, genus, family, order, class, and phylum views

### Phase 7: Validation And Refinement

- add tests for lineage insertion
- add tests for closure traversal
- add tests for rank rollup behavior
- add tests for branch filtering
- add tests for graph aggregation by rank
- keep prototype hardening narrow and focused on the active import and graph workflow

Deliverable:

- confidence that taxonomy-aware reads and imports behave correctly

## Immediate Next Step

Keep the current prototype path reliable:

- preserve preview-first taxonomy writes
- keep skip-and-report behavior for review-required workbook taxa
- extend tests only where active import or graph behavior is still changing

# Graph Design

## Purpose

The graph view represents organism-organism associations derived from curated `RelativeAssociation` records.

Its purpose is to let users visually explore:

- which organisms are connected
- the strength and type of those associations
- how interactions change under different filters
- which organisms appear central or highly connected

This graph is intended as an exploratory layer on top of the database browser, not as the sole way to inspect the data.

---

## Design principles

- The graph should be generated from database records, not maintained separately.
- The graph should reflect the current filtered query state.
- The graph should remain interpretable and not try to display everything at once.
- Backend graph construction and analysis should happen in Python.
- Frontend rendering should be interactive and browser-native.

Recommended implementation:

- use `networkx` on the backend for graph construction and analysis
- use Cytoscape.js on the frontend for rendering and interaction

---

## Source data

The graph is built primarily from `RelativeAssociation` records.

Each graph edge should correspond to one or more association records between two organisms.

Primary source model:

- `RelativeAssociation`

Supporting models that may enrich graph metadata:

- `Organism`
- `Sample`
- `Study`
- `CoreMetadata`

---

## Graph semantics

### Node meaning

A node represents one `Organism`.

Nodes should map directly to organism records in the database.

### Edge meaning

An edge represents an association between two organisms.

In the simplest version, one edge can correspond to one `RelativeAssociation` record.

In more advanced versions, multiple association records between the same organism pair may be aggregated into one edge depending on active filters or graph mode.

---

## Node fields

Suggested node payload fields:

- `id`: internal `Organism.id`
- `label`: organism scientific name
- `taxonomy_id`: `Organism.ncbi_taxonomy_id`
- `rank`: `Organism.taxonomic_rank`
- `genus`: optional
- `species`: optional
- `degree`: optional computed graph degree
- `group`: optional grouping/category for coloring
- `study_count`: optional number of supporting studies
- `sample_count`: optional number of supporting samples

Example:

```json
{
  "id": "42",
  "label": "Faecalibacterium prausnitzii",
  "taxonomy_id": 853,
  "rank": "species",
  "group": "species",
  "degree": 8
}

# Roadmap

## Goal

Build a small Django application for curated microbiome association data with:

- a public/internal home page
- a clean database browser
- an interactive organism interaction graph
- admin-based manual data entry
- CSV-based bulk ingestion

The project is intentionally small-scale and admin-focused.

---

## Guiding principles

- keep the stack simple
- favor server-rendered Django templates
- use Bootstrap for UI
- use HTMX for incremental interactivity where useful
- use PostgreSQL
- use Django admin heavily
- keep provenance and validation explicit
- avoid unnecessary frontend complexity

---

## Recommended stack

- Django
- PostgreSQL
- Bootstrap 5
- HTMX
- `django-filter`
- `django-tables2`
- `networkx`
- Cytoscape.js

---

## Phase 1: project setup

### Objectives

- initialize Django project
- configure PostgreSQL
- define project apps
- set up environment configuration
- configure static files and templates

### Deliverables

- working Django project
- database connection configured
- base template and Bootstrap integration
- local development setup documented

### Suggested app structure

Option A:

- `core`
- `database`
- `imports`

Option B:

- `core`
- `studies`
- `organisms`
- `associations`
- `imports`

For a small project, fewer apps are acceptable.

---

## Phase 2: schema implementation

### Objectives

- implement the core models from `docs/schema.md`
- add model constraints
- create migrations
- verify the schema in PostgreSQL
- configure Django admin for all core entities

### Priority models

- `Study`
- `Sample`
- `Organism`
- `RelativeAssociation`
- `CoreMetadata`
- `MetadataVariable`
- `MetadataValue`
- `ImportBatch`

### Deliverables

- `models.py`
- migrations
- admin registration
- basic model tests for integrity constraints

---

## Phase 3: admin and manual CRUD

### Objectives

- make all core entities manageable from Django admin
- improve admin usability
- support item-by-item record creation and editing

### Deliverables

- searchable admin for key models
- filters in admin
- inline views where useful
- readable list displays

### Notes

Use Django admin as the default interface for manual curation.

---

## Phase 4: CSV import workflow

### Objectives

- create an admin-only import flow
- validate CSV structure and required columns
- preview parsed rows before import
- report errors and duplicates
- persist import provenance

### Deliverables

- upload form
- validation layer
- preview page
- import confirmation flow
- import summary page
- `ImportBatch` integration

### Notes

Do not rely only on admin raw forms for CSV ingestion.

---

## Phase 5: database browser

### Objectives

- build a modern browser UI for:
  - studies
  - samples
  - organisms
  - relative associations
- add sorting, filtering, search, and pagination
- keep the UX clean and admin-friendly

### Deliverables

- list pages
- detail pages
- filter forms
- sortable tables
- responsive layout

### Recommended tooling

- `django-filter`
- `django-tables2`
- HTMX for partial reloads if needed

### Notes

The `RelativeAssociation` browser is likely the most important page.

---

## Phase 6: home page

### Objectives

- create a polished landing page
- explain the project and database contents
- show summary statistics if available

### Suggested content

- project description
- why microbiome interactions matter
- counts of studies, samples, organisms, and associations
- links to browser, graph, and admin/import pages

---

## Phase 7: network graph

### Objectives

- expose filtered interaction data
- build a graph from associations
- render it interactively in the browser

### Backend plan

- query filtered `RelativeAssociation` records
- create graph using `networkx`
- compute node/edge attributes as needed
- serialize nodes and edges to JSON

### Frontend plan

- render with Cytoscape.js
- support zoom, drag, and click interactions
- optionally color by taxonomic rank or condition
- optionally size nodes by degree or importance

### Deliverables

- graph page
- graph API/JSON endpoint or view context
- interactive node and edge display

---

## Phase 8: refinement and validation

### Objectives

- improve performance
- add tests
- refine filters and admin UX
- harden import validation
- polish styling

### Deliverables

- integration tests
- import tests
- browser/filter tests
- cleaned templates and styling

---

## Version 1 milestone

Version 1 should include:

- schema implementation
- admin CRUD
- CSV import
- browser for core tables
- basic graph page

Not required for V1:

- complex public authentication
- SPA frontend
- advanced taxonomy ontology modeling
- highly dynamic dashboards

---

## Likely implementation order

1. project setup
2. models and migrations
3. admin configuration
4. import flow
5. browser views
6. home page
7. graph page
8. testing and polish

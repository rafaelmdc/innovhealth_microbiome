# Microbiome Association Database

A Django-based database and browser for curated microbiome study data, focused on organism-organism associations, structured sample metadata, and interactive network exploration.

## Project goal

This project aims to centralize curated microbiome association data from published studies in a reproducible and queryable format.

The database is designed to support:

- study-level metadata
- cohort/sample-level metadata
- organism/taxon records
- pairwise organism-organism associations
- flexible metadata storage for heterogeneous variables
- CSV-based ingestion workflows
- interactive browsing and filtering
- network visualization of organism interactions

The intended users are primarily internal/admin users rather than a large public user base.

---

## Planned features

- Home page describing the microbiome project and database purpose
- Modern database browser with filtering, sorting, and search
- Interactive network graph of organism interactions
- Admin-only CSV import flow
- Admin CRUD for manual record creation and editing

---

## Recommended stack

- Django
- PostgreSQL
- Bootstrap 5
- Django templates
- HTMX
- Django admin
- `django-filter`
- `django-tables2`
- `networkx` for backend graph generation/analysis
- `Cytoscape.js` for frontend graph rendering

---

## Architecture summary

The schema uses a hybrid design:

- common, high-frequency metadata is stored in structured tables
- more heterogeneous metadata is stored through a controlled EAV model

Core entities:

- `Study`
- `Sample`
- `Organism`
- `RelativeAssociation`
- `CoreMetadata`
- `MetadataVariable`
- `MetadataValue`
- `ImportBatch`

Optional entities:

- `AlphaMetric`
- `BetaMetric`

See `docs/schema.md` for the full schema description.

---

## Website plan

### Home page
A simple project landing page explaining:

- project purpose
- what the database contains
- why microbiome associations matter
- links to browser, graph, and admin tools

### Database browser
A server-rendered browser for:

- studies
- samples
- organisms
- relative associations

The browser should support:

- sorting
- filtering
- search
- pagination
- clean, modern UX

### Network graph
The graph page should:

- query filtered association data
- build a graph with `networkx`
- serialize nodes and edges as JSON
- render interactively in the browser with Cytoscape.js

### Data entry
Two paths are planned:

- Django admin for item-by-item editing
- custom CSV import workflow for batch ingestion

---

## Development status

This repo is currently in the planning and schema definition phase.

Next major steps:

1. finalize the schema
2. implement Django models
3. configure Django admin
4. build CSV import flow
5. build browser views
6. build graph view

See `docs/roadmap.md` for the implementation roadmap.

---

## Notes for contributors and coding agents

This project intentionally favors:

- Django simplicity over overengineered frontend architecture
- server-rendered pages over a SPA
- explicit schema constraints
- admin-friendly workflows
- provenance-aware imports

Before making schema or architecture changes, read:

- `docs/schema.md`
- `docs/roadmap.md`
- `AGENTS.md`

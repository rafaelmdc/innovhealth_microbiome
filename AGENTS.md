# Agent instructions

This repository contains a small Django-based microbiome association database and browser.

Your job is to help implement the project incrementally while preserving the documented architecture and keeping the codebase simple, readable, and admin-friendly.

Before making architectural, schema, or implementation decisions, read:

- `README.md`
- `docs/schema.md`
- `docs/roadmap.md`
- `docs/graph.md`

If those documents conflict with the current code, prefer the documented architecture unless the user explicitly asks to revise it.

---

## Project intent

This is a relatively small project with no complex end-user account system.

The application should provide:

- a home page describing the microbiome project
- a clean database browser with filtering, sorting, search, and pagination
- an interactive organism interaction graph
- admin-driven manual data entry
- admin-only CSV import workflows

The project is intentionally not a heavy SPA and should not be overengineered.

---

## Core stack expectations

Prefer the following stack unless explicitly told otherwise:

- Django
- PostgreSQL
- Django templates
- Bootstrap 5
- HTMX where useful but not everywhere
- Django admin for internal CRUD
- `django-filter`
- `django-tables2`
- `networkx` for backend graph construction/analysis
- Cytoscape.js for frontend graph rendering

Do not introduce React, Next.js, a full SPA, or unnecessary frontend complexity unless explicitly requested.

Do not introduce unnecessary infrastructure, background workers, microservices, or extra deployment complexity unless the project genuinely needs them.

---

Current implementation priority: project startup, define Django models and migrations from `docs/schema.md`, then register them in Django admin.

---

## Schema expectations

The schema is already defined in `docs/schema.md` and should be preserved.

Core priority models:

- `Study`
- `Sample`
- `Organism`
- `RelativeAssociation`
- `CoreMetadata`
- `MetadataVariable`
- `MetadataValue`
- `ImportBatch`

Optional models that may be added later if needed:

- `AlphaMetric`
- `BetaMetric`

When implementing models, preserve the documented field meanings and constraints.

### Important schema rules

- Use explicit foreign key naming and clear model relationships.
- Preserve uniqueness constraints documented in `docs/schema.md`.
- Preserve check constraints where applicable.
- Keep `CoreMetadata` minimal and structured.
- Keep flexible metadata in `MetadataVariable` + `MetadataValue`.
- Ensure EAV values remain controlled and validated.
- Preserve provenance via `ImportBatch`.

### Pairwise data rules

For pairwise tables such as `RelativeAssociation` and `BetaMetric`:

- enforce canonical ordering when appropriate
- prevent self-pairs
- preserve uniqueness constraints
- do not duplicate reverse pairs unless explicitly required by the design

---

## Graph expectations

The graph design is documented in `docs/graph.md`.

Use the following architecture:

- query association data with Django ORM
- build graph structures in Python with `networkx`
- compute lightweight graph attributes only when useful
- serialize nodes and edges as JSON
- render interactively in the browser with Cytoscape.js

Do not use raw matplotlib or raw NetworkX static plots as the main web graph solution.

Do not design the graph feature as a separate disconnected system; it should remain a view over database records.

---

## Website expectations

Favor server-rendered pages and incremental enhancements.

The site should include:

### Home page
A clear landing page explaining:
- project purpose
- what the database contains
- why microbiome interactions matter
- navigation to browser, graph, and admin/import tools

### Database browser
A clean browser for:
- studies
- samples
- organisms
- relative associations

The browser should support:
- sorting
- filtering
- search
- pagination
- clear detail views

The `RelativeAssociation` browser is especially important.

### Data entry
Use:
- Django admin for item-by-item editing
- custom admin-only CSV import flows for bulk ingestion

CSV imports should support:
- upload
- validation
- preview
- duplicate checks
- confirmation
- import result summaries

Imported data should remain traceable through `ImportBatch`.

---

## Implementation style

When implementing features:

- make the smallest correct change
- prefer simple, explicit code over clever abstractions
- match existing naming and structure
- avoid unrelated refactors
- preserve admin usability
- preserve schema integrity
- keep templates readable
- keep query logic understandable

Do not add abstractions “for future flexibility” unless they clearly solve a current need.

Do not redesign the project structure casually once a reasonable structure exists.

---

## Working order

Unless the user asks otherwise, prefer working in this order:

1. project setup
2. models and migrations
3. admin configuration
4. CSV import workflow
5. browser views and templates
6. home page
7. graph feature
8. testing and refinement

When adding a feature, first check whether the required supporting models, constraints, and admin tooling already exist.

---

## Coding decisions

### Django
- Prefer class-based generic views when they keep code simpler.
- Use Django forms and model validation where appropriate.
- Keep business logic out of templates.
- Keep model methods focused and small.

### Templates
- Use Bootstrap 5 for layout and styling.
- Use HTMX only where it clearly improves UX.
- Avoid heavy custom JavaScript unless needed for the graph.

### Queries
- Avoid unnecessary N+1 queries.
- Use `select_related` and `prefetch_related` where appropriate.
- Keep filtering logic explicit and testable.

### Admin
- Make admin genuinely useful.
- Add search fields, filters, and list displays for important models.
- Use inlines where they improve editing clarity.

### Imports
- Validate data before writing to the database.
- Prefer clear import services/helpers over huge view functions.
- Surface errors clearly.
- Preserve provenance and import summaries.

---

## Documentation expectations

When adding or changing important architecture, update the relevant docs:

- `README.md`
- `docs/schema.md`
- `docs/roadmap.md`
- `docs/graph.md`

Do not let implementation drift too far from the written docs without updating them.

---

## When uncertain

If something is unclear:

1. read the project docs first
2. preserve the documented schema and architecture
3. choose the simpler implementation
4. avoid introducing new major dependencies without strong justification

If there is a tradeoff between elegance and maintainability, prefer maintainability.

If there is a tradeoff between frontend sophistication and development simplicity, prefer simplicity unless the user asks for richer interactivity.

---

## Output expectations

When proposing changes:

- explain the purpose briefly
- identify the main files involved
- keep plans short
- implement incrementally
- mention validation steps when relevant

For non-trivial work, prefer a short plan before large edits.

After major milestones, summarize what was built, what remains, and any risks or open questions.

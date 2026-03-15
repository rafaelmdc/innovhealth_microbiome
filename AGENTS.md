# Agent instructions

This repository contains a Django-based microbiome literature database and browser.

Your job is to help refactor and extend the project incrementally while preserving the documented architecture, keeping the codebase simple, readable, scalable, and admin-friendly.

Before making architectural, schema, or implementation decisions, read:

- `README.md`
- `docs/schema.md`
- `docs/roadmap.md`
- `docs/graph.md`
- `docs/import_pipeline.md`

If those documents conflict with the current code, prefer the documented architecture unless the user explicitly asks to revise it.

---

## Project intent

This project is a curated microbiome literature database focused on storing:

- publication-level study records
- study groups / cohorts / subgroups
- explicit comparisons between groups
- qualitative directional findings such as enriched / depleted taxa
- quantitative findings such as relative abundance values
- optional alpha and beta diversity metrics
- light structured and flexible metadata
- provenance-aware imports

The application should provide:

- a home page describing the microbiome project
- a clean database browser with filtering, sorting, search, and pagination
- an interactive graph view derived from stored findings
- admin-driven manual data entry
- admin-only staged import workflows

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

## Current implementation priority

Current implementation priority is to align the whole codebase with the new schema and methodology:

- move away from the old `RelativeAssociation`-centered design
- treat the main extraction units as:
  - qualitative findings in a comparison
  - quantitative values in a group
- preserve a compact, presentation-friendly, scalable architecture
- support staged import workflows for workbook-based data ingestion

---

## Schema expectations

The schema is defined in `docs/schema.md` and should follow the new compact model.

### Core priority models

- `Study`
- `Group`
- `Comparison`
- `Organism`
- `QualitativeFinding`
- `QuantitativeFinding`
- `ImportBatch`

### Flexible metadata models

- `MetadataVariable`
- `MetadataValue`

### Optional models

- `AlphaMetric`
- `BetaMetric`

---

## Core schema logic

### Study
Represents a paper / publication.

### Group
Represents a study arm, cohort, subgroup, or analytical group such as:

- disease
- control
- mild disease
- severe disease
- discovery cohort
- validation cohort

This replaces the old vague `Sample` concept.

### Comparison
Represents a comparison between two groups.

Examples:
- Parkinson’s disease vs healthy control
- severe CKD vs mild CKD

This model is essential for qualitative enriched/depleted logic.

### Organism
Represents a microbial taxon.

### QualitativeFinding
Represents a directional finding for one organism in one comparison.

Examples:
- enriched
- depleted
- increased
- decreased

This is now one of the main analytical tables.

### QuantitativeFinding
Represents one exact numeric value for one organism in one group.

Examples:
- relative abundance
- later possibly absolute abundance

This replaces the old incorrect assumption that relative abundance should be modeled as organism A relative to organism B.

### ImportBatch
Tracks provenance and status for imports.

### MetadataVariable / MetadataValue
Provides a slim EAV layer for heterogeneous metadata that should not become dedicated columns.

### AlphaMetric / BetaMetric
Optional extensions for direct diversity values when available.

---

## Important schema rules

- Use explicit foreign key naming and clear model relationships.
- Preserve uniqueness constraints documented in `docs/schema.md`.
- Preserve check constraints where applicable.
- Keep direct columns minimal and focused on common fields.
- Keep flexible metadata in `MetadataVariable` + `MetadataValue`.
- Keep EAV controlled and validated.
- Preserve provenance through `ImportBatch`.
- Do not reintroduce the old organism-organism abundance logic.

---

## Important modeling rules

### Relative abundance
Relative abundance must be modeled as:

- one organism
- in one group
- with one numeric value

It must **not** be modeled as a relationship between organism A and organism B.

### Qualitative findings
Qualitative statements such as enriched/depleted must be modeled relative to a `Comparison`.

A directional finding without a comparison context is incomplete.

### Old pairwise logic
The old `RelativeAssociation` model should not remain the main data path.

If true organism-organism pairwise relationships are needed later, they should be added as a separate optional model, not reused for abundance or directional findings.

### Metadata
Do not reintroduce a bloated metadata system.

Use:
- direct columns for common metadata
- slim EAV for sparse or inconsistent metadata

### Optional diversity models
Keep `AlphaMetric` and `BetaMetric` optional and lightweight.
Do not make the rest of the codebase depend on them.

---

## Graph expectations

The graph design is documented in `docs/graph.md`.

Use the following architecture:

- query findings with Django ORM
- build graph structures in Python with `networkx`
- compute lightweight graph attributes only when useful
- serialize nodes and edges as JSON
- render interactively in the browser with Cytoscape.js

Do not use raw matplotlib or raw NetworkX static plots as the main web graph solution.

Do not design the graph feature as a separate disconnected system; it should remain a view over database records.

### New graph semantics

Prefer graphs based on the new model, especially:

- comparison/taxon networks
- disease/taxon networks
- qualitative enriched/depleted edges

`QuantitativeFinding` should act as a supporting evidence layer rather than the default graph edge type.

Do not build the graph around the old `RelativeAssociation` logic.

---

## Website expectations

Favor server-rendered pages and incremental enhancements.

The site should include:

### Home page
A clear landing page explaining:
- project purpose
- what the database contains
- why microbiome changes matter
- navigation to browser, graph, and admin/import tools

### Database browser
A clean browser for:
- studies
- groups
- comparisons
- organisms
- qualitative findings
- quantitative findings

The browser should support:
- sorting
- filtering
- search
- pagination
- clear detail views

The most important browsing views are:
- `QualitativeFinding`
- `QuantitativeFinding`

### Data entry
Use:
- Django admin for item-by-item editing
- custom admin-only staged import flows for bulk ingestion

Imports should support:
- upload
- validation
- preview
- duplicate checks
- confirmation
- import result summaries

Imported data must remain traceable through `ImportBatch`.

---

## Import expectations

The import system should align with the new data model.

It should support:
- qualitative imports into `QualitativeFinding`
- quantitative imports into `QuantitativeFinding`
- optional alpha imports into `AlphaMetric`
- optional beta imports into `BetaMetric`
- metadata imports into `MetadataValue`
- provenance tracking via `ImportBatch`

The staged workbook import workflow remains important.

Prioritize:
1. workbook read
2. parsing
3. paper status filtering
4. organism resolution preview
5. preview of mapped findings before commit

Parsers should be tolerant but validated.
Do not assume every import source contains all fields.

---

## Implementation style

When implementing features:

- make the smallest correct change
- prefer simple, explicit code over clever abstractions
- match existing naming and structure where still reasonable
- avoid unrelated refactors
- preserve admin usability
- preserve schema integrity
- keep templates readable
- keep query logic understandable

Do not add abstractions “for future flexibility” unless they clearly solve a current need.

Do not casually redesign the project structure once a reasonable structure exists.

---

## Working order

Unless the user asks otherwise, prefer working in this order:

1. models and migrations
2. admin configuration
3. import workflow
4. browser views and templates
5. home page
6. graph feature
7. testing and refinement
8. documentation updates

When adding a feature, first check whether the required supporting models, constraints, admin tooling, and import logic already exist.

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
- `docs/import_pipeline.md`

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

If there is a tradeoff between preserving old code and aligning with the new model, prefer the new model.

---

## Output expectations

When proposing changes:

- explain the purpose briefly
- identify the main files involved
- keep plans short
- implement incrementally
- mention validation steps when relevant

For non-trivial work, prefer a short plan before large edits.

After major milestones, summarize:
- what was built
- what remains
- any risks
- any open questions

---

## Final instruction

The old architecture centered on `RelativeAssociation` and organism-organism pairwise abundance logic is no longer the correct model for the project’s real data.

The new core must remain centered on:

- `Study`
- `Group`
- `Comparison`
- `Organism`
- `QualitativeFinding`
- `QuantitativeFinding`

with:

- slim EAV metadata
- optional alpha/beta models
- provenance-aware imports
- browser and graph features built on top of this structure

When in doubt, choose the implementation that makes this model clearer, smaller, and easier to maintain.
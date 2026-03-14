# Schema

## Overview

This project stores curated microbiome association data using a Django/PostgreSQL schema designed for:

- publication-level study records
- analyzable sample/cohort/group records
- organism/taxon records
- pairwise organism-organism relationships
- structured core metadata
- flexible metadata through a controlled EAV model
- provenance-aware CSV imports

The schema is intentionally hybrid:

- frequently queried fields are stored in structured tables
- heterogeneous metadata is stored in a controlled EAV system

---

## Core design principles

- `Study` represents the publication or source paper.
- `Sample` represents a subgroup/cohort/unit extracted from a study.
- `Organism` represents a microbial taxon.
- `RelativeAssociation` stores a pairwise organism-organism relationship within a sample/group.
- `CoreMetadata` stores common structured metadata fields.
- `MetadataVariable` and `MetadataValue` store flexible sample metadata.
- `ImportBatch` tracks import provenance and ingestion status.
- `AlphaMetric` and `BetaMetric` are optional and can be added later.

---

## Main models

### Study

Stores publication-level information.

Fields:

- `id`
- `source_doi`
- `title`
- `country`
- `journal`
- `publication_year`
- `notes`
- `created_at`
- `updated_at`

Rules:

- `source_doi` should be unique when present

---

### Sample

Stores the analyzable study unit.

This may represent:

- a cohort
- a subgroup
- a site-specific subset
- a methodological subgroup
- another meaningful extracted analytical unit

Fields:

- `id`
- `study_id`
- `label`
- `site`
- `method`
- `cohort`
- `sample_size`
- `notes`
- `created_at`
- `updated_at`

Rules:

- unique constraint on `(study_id, label)`

---

### Organism

Stores taxon information.

Fields:

- `id`
- `ncbi_taxonomy_id`
- `scientific_name`
- `taxonomic_rank`
- `parent_taxonomy_id` optional self-reference
- `genus`
- `species`
- `notes`

Rules:

- `ncbi_taxonomy_id` should be unique and indexed
- use a normal internal Django `id` primary key rather than making taxonomy ID the PK

---

### RelativeAssociation

Stores a pairwise relationship between two organisms in a given sample/group.

Fields:

- `id`
- `sample_id`
- `organism_1_id`
- `organism_2_id`
- `association_type`
- `value`
- `sign`
- `p_value`
- `q_value`
- `method`
- `confidence`
- `notes`
- `import_batch_id`
- `created_at`
- `updated_at`

Rules:

- canonical organism ordering should be enforced
- unique constraint on `(sample_id, organism_1_id, organism_2_id, association_type)`
- `organism_1_id != organism_2_id`

Notes:

This table is the main source for browser exploration and graph generation.

---

### CoreMetadata

Stores structured sample-level metadata that is expected to be queried frequently.

Fields:

- `sample_id` one-to-one with `Sample`
- `condition`
- `male_percent`
- `age_mean`
- `age_sd`
- `bmi_mean`
- `bmi_sd`
- `notes`

Rules:

- keep only commonly queried fields here
- do not use this table as a dumping ground for all metadata

---

### MetadataVariable

Defines controlled metadata variables for the EAV system.

Fields:

- `id`
- `name`
- `display_name`
- `domain`
- `value_type`
- `default_unit`
- `description`
- `is_filterable`
- `allowed_values`
- `created_at`
- `updated_at`

Notes:

This table controls metadata consistency.

---

### MetadataValue

Stores flexible sample-level metadata values.

Fields:

- `id`
- `sample_id`
- `variable_id`
- `value_float`
- `value_int`
- `value_text`
- `value_bool`
- `unit`
- `raw_value`
- `variation`
- `notes`
- `import_batch_id`

Rules:

- unique constraint on `(sample_id, variable_id)`
- exactly one typed value field should be populated

---

### ImportBatch

Tracks import provenance for CSV ingestion.

Fields:

- `id`
- `name`
- `source_file`
- `import_type`
- `uploaded_at`
- `notes`
- `success_count`
- `error_count`
- `status`

Purpose:

- auditability
- validation tracking
- error reporting
- import provenance

---

## Optional models

### AlphaMetric

Stores within-sample/group diversity metrics.

Fields:

- `id`
- `sample_id`
- `metric_type`
- `value`
- `unit`
- `notes`
- `import_batch_id`

Rules:

- unique constraint on `(sample_id, metric_type)`

---

### BetaMetric

Stores pairwise between-sample/group diversity metrics.

Fields:

- `id`
- `sample_a_id`
- `sample_b_id`
- `metric_type`
- `value`
- `notes`
- `import_batch_id`

Rules:

- canonical sample ordering should be enforced
- unique constraint on `(sample_a_id, sample_b_id, metric_type)`
- `sample_a_id != sample_b_id`

---

## Integrity rules

### Uniqueness

- `Study.source_doi` unique when present
- `Organism.ncbi_taxonomy_id` unique
- `Sample(study_id, label)` unique
- `RelativeAssociation(sample_id, organism_1_id, organism_2_id, association_type)` unique
- `MetadataValue(sample_id, variable_id)` unique
- `AlphaMetric(sample_id, metric_type)` unique
- `BetaMetric(sample_a_id, sample_b_id, metric_type)` unique

### Checks

- `sample_size >= 0`
- `male_percent` between `0` and `100`
- `p_value` between `0` and `1`
- `q_value` between `0` and `1`
- organism pair members must differ
- beta pair members must differ
- only one typed metadata value field should be filled

---

## Implementation notes

### Django naming
Use explicit FK names such as:

- `study_id`
- `sample_id`
- `organism_1_id`
- `organism_2_id`

Avoid ambiguous names like `sample` or duplicate FK labels.

### Network graph
Use:

- `networkx` on the backend
- Cytoscape.js on the frontend

Do not rely on raw NetworkX plots for the main web visualization.

Recommended graph pipeline:

1. query filtered associations
2. build graph with `networkx`
3. compute graph properties if needed
4. serialize nodes and edges to JSON
5. render interactively with Cytoscape.js

### CSV ingestion
All imported records should be traceable through `ImportBatch`.

CSV import flow should support:

- upload
- validation
- preview
- duplicate checks
- confirmation
- result summary

---

## Version 1 priority models

For the first usable version, prioritize:

- `Study`
- `Sample`
- `Organism`
- `RelativeAssociation`
- `CoreMetadata`
- `MetadataVariable`
- `MetadataValue`
- `ImportBatch`

Add `AlphaMetric` and `BetaMetric` later unless they are immediately required.

# MINdb — Directional Taxon Network Concept

## Goal

Add a new exploratory network view to MINdb that connects taxa to other taxa based on how they are reported within the same comparison context.

This view should help users explore recurring patterns such as:

- taxa that often appear increased together
- taxa that often appear decreased together
- taxa that often appear in opposite directions within the same disease comparison

---

## What the network means

The network is derived from curated **qualitative findings**.

For a given comparison:

- if two taxa are reported in the same direction, they form a **same-direction** relationship
- if one is increased and the other is decreased, they form an **opposite-direction** relationship

When this pattern repeats across multiple comparisons, the edge becomes stronger.

This should be presented as a **pattern view**, not as proof of direct biological interaction.

---

## Important framing

This network is:

- exploratory
- derived from shared comparison context
- based on repeated directional co-patterns

This network is **not**:

- causal
- mechanistic
- statistical proof of interaction
- a correlation network

Suggested wording:

> A network connecting taxa that are repeatedly reported in the same or opposite directions within shared comparison contexts.

---

## Best first scope

The first version should stay small and focused:

- build the network from qualitative findings
- derive taxon-taxon relationships from findings inside the same comparison
- allow users to explore one taxonomic rank at a time
- allow filtering by disease or condition
- show whether relationships are mostly same-direction or opposite-direction

The point is to make the view understandable and useful, not overly ambitious.

---

## Why this is a good fit for MINdb

MINdb already stores directional findings in disease comparison contexts.

That makes it well suited for a derived network that asks:

- which taxa tend to move together?
- which taxa tend to move in opposite directions?
- which recurring microbiome patterns appear across similar disease comparisons?

This creates a second network perspective that complements the existing comparison-centered view.

---

## Recommended interpretation for users

Users should understand edges as:

- **same-direction**: the two taxa are often reported moving in the same direction in the same comparison context
- **opposite-direction**: the two taxa are often reported moving in opposite directions in the same comparison context
- **mixed**: no clear dominant pattern

This keeps the view honest and interpretable.

---

## Display philosophy

This network should feel like an exploratory lens over the curated literature, not a hard biological claim.

It should help users notice patterns like:

- recurring co-enrichment
- recurring co-depletion
- recurring opposed shifts

A disease-specific view is likely the most interpretable default.

---

## Naming

Recommended feature name:

**Directional Taxon Network**

Other acceptable variants:

- Taxon Relationship Network
- Co-shift Network
- Directional Relationship View

`Directional Taxon Network` is the clearest.

---

## Short description for the product

> An exploratory network that connects taxa based on repeated same-direction or opposite-direction patterns within shared disease comparison contexts.

---

## Caveat text

> This view summarizes recurring qualitative direction patterns from curated findings. It is intended for exploration and should not be interpreted as causal, mechanistic, or statistical evidence of direct taxon-taxon interaction.

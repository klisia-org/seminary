# Architecture Decision Records (ADRs)

This directory contains Architecture Decision Records for SeminaryERP. ADRs capture important technical and design decisions along with their context and consequences.

## Format

Each ADR follows this structure:

```markdown
# NNN — Title

**Date:** YYYY-MM-DD
**Status:** Accepted | Superseded by NNN | Deprecated

## Context

What situation forced this decision?

## Decision

What did we decide?

## Consequences

What does this make easier? What does it make harder?
What questions remain open?
```

## Guidelines

- Keep ADRs short (~200 words)
- Write at the moment of decision, while reasoning is fresh
- One decision per document
- Number sequentially: `001-`, `002-`, etc.
- ADRs are immutable once accepted — if a decision changes, write a new ADR and mark the old one as superseded

## Audience

ADRs are for contributors and developers. They are excluded from the public documentation site.

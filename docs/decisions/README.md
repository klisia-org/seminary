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

- Keep ADRs short. Size has been drifting up. Aim at 100 words for context and 100 words for consequences. Explain the decisions succintly, but covering briefly the rejected alternatives if they have some merit. The goal is not to show we considered every alternative, just document good-not-best ones and why the choice.
- Write at the moment of decision, while reasoning is fresh
- One decision per document, unless they group naturally and don't require a very long ADR. Otherwise, use parent and children: the parent describing the context, big idea, and components --> children describe components.
- Number sequentially: `001-`, `002-`, etc.
- ADRs are immutable once accepted — if a decision changes, write a new ADR and mark the old one as superseded. Execution may be ammended later, with a notation on the header, mentioning the section.

## Audience

ADRs are for contributors and developers. They are excluded from the public documentation site. NEVER mention ADR or decisions in public-facing documents, such as doctypes descriptions or labels. 

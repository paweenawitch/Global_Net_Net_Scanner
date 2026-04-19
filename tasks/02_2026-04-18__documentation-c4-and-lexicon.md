# Task: Documentation C4 architecture & Financial Lexicon

## Goal
Document the Clean Architecture layout using Mermaid C4 diagrams and create a rigid financial lexicon defining every metric.

## Done means
- [x] Create `docs/architecture.md` containing Mermaid C4 diagrams (Domain <- Application <- Infrastructure).
- [x] Create `docs/domain_lexicon.md` that mathematically defines all metrics (DilutionCAGR, ROCE_adj, FCF Yield).
- [x] Tests added/updated as required (N/A for documentation but review passes)
- [x] `scripts/check.*` passes

## Constraints / must not change
- Keep the C4 models aligned strictly with Uncle Bob's definitions.
- The lexicon must reflect the current truth of code implementations.

## Scope
IN:
- Markdown documentation files in `docs/` or root directory.
- Mermaid.js syntax for C4.

OUT:
- Refactoring the actual codebase to match the desired architecture (this task is purely documentation of the desired/current state).

## Suggested files (optional)
- `docs/architecture.md`
- `docs/domain_lexicon.md`

## Review Feedback
- **Correlation**: Highly accurate. `architecture.md` has a very precise Clean Architecture C4 Diagram that maps to the implemented rules in your Python constraint test.
- **Lexicon details**: The financial lexicon covers required metrics mathematically in a language-agnostic format, enforcing determinism across whatever programming logic operates on it. Domain terminology is well isolated.

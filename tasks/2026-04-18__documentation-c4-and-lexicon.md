# Task: Documentation C4 architecture & Financial Lexicon

## Goal
Document the Clean Architecture layout using Mermaid C4 diagrams and create a rigid financial lexicon defining every metric.

## Done means
- [ ] Create `docs/architecture.md` containing Mermaid C4 diagrams (Domain <- Application <- Infrastructure).
- [ ] Create `docs/domain_lexicon.md` that mathematically defines all metrics (DilutionCAGR, ROCE_adj, FCF Yield).
- [ ] Tests added/updated as required (N/A for documentation but review passes)
- [ ] `scripts/check.*` passes

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

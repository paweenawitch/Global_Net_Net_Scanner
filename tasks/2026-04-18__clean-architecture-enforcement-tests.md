# Task: Clean Architecture Enforcement Tests

## Goal
Enforce Uncle Bob's Dependency Rule automatically via tests. Prevent outer layers (application, infrastructure) from leaking into the `domain` layer.

## Done means
- [ ] Create `tests/architecture/test_dependency_rules.py`.
- [ ] Implement AST parser or use `pytest-arch` / `importlab` to scan `domain/` imports.
- [ ] Test fails if `domain/` imports from `application/`, `infrastructure/`, or `ui/`.
- [ ] Integrate test into CI/CD or `scripts/check.sh`.
- [ ] Tests added/updated as required
- [ ] `scripts/check.*` passes

## Constraints / must not change
- Do not modify existing domain logic, purely add test assertions.
- Keep tests fast (sub 1 second) so they can run locally aggressively.

## Scope
IN:
- AST parsing logic for `import` and `from ... import` statements.
- Root namespace `domain`.

OUT:
- Refactoring existing dependency violations (that would be a follow-up task).

## Suggested files (optional)
- `tests/architecture/test_dependency_rules.py`

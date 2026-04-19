# Task: Clean Architecture Enforcement Tests

## Goal
Enforce Uncle Bob's Dependency Rule automatically via tests. Prevent outer layers (application, infrastructure) from leaking into the `domain` layer.

## Done means
- [x] Create `tests/architecture/test_dependency_rules.py`.
- [x] Implement AST parser or use `pytest-arch` / `importlab` to scan `domain/` imports.
- [x] Test fails if `domain/` imports from `application/`, `infrastructure/`, or `ui/`.
- [x] Integrate test into CI/CD or `scripts/check.sh`.
- [x] Tests added/updated as required
- [x] `scripts/check.*` passes

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

## Review Feedback
- **Correlation**: The code correctly accomplishes all goals outline above (AST parser implemented, `check.ps1` available).
- **Code implementation note**: *[RESOLVED]* You successfully updated the AST logic to capture relative imports! Now it effectively stops any `from ..application import ...` or `from .. import application` from breaking the internal domain bounds using `node.level`.
- **Platform note**: *[RESOLVED]* Switching to `python -m pytest tests/` in `scripts/check.ps1` natively hooks into Windows testing environments seamlessly. Tested, and successfully executes all 17 root test assertions with 0 failures!

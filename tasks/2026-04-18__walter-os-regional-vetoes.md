# Task: Walter OS Market-Specific Hard Vetoes

## Goal
Expand the "Universal Vetoes" to include regional traps, like Keiretsu cross-holdings in Japan.

## Done means
- [ ] Define the interface for market-specific vetoes extending the universal veto concept.
- [ ] Implement a specific regional veto (e.g., Japanese Keiretsu Cross-Holding Veto).
- [ ] Integrate market-specific vetoes into the main screening path.
- [ ] Tests added/updated as required
- [ ] `scripts/check.*` passes

## Constraints / must not change
- Must not override or bypass the core Universal Owner-Style Vetoes.
- Must execute deterministically.

## Scope
IN:
- `domain/models/vetoes.py` or similar veto domain logic.
- Region-specific logic modules.

OUT:
- Vetoing based on qualitative or predictive LLM logic.

## Suggested files (optional)
- `domain/models/vetoes.py`
- `domain/playbooks/veto_engine.py`

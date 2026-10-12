# ALEX 2501 — Baseline Audit & Test Harness v0.1

## Scope
Deterministic *prototype* of selected rules in the ALEX Behavioral Engine v3.3 specification. No LLM, state persistence, live profile, or automated behavioral judgments. This module does not claim that v3.3 is fully implemented.

## Requirements
Debian 13, Python 3.11+; Python standard library only. Commands below are compatible with fish 4.x.

## Run (fish)
```fish
cd ~/alex2501_baseline
python3 -m unittest discover -s tests -v
python3 alex2501.py example.json
```

## Source-derived rules
- v3.3 §15.1–15.4: nine risk weights; weighted risk; domain threshold >=85; integer risk bands.
- v3.3 §16: safety override when aggregate >=61, critical risk, or high-consequence decision.
- v3.3 §31.1–31.4: seven decision weights; base score and two penalties 0–30; hard constraint violations cannot be repaired by penalty.
- v3.3 §32: actually compute candidate scores.
- v3.3 §36: mode precedence.

## Explicit ALEX 2501 extensions (NOT asserted as existing v3.3 requirements)
1. Treat **all nine risk domains** as critical-override eligible by default; configurable in Python because v3.3 does not enumerate 'critical domains'.
2. For fractional aggregate risks, apply continuous band cutoffs <=20, <=40, <=60, <=80; v3.3 uses integer bands.
3. On ties, report `TIE_REQUIRES_POLICY` rather than selecting arbitrarily.
4. Preserve negative final scores; no clamping rule appears in v3.3.
5. Reject missing criteria, unknown criteria, non-finite values, and unspecified hard-constraint status.
6. Do not invent missing numeric input values; return validation errors.
7. `high_consequence` is an explicit caller-provided boolean; the engine cannot independently identify it yet.

## Known limitations / next steps
- No rubric maps user language to each 0–100 score; values are caller supplied.
- `hard_constraints_passed` is asserted by the caller, not independently verified.
- No state machine, hysteresis, persistence, memory provenance, or freshness checks.
- No audit log or reproducible model input/output provenance.
- No automatic safety refusal; the override is a signal for the response policy.
- Mode triggers are not inferred; mode priority alone is implemented.
- No uncertainty mode alias resolution (`CRITICAL_UNCERTAINTY` versus `UNCERTAINTY_MODE`).
- Does not validate the entire 4,140-line original specification or its internal consistency.

## Project rule
Keep ALEX v3.3 as an unchanged baseline. Only promote new rules after tests and explicit acceptance.

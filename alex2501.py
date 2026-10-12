"""ALEX 2501 baseline deterministic evaluator; Python 3.11+, stdlib only."""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from typing import Mapping
import json
import sys

D = Decimal
DECISION_WEIGHTS = {
    'STATE_MATCH': D('0.20'), 'INTENT_MATCH': D('0.20'),
    'TASK_MATCH': D('0.15'), 'LONG_TERM_GOAL_MATCH': D('0.10'),
    'ACTION_MATCH': D('0.10'), 'STYLE_MATCH': D('0.05'),
    'EPISTEMIC_FIT': D('0.20'),
}
RISK_WEIGHTS = {
    'physical_risk': D('0.17'), 'medical_risk': D('0.14'),
    'financial_risk': D('0.14'), 'legal_risk': D('0.10'),
    'security_risk': D('0.10'), 'irreversible_risk': D('0.14'),
    'misinformation_risk': D('0.07'),
    'social_reputational_risk': D('0.07'),
    'technical_system_risk': D('0.07'),
}
# ALEX 2501 extension: explicit list needed because v3.3 says "critical domain"
# without unambiguously enumerating which of the nine domains are critical.
DEFAULT_CRITICAL_DOMAINS = frozenset(RISK_WEIGHTS)
MODE_PRIORITY = ('SAFETY_OVERRIDE', 'CRITICAL_UNCERTAINTY', 'DEESCALATION',
                 'CLARIFICATION', 'ANTI_PERFECTIONISM', 'NORMAL_SCORING')

class ValidationError(ValueError):
    pass

def _number(value: object, field: str, maximum: str = '100') -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float, str, Decimal)):
        raise ValidationError(f'{field}: expected numeric value')
    try:
        number = D(str(value))
    except Exception as exc:
        raise ValidationError(f'{field}: invalid number') from exc
    if not number.is_finite() or not D('0') <= number <= D(maximum):
        raise ValidationError(f'{field}: expected finite number in [0, {maximum}]')
    return number

def _weighted(values: Mapping[str, object], weights: Mapping[str, Decimal]) -> Decimal:
    if not isinstance(values, Mapping):
        raise ValidationError('expected object of numeric criteria')
    missing, extra = set(weights) - set(values), set(values) - set(weights)
    if missing or extra:
        raise ValidationError(f'criteria mismatch: missing={sorted(missing)}, extra={sorted(extra)}')
    return sum((_number(values[k], k) * w for k, w in weights.items()), D('0'))

def verify_weights() -> None:
    for name, weights in [('decision', DECISION_WEIGHTS), ('risk', RISK_WEIGHTS)]:
        if sum(weights.values(), D('0')) != D('1.00'):
            raise ValidationError(f'{name} weights must sum to 1.00')

def risk_level(score: Decimal) -> str:
    # Extension: continuous interpretation of integer bands from v3.3.
    if score <= 20: return 'LOW'
    if score <= 40: return 'MODERATE'
    if score <= 60: return 'ELEVATED'
    if score <= 80: return 'HIGH'
    return 'CRITICAL'

def evaluate_risk(values: Mapping[str, object], *, critical_domains=DEFAULT_CRITICAL_DOMAINS,
                  high_consequence: bool = False) -> dict:
    if not isinstance(high_consequence, bool):
        raise ValidationError('high_consequence must be boolean')
    if not set(critical_domains) <= set(RISK_WEIGHTS):
        raise ValidationError('unknown critical domain')
    overall = _weighted(values, RISK_WEIGHTS)
    critical = any(_number(values[k], k) >= 85 for k in critical_domains)
    return {'overall_risk': str(overall), 'risk_level': risk_level(overall),
            'critical_risk': critical,
            'safety_override': overall >= 61 or critical or high_consequence,
            'high_consequence': high_consequence}

def evaluate_candidate(candidate: Mapping[str, object]) -> dict:
    if not isinstance(candidate, Mapping):
        raise ValidationError('candidate must be object')
    identifier = candidate.get('id')
    if not isinstance(identifier, str) or not identifier.strip():
        raise ValidationError('candidate id must be nonempty string')
    valid = candidate.get('hard_constraints_passed')
    if not isinstance(valid, bool):
        raise ValidationError('hard_constraints_passed must be explicit boolean')
    base = _weighted(candidate.get('criteria'), DECISION_WEIGHTS)
    risk_penalty = _number(candidate.get('risk_penalty'), 'risk_penalty', '30')
    contradiction_penalty = _number(candidate.get('contradiction_penalty'), 'contradiction_penalty', '30')
    final = base - risk_penalty - contradiction_penalty
    # Negative scores are retained: v3.3 does not define clamping.
    return {'id': identifier, 'valid': valid, 'base_score': str(base),
            'risk_penalty': str(risk_penalty),
            'contradiction_penalty': str(contradiction_penalty),
            'final_score': str(final),
            'rejection_reason': None if valid else 'hard_constraints_failed'}

def choose(candidates: list[Mapping[str, object]]) -> dict:
    if not isinstance(candidates, list) or not candidates:
        raise ValidationError('candidates must be nonempty list')
    evaluated = [evaluate_candidate(c) for c in candidates]
    ids = [c['id'] for c in evaluated]
    if len(ids) != len(set(ids)):
        raise ValidationError('candidate ids must be unique')
    eligible = [c for c in evaluated if c['valid']]
    if not eligible:
        return {'selected_id': None, 'status': 'NO_VALID_CANDIDATE', 'candidates': evaluated}
    best_score = max(D(c['final_score']) for c in eligible)
    winners = [c for c in eligible if D(c['final_score']) == best_score]
    # Extension: ties explicitly unresolved, rather than silently biased by input order.
    return {'selected_id': winners[0]['id'] if len(winners) == 1 else None,
            'status': 'SELECTED' if len(winners) == 1 else 'TIE_REQUIRES_POLICY',
            'tied_ids': sorted(c['id'] for c in winners) if len(winners) > 1 else [],
            'candidates': evaluated}

def select_mode(active_modes: list[str]) -> str:
    if not isinstance(active_modes, list) or any(m not in MODE_PRIORITY for m in active_modes):
        raise ValidationError('unknown mode')
    return next((mode for mode in MODE_PRIORITY if mode in active_modes), 'NORMAL_SCORING')

def run(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise ValidationError('input must be a JSON object')
    verify_weights()
    result = {'engine': 'ALEX_2501_BASELINE_V0.1'}
    if 'risk' in payload:
        result['risk'] = evaluate_risk(payload['risk'], high_consequence=payload.get('high_consequence', False))
    if 'candidates' in payload:
        result['selection'] = choose(payload['candidates'])
    if 'active_modes' in payload:
        result['mode'] = select_mode(payload['active_modes'])
    return result

if __name__ == '__main__':
    try:
        if len(sys.argv) != 2:
            raise ValidationError('usage: python3 alex2501.py INPUT.json')
        with open(sys.argv[1], encoding='utf-8') as handle:
            payload = json.load(handle)
        print(json.dumps(run(payload), indent=2, ensure_ascii=False))
    except (ValidationError, OSError, json.JSONDecodeError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        sys.exit(2)

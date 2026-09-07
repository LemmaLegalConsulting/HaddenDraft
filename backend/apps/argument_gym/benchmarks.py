"""Deterministic grading of closed-world legal reasoning probes.

Gold proposition/span bindings are curated in the suite. This is deliberately
not a general entailment detector and does not grade free-form brief quality.
"""

from copy import deepcopy
import hashlib
import json
from pathlib import Path

import yaml


DEFAULT_SUITE = Path(__file__).resolve().parents[3] / 'content/argument-gym/minimal-pairs.yaml'
_MISSING = object()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def normalize_span(text):
    # No punctuation, case, OCR glyph, or semantic substitutions are permitted.
    return ' '.join(text.split())


def evidence_key(item):
    if not isinstance(item, dict) or set(item) != {'source_id', 'span'}:
        raise ValueError('Evidence requires exactly source_id and span.')
    if not all(isinstance(item[k], str) and item[k].strip() for k in item):
        raise ValueError('Evidence source_id and span must be nonempty strings.')
    return item['source_id'], normalize_span(item['span'])


def load_suite(path=DEFAULT_SUITE):
    suite = yaml.safe_load(Path(path).read_text(encoding='utf-8'))
    if suite.get('schema_version') != 1 or suite.get('synthetic') is not True:
        raise ValueError('Expected a version 1 synthetic benchmark suite.')
    cases = []
    pair_ids = set()
    for pair in suite['pairs']:
        if pair['id'] in pair_ids or len(pair['variants']) != 2:
            raise ValueError('Pair ids must be unique and each pair must have two variants.')
        pair_ids.add(pair['id'])
        variable = pair['variable']
        if variable not in pair['input']:
            raise ValueError('The decisive variable must be an existing input field.')
        if pair['variants'][0]['value'] == pair['variants'][1]['value']:
            raise ValueError('A minimal pair must change its decisive variable.')
        if pair['variants'][0]['expected']['decisions'] == pair['variants'][1]['expected']['decisions']:
            raise ValueError('A minimal pair must change the expected decision.')
        for variant in pair['variants']:
            payload = deepcopy(pair['input'])
            payload[variable] = variant['value']
            cases.append(dict(id=f"{pair['id']}/{variant['id']}", pair_id=pair['id'],
                              priority=pair['priority'], input=payload, expected=variant['expected']))
    cases.extend(dict(case, pair_id=None) for case in suite.get('cases', []))
    if not cases:
        raise ValueError('A benchmark suite must contain scenarios.')
    ids = [case['id'] for case in cases]
    if len(ids) != len(set(ids)):
        raise ValueError('Scenario ids must be unique.')
    for case in cases:
        expected = case['expected']
        if (not isinstance(expected.get('decisions'), dict) or not expected['decisions']
                or not isinstance(expected.get('evidence'), list)):
            raise ValueError('Gold requires nonempty decisions and an evidence array.')
        sources = case['input'].get('sources', [])
        texts = {source['id']: source['text'] for source in sources}
        if len(texts) != len(sources):
            raise ValueError('Source ids must be unique within a scenario.')
        if 'record_text' in case['input']:
            texts['record'] = case['input']['record_text']
        for evidence in case['expected']['evidence']:
            source_id, span = evidence_key(evidence)
            if source_id not in texts or span not in normalize_span(texts[source_id]):
                raise ValueError(f"Gold evidence is absent from {case['id']}: {source_id}")
    return cases


def model_input(case):
    """No gold values, pair names, priorities, or sibling answers reach the model."""
    return dict(scenario=deepcopy(case['input']),
                decision_fields=list(case['expected']['decisions']))


def grade_case(case, response=_MISSING):
    if response is _MISSING:
        return dict(id=case['id'], status='not_run', findings=['No response supplied.'])
    findings = []
    if not isinstance(response, dict) or set(response) != {'decisions', 'evidence'}:
        return dict(id=case['id'], status='fail', findings=['Expected exactly decisions and evidence.'])
    # JSON comparison preserves types (True must not pass for integer 1).
    if digest(response['decisions']) != digest(case['expected']['decisions']):
        findings.append('Decisions differ from the curated expectation.')
    try:
        if not isinstance(response['evidence'], list):
            raise ValueError('Evidence must be an array.')
        actual = [evidence_key(item) for item in response['evidence']]
        expected = [evidence_key(item) for item in case['expected']['evidence']]
        if len(actual) != len(set(actual)) or set(actual) != set(expected):
            findings.append('Proposition-to-source spans or attribution differ from the curated expectation.')
    except (ValueError, TypeError) as exc:
        findings.append(str(exc))
    return dict(id=case['id'], status='fail' if findings else 'pass', findings=findings)


def evaluate(cases, responses):
    if not isinstance(responses, dict):
        raise ValueError('Responses must be an object keyed by scenario id.')
    unknown = sorted(set(responses) - {case['id'] for case in cases})
    if unknown:
        raise ValueError(f'Unknown response ids: {unknown}')
    results = [dict(grade_case(case, responses.get(case['id'], _MISSING)),
                    priority=case['priority'], expected=deepcopy(case['expected']),
                    input_sha256=digest(model_input(case))) for case in cases]
    by_id = {result['id']: result for result in results}
    pairs = {}
    for case in cases:
        if case['pair_id']:
            pairs.setdefault(case['pair_id'], []).append(by_id[case['id']]['status'])
    # Both individually correct answers are required; merely changing answers is insufficient.
    pairs = {key: ('not_run' if 'not_run' in values else 'pass' if all(v == 'pass' for v in values) else 'fail')
             for key, values in pairs.items()}
    return dict(schema_version=1, suite_sha256=digest(cases), results=results, pairs=pairs,
                complete=all(result['status'] != 'not_run' for result in results),
                passed=all(result['status'] == 'pass' for result in results))

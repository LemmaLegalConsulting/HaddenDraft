"""Harness regression tests, not evidence of model reasoning performance."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

import yaml
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase

from apps.ai.gym_benchmark import benchmark_prompt, run_benchmark_case
from apps.argument_gym.benchmarks import DEFAULT_SUITE, evaluate, grade_case, load_suite, model_input


class MinimalPairBenchmarkTests(SimpleTestCase):
    def setUp(self):
        self.cases = load_suite()
        self.by_id = {case['id']: case for case in self.cases}

    def test_six_pairs_change_exactly_one_input_field_and_require_different_decisions(self):
        pairs = {}
        for case in self.cases:
            if case['pair_id']:
                pairs.setdefault(case['pair_id'], []).append(case)
        self.assertEqual(len(pairs), 6)
        for cases in pairs.values():
            with self.subTest(pair=cases[0]['pair_id']):
                left, right = cases
                self.assertEqual(sum(left['input'][k] != right['input'][k] for k in left['input']), 1)
                self.assertNotEqual(left['expected']['decisions'], right['expected']['decisions'])
                # A constant answer cannot pass both halves of any pair.
                self.assertEqual(grade_case(right, left['expected'])['status'], 'fail')
                self.assertEqual(grade_case(left, right['expected'])['status'], 'fail')

    def test_curated_answers_pass_harness_and_empty_run_is_not_evidence(self):
        report = evaluate(self.cases, {c['id']: c['expected'] for c in self.cases})
        self.assertTrue(report['passed'])
        self.assertEqual(set(report['pairs'].values()), {'pass'})
        empty = evaluate(self.cases, {})
        self.assertFalse(empty['passed'])
        self.assertFalse(empty['complete'])
        self.assertEqual(set(empty['pairs'].values()), {'not_run'})

    def test_binding_authority_beats_more_semantically_similar_nonbinding_case(self):
        case = self.by_id['appellate-district/eighth']
        response = deepcopy(case['expected'])
        response['decisions'].update(governing='case-b', case_a='persuasive', case_b='binding')
        self.assertEqual(grade_case(case, response)['status'], 'fail')

    def test_each_material_proposition_requires_its_curated_support_span(self):
        case = self.by_id['entailment/supported']
        for evidence in ([], [{'source_id': 'keywords', 'span': 'The tenant requested dismissal and disputed warning X.'}],
                         [{'source_id': 'contradiction', 'span': 'Omitting warning X does not require dismissal.'}],
                         [{'source_id': 'support', 'span': 'Omitting warning X always requires dismissal.'}]):
            with self.subTest(evidence=evidence):
                response = dict(decisions=case['expected']['decisions'], evidence=evidence)
                self.assertEqual(grade_case(case, response)['status'], 'fail')

    def test_contradicted_is_distinct_from_not_established(self):
        case = self.by_id['entailed-source-contradicts-claim']
        response = deepcopy(case['expected'])
        for status in ('SUPPORTED', 'NOT_ESTABLISHED'):
            response['decisions']['status'] = status
            self.assertEqual(grade_case(case, response)['status'], 'fail')

    def test_only_whitespace_is_normalized_in_evidence(self):
        case = self.by_id['entailment/supported']
        response = deepcopy(case['expected'])
        response['evidence'][0]['span'] = 'Omitting warning X\n requires   dismissal.'
        self.assertEqual(grade_case(case, response)['status'], 'pass')
        response['evidence'][0]['span'] = 'omitting warning X requires dismissal.'
        self.assertEqual(grade_case(case, response)['status'], 'fail')

    def test_poisoned_quote_attribution_and_treatment_cannot_pass(self):
        for case_id, field, poisoned in [('quote-misattributed', 'status', 'SUPPORTED'),
                                        ('quote-paraphrase', 'status', 'SUPPORTED'),
                                        ('bad-treatment', 'governing', 'case-a'),
                                        ('wrong-precedential-level', 'case_a', 'binding')]:
            with self.subTest(case=case_id):
                case = self.by_id[case_id]
                response = deepcopy(case['expected'])
                response['decisions'][field] = poisoned
                self.assertEqual(grade_case(case, response)['status'], 'fail')

    def test_malformed_extra_and_duplicate_evidence_fail_closed(self):
        case = self.by_id['entailment/supported']
        for response in (None, [], {}, {'decisions': {}}, dict(case['expected'], reviewed=True),
                         dict(decisions=case['expected']['decisions'], evidence='source'),
                         dict(decisions=case['expected']['decisions'], evidence=[{}, {}]),
                         dict(decisions=case['expected']['decisions'], evidence=case['expected']['evidence'] * 2)):
            with self.subTest(response=response):
                self.assertEqual(grade_case(case, response)['status'], 'fail')
        with self.assertRaises(ValueError):
            evaluate(self.cases, {'unknown': {}})

    def test_pair_requires_both_correct_not_just_different_answers(self):
        responses = {c['id']: deepcopy(c['expected']) for c in self.cases}
        responses['appellate-district/eighth']['decisions']['governing'] = 'invented'
        report = evaluate(self.cases, responses)
        self.assertTrue(report['complete'])
        self.assertFalse(report['passed'])
        self.assertEqual(report['pairs']['appellate-district'], 'fail')

    def test_prompt_and_live_adapter_do_not_receive_gold_or_database_overrides(self):
        for case in self.cases:
            payload = model_input(case)
            self.assertEqual(set(payload), {'scenario', 'decision_fields'})
            self.assertEqual(payload['scenario'], case['input'])
            prompt = benchmark_prompt(payload)  # SimpleTestCase forbids database access.
            self.assertIn(json.dumps(payload, sort_keys=True), prompt.user)
        client = Mock()
        client.complete.return_value = json.dumps(self.cases[0]['expected'])
        response, raw = run_benchmark_case(model_input(self.cases[0]), client=client)
        self.assertEqual(response, self.cases[0]['expected'])
        client.complete.assert_called_once()
        client.complete.return_value = 'This is not JSON.'
        response, raw = run_benchmark_case(model_input(self.cases[0]), client=client)
        self.assertEqual(grade_case(self.cases[0], response)['status'], 'fail')

    def test_replay_command_writes_failures_and_missing_results_before_nonzero_exit(self):
        with TemporaryDirectory() as directory:
            inputs, output = Path(directory) / 'responses.json', Path(directory) / 'report.json'
            inputs.write_text('{}')
            with self.assertRaises(CommandError):
                call_command('run_gym_benchmark', responses=str(inputs), output=str(output))
            report = json.loads(output.read_text())
            self.assertFalse(report['complete'])
            self.assertTrue(report['prompt_sha256'])
            inputs.write_text(json.dumps({c['id']: c['expected'] for c in self.cases}))
            call_command('run_gym_benchmark', responses=str(inputs), output=str(output))
            self.assertTrue(json.loads(output.read_text())['passed'])

    @patch('apps.argument_gym.management.commands.run_gym_benchmark.OpenAICompatibleClient')
    def test_provider_failure_is_not_run_and_report_redacts_error_text(self, client_type):
        client_type.return_value.complete.side_effect = RuntimeError('secret-provider-token')
        with TemporaryDirectory() as directory:
            output = Path(directory) / 'report.json'
            with self.assertRaises(CommandError):
                call_command('run_gym_benchmark', live=True, output=str(output))
            self.assertNotIn('secret-provider-token', output.read_text())
            report = json.loads(output.read_text())
            self.assertEqual({r['status'] for r in report['results']}, {'not_run'})

    def test_export_inputs_never_exports_gold(self):
        with TemporaryDirectory() as directory:
            output = Path(directory) / 'inputs.json'
            call_command('run_gym_benchmark', export_inputs=True, output=str(output))
            exported = json.loads(output.read_text())
            self.assertEqual(len(exported), len(self.cases))
            self.assertTrue(all(set(value) == {'scenario', 'decision_fields'} for value in exported.values()))

    def test_suite_rejects_absent_gold_spans_and_non_counterfactual_pairs(self):
        original = yaml.safe_load(DEFAULT_SUITE.read_text())
        absent_span = deepcopy(original)
        absent_span['pairs'][0]['variants'][0]['expected']['evidence'][0]['span'] = 'Invented quotation.'
        same_input = deepcopy(original)
        same_input['pairs'][0]['variants'][1]['value'] = same_input['pairs'][0]['variants'][0]['value']
        same_decisions = deepcopy(original)
        same_decisions['pairs'][0]['variants'][1]['expected'] = same_decisions['pairs'][0]['variants'][0]['expected']
        duplicate_id = deepcopy(original)
        duplicate_id['cases'].append(duplicate_id['cases'][0])
        for suite in (absent_span, same_input, same_decisions, duplicate_id):
            with self.subTest(suite=suite['pairs'][0]['id']), TemporaryDirectory() as directory:
                path = Path(directory) / 'suite.yaml'
                path.write_text(yaml.safe_dump(suite))
                with self.assertRaises(ValueError):
                    load_suite(path)

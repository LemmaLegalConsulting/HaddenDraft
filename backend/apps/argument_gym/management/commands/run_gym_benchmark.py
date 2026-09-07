"""Run or replay the synthetic minimal-pair benchmark; never auto-substitute gold."""
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.utils.timezone import now

from apps.ai.gym_benchmark import benchmark_prompt, run_benchmark_case
from apps.ai.openai_client import OpenAICompatibleClient
from apps.argument_gym.benchmarks import DEFAULT_SUITE, digest, evaluate, load_suite, model_input


class Command(BaseCommand):
    help = 'Grade recorded responses or explicitly run live synthetic Argument Gym probes.'

    def add_arguments(self, parser):
        parser.add_argument('--suite', default=str(DEFAULT_SUITE))
        mode = parser.add_mutually_exclusive_group(required=True)
        mode.add_argument('--responses', help='JSON object keyed by scenario id; each value has decisions and evidence.')
        mode.add_argument('--live', action='store_true', help='Make one configured model call per scenario (incurs API costs).')
        mode.add_argument('--export-inputs', action='store_true', help='Write model inputs without gold; no model calls.')
        parser.add_argument('--output', required=True)
        parser.add_argument('--model')
        parser.add_argument('--reasoning-level')

    def handle(self, *args, **options):
        try:
            cases = load_suite(options['suite'])
            if options['export_inputs']:
                Path(options['output']).write_text(json.dumps({c['id']: model_input(c) for c in cases}, indent=2) + '\n')
                return
            raw, errors = {}, {}
            if options['responses']:
                responses = json.loads(Path(options['responses']).read_text())
                execution = {'mode': 'replay', 'model': 'unverified external responses'}
            else:
                client = OpenAICompatibleClient()
                responses = {}
                prompt = benchmark_prompt(model_input(cases[0]))
                execution = dict(mode='live', model=options['model'] or prompt.default_model,
                                 reasoning_level=options['reasoning_level'] or prompt.default_reasoning_level)
                for case in cases:
                    try:
                        responses[case['id']], raw[case['id']] = run_benchmark_case(
                            model_input(case), client=client, model=options['model'],
                            reasoning_level=options['reasoning_level'])
                    except Exception as exc:
                        # Do not place provider errors (which may contain credentials) in artifacts.
                        errors[case['id']] = type(exc).__name__
            report = evaluate(cases, responses)
            report.update(execution=execution, created_at=now().isoformat(), responses=responses,
                          raw_responses=raw, execution_errors=errors,
                          prompt_sha256=digest(Path(benchmark_prompt(model_input(cases[0])).source).read_text()))
            Path(options['output']).write_text(json.dumps(report, indent=2) + '\n')
        except (ValueError, OSError) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(f"Wrote {len(report['results'])} scenario results to {options['output']}")
        if not report['passed']:
            raise CommandError('Benchmark has failures or unrun scenarios; inspect the report.')

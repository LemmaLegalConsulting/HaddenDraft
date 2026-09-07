"""File-only prompt execution for the Argument Gym reasoning benchmark."""
import json

from apps.ai.prompt_catalog import render_prompt


def benchmark_prompt(payload):
    return render_prompt('argument_gym.benchmark', allow_database_override=False,
                         scenario_json=json.dumps(payload, sort_keys=True))


def run_benchmark_case(payload, *, client, model=None, reasoning_level=None):
    prompt = benchmark_prompt(payload)
    raw = client.complete(system=prompt.system, user=prompt.user,
                          model=model or prompt.default_model,
                          reasoning_level=reasoning_level or prompt.default_reasoning_level,
                          temperature=0)
    try:
        response = json.loads(raw)
    except (ValueError, TypeError):
        response = {'invalid_json': True}
    return response, raw

"""Run every fixture through the Argument Gym in both conditions.

One run per fixture per condition, sixteen in all. The Gym receives the brief
text and, where the fixture has one, the record -- and nothing else. It never
sees fixture.json, mutations.yaml, the mutation class, the gold vulnerability,
or which condition it is looking at: workspace and document titles carry the
fixture id and the word "control"/"mutant" nowhere.

Everything about the run that could differ between the two conditions is held
fixed: the same model, the same temperature, the same prompts from the file
catalog, the same isolated database seeded the same way, the same record bytes.
The brief text is the only thing that differs, which is the whole design.

Adjudication -- did a challenge name the registered vulnerability -- is NOT done
here. This writes the raw challenges; scoring is a separate, human-checkable
step so that the run cannot quietly grade itself.
"""

import argparse
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import tarfile
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit

import django

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.conf import settings  # noqa: E402
from django.contrib.auth import get_user_model  # noqa: E402
from django.db import close_old_connections, connections  # noqa: E402
from django.test import override_settings  # noqa: E402
from django.utils.timezone import now  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from routing import RoutedCapture, note_prompt, role_for  # noqa: E402
from apps.ai.prompt_catalog import render_prompt  # noqa: E402
from apps.argument_gym import checks, ingestion  # noqa: E402
from apps.argument_gym.models import GymDocument, GymRun, GymWorkspace  # noqa: E402
from apps.argument_gym.pipeline import execute_run  # noqa: E402
from apps.rules.court_profiles import sync_court_profile_seeds  # noqa: E402
from apps.rules.legal_rules import sync_legal_rule_seeds  # noqa: E402
from apps.sources.models import SourceConfiguration  # noqa: E402
from apps.sources.registry import connector_registry  # noqa: E402

EXPERIMENT = ROOT / "lexis_real_briefs" / "experiment"
FIXTURES = EXPERIMENT / "fixtures"   # overridden by --fixtures-dir
CONDITIONS = {"control": "normalized", "mutant": "mutant"}
SOURCE_IDS = ["ohio-cases", "ohio-statutes", "ohio-ordinances", "treatise"]


def family(model):
    """The model's vendor family, which is what 'same-family judge' asks about."""
    name = model.lower()
    for token, label in (("deepseek", "deepseek"), ("gpt", "openai"), ("mistral", "mistral"),
                         ("llama", "meta"), ("grok", "xai"), ("kimi", "moonshot"),
                         ("phi", "microsoft"), ("gemini", "google"), ("cohere", "cohere")):
        if token in name:
            return label
    return name


def same_family(attack_model, judge_model):
    return family(attack_model) == family(judge_model)


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def ingest_text(text):
    """Structure a fixture's plain text the way an upload would be structured.

    The fixtures are text, not .docx, because normalization and mutation happen
    on text; but the Gym anchors every challenge to a structural unit, and a
    document with no units is refused before the first stage. So the same
    `structure_units` the uploader uses is applied here, from paragraphs split
    on the blank line that separates them in a fixture.

    There is no formatting block, because plain text has no margins or type
    size. The court-format checks will report those as unmeasured -- identically
    in both conditions, which is what matters.
    """
    paragraphs = [{"text": block.strip(), "page": None}
                  for block in text.split("\n\n") if block.strip()]
    units = ingestion.structure_units(paragraphs)
    return {
        "extractor": "experiment-fixture-text",
        "pageCount": None,
        "paragraphCount": len(paragraphs),
        "units": units,
        "checksum": ingestion.text_checksum(text),
        "formatting": {},
        "split": None,
        "truncated": False,
    }


class RecordingRegistry:
    def __init__(self, live):
        self.live, self.calls = live, []

    def search(self, query, **kwargs):
        results = connector_registry.search(query, **kwargs) if self.live else []
        self.calls.append({"query": query, "source_ids": kwargs.get("source_ids"),
                           "results": [result.to_dict() for result in results]})
        return results


def run_one(fixture, condition, user, *, directory, live, models, reasoning, enabled_checks):
    """One condition of one fixture. Blind: no label reaches the workspace."""
    home = FIXTURES / fixture["fixture_id"]
    side = CONDITIONS[condition]
    brief_path = home / side / "brief.txt"
    brief_text = brief_path.read_text()

    # The title is the filing's own title. It carries no fixture id and no
    # condition, so nothing in the prompt tells the model which arm it is in.
    workspace = GymWorkspace.objects.create(
        owner=user, title=fixture["document"]["title"],
        jurisdiction=fixture["document"]["jurisdiction"],
        enabled_checks=enabled_checks,
    )
    brief = GymDocument.objects.create(
        workspace=workspace, role=GymDocument.BRIEF_UNDER_TEST,
        source_type=GymDocument.UPLOAD, title=fixture["document"]["title"],
        pleading_type=fixture["document"]["pleading_type"],
        extracted_text=brief_text,
        extraction_metadata=ingest_text(brief_text),
    )
    record_ids = []
    for attachment in sorted((home / side / "attachments").glob("*.txt")):
        record_text = attachment.read_text()
        document = GymDocument.objects.create(
            workspace=workspace, role=GymDocument.CASE_RECORD,
            source_type=GymDocument.UPLOAD, title=attachment.stem,
            extracted_text=record_text,
            extraction_metadata=ingest_text(record_text),
        )
        record_ids.append(document.id)

    run = GymRun.objects.create(workspace=workspace, brief=brief, configuration={
        "benchmark": "lexis-mutation-2026-09",
        "mode": "live" if live else "offline",
        "sourceIds": SOURCE_IDS,
    })
    registry = RecordingRegistry(live)
    with RoutedCapture(directory, live=live, models=models, reasoning=reasoning) as capture:
        run = execute_run(run, connector_registry=registry)

    # Preserve complete role outputs and exclude any run where a model call or
    # the Judge's one-ruling-per-candidate contract failed.
    degraded = capture.degraded(run.stage_trace)
    opponent_calls = capture.payloads_for("attack")
    judge_calls = capture.payloads_for("judge")

    findings = run.check_results or {}
    challenges = list(run.challenges.order_by("ordinal", "id").values(
        "ordinal", "category", "severity", "confidence", "opponent_argument",
        "why_it_matters", "target", "legal_sources", "record_sources",
        "judge_assessment", "judge_verdict", "suggested_response",
        "coaching_recommendation", "disposition"))
    return {
        "fixture_id": fixture["fixture_id"],
        "condition": condition,
        "case_family_id": fixture["case_family_id"],
        "stratum": fixture["stratum"],
        "run_id": run.id,
        "run_at": now().isoformat(),
        "status": "degraded" if degraded else run.status,
        "pipeline_status": run.status,
        "degraded": degraded,
        "error": "Pipeline failed; inspect the run database" if run.error else "",
        "brief_sha256": sha256_file(brief_path),
        "brief_chars": len(brief_text),
        "record_documents": len(record_ids),
        "attack_model": models["attack"],
        "judge_model": models["judge"],
        "base_model": models["base"],
        "same_family": same_family(models["attack"], models["judge"]),
        "reasoning": reasoning,
        "unit_budget_chars": settings.ARGUMENT_GYM_UNIT_BUDGET_CHARS,
        "units": len(brief.structure_units or []),
        "court": run.court_detection,
        "deterministic_findings": {key: len(value.get("findings", []))
                                   for key, value in findings.items()},
        "checks_run": run.checks_run,
        "check_results": run.check_results,
        "correctness_tests": [
            test
            for result in (run.check_results or {}).values()
            for test in result.get("tests", [])
        ],
        "rule_audit": run.rule_audit,
        "compliance": run.compliance,
        "challenges": challenges,
        "challenge_count": len(challenges),
        "opponent_calls": opponent_calls,
        "judge_calls": judge_calls,
        "verdict": run.assessment_verdict,
        "assessment": run.assessment,
        "stage_trace": run.stage_trace,
        "research_trace": run.research_trace,
        "retrieval": registry.calls,
        "model_calls": capture.summary(),
    }


def record_state(directory, fixtures, args, models):
    def git(*argv):
        return subprocess.check_output(["git", *argv], cwd=ROOT).decode()

    names = git("ls-files", "-co", "--exclude-standard").splitlines()
    selected = sorted({
        name for name in names
        if name.startswith(("backend/", "prompts/", "scripts/", "content/drafting-rules/",
                            "content/court-rules/", "content/legal-rules/",
                            "content/argument-gym/"))
        or name == "requirements.txt"
    })
    with tarfile.open(directory / "code-snapshot.tar.gz", "w:gz") as archive:
        for name in selected:
            if (ROOT / name).is_file():
                archive.add(ROOT / name, arcname=name)
    # The working tree is dirty; the patch is what makes the run reproducible.
    (directory / "working-tree.patch").write_text(git("diff", "HEAD", "--binary"))
    (directory / "dependencies.txt").write_bytes(
        subprocess.check_output([sys.executable, "-m", "pip", "freeze"]))

    config = SourceConfiguration.effective_settings("openai", {
        "api_key": settings.OPENAI_API_KEY, "base_url": settings.OPENAI_BASE_URL,
    })
    if args.live and not config.get("api_key"):
        raise SystemExit("No configured model credential; a live run needs one.")

    return {
        "registry_id": "lexis-mutation-2026-09",
        "created_at": now().isoformat(),
        "mode": "live" if args.live else "offline",
        "git_commit": git("rev-parse", "HEAD").strip(),
        "git_status": git("status", "--short"),
        "command": [sys.executable, *sys.argv],
        "python": sys.version,
        "cell": args.cell or "single-model",
        "models": models,
        "model": models["base"],
        "attack_family": family(models["attack"]),
        "judge_family": family(models["judge"]),
        "same_family_judge": same_family(models["attack"], models["judge"]),
        "role_routing": "named Opponent prompts -> attack; legacy and correctness Judge "
                        "prompts -> judge; everything else -> base",
        "reasoning": args.reasoning,
        "temperature": 0,
        "provider_host": urlsplit(config.get("base_url") or "https://api.openai.com").hostname,
        "model_version_note": "Requested deployment alias; the provider's snapshot "
                              "identity is not exposed to the application client.",
        "code_sha256": sha256_file(directory / "code-snapshot.tar.gz"),
        "dependencies_sha256": sha256_file(directory / "dependencies.txt"),
        "unit_budget_chars": settings.ARGUMENT_GYM_UNIT_BUDGET_CHARS,
        "unit_text_chars": settings.ARGUMENT_GYM_UNIT_TEXT_CHARS,
        "brief_text_chars": settings.ARGUMENT_GYM_BRIEF_TEXT_CHARS,
        "source_ids": SOURCE_IDS,
        "enabled_checks": args.check or list(checks.CORRECTNESS_CHECK_IDS),
        "blinding": "The Gym receives brief text and record text only. No fixture id, "
                    "condition label, mutation class or gold vulnerability reaches any prompt.",
        "scoring": "The Gym writes stable per-target dispositions. Whether a result matches "
                   "the registered mutation remains a separate, human-checkable step.",
        "fixtures": [{
            "fixture_id": f["fixture_id"],
            "control_sha256": f["provenance"]["control_sha256"],
            "mutant_sha256": f["provenance"]["mutant_sha256"],
            "attachment_sha256": f["provenance"]["attachment_sha256"],
        } for f in fixtures],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--model", default="gpt-5.4-mini",
                        help="model for every stage unless a role is overridden")
    parser.add_argument("--attack-model", help="model for the opponent stage")
    parser.add_argument("--judge-model", help="model for the judge stage")
    parser.add_argument("--base-model",
                        help="model for every other stage; held constant across a 2x2 "
                             "so the design varies two factors, not ten")
    parser.add_argument("--cell", help="label for this cell of a factorial design")
    parser.add_argument("--fixtures-dir",
                        help="fixture tree to run; defaults to the subtle tier")
    parser.add_argument("--reasoning", default="medium")
    parser.add_argument("--fixture", action="append", help="limit to these fixture ids")
    parser.add_argument(
        "--check", action="append", choices=checks.CORRECTNESS_CHECK_IDS,
        help="run only this correctness check; repeat for more than one",
    )
    args = parser.parse_args()

    directory = Path(args.output_dir).resolve()
    if EXPERIMENT / "results" not in directory.parents:
        parser.error("Output directory must be inside lexis_real_briefs/experiment/results")
    directory.mkdir(mode=0o700, parents=True, exist_ok=False)

    global FIXTURES
    if args.fixtures_dir:
        FIXTURES = Path(args.fixtures_dir).resolve()

    models = {
        "attack": args.attack_model or args.model,
        "judge": args.judge_model or args.model,
        "base": args.base_model or args.model,
    }
    enabled_checks = args.check or list(checks.CORRECTNESS_CHECK_IDS)

    fixtures = [json.loads((home / "fixture.json").read_text())
                for home in sorted(FIXTURES.iterdir()) if home.is_dir()]
    if args.fixture:
        fixtures = [f for f in fixtures if f["fixture_id"] in set(args.fixture)]
    if not fixtures:
        parser.error("No matching fixtures")

    if settings.DATABASES["default"]["ENGINE"] != "django.db.backends.sqlite3":
        parser.error("This runner requires SQLite so the run gets its own database copy")
    db_path = directory / "run.sqlite3"
    with sqlite3.connect(f"file:{settings.DATABASES['default']['NAME']}?mode=ro", uri=True) as source:
        with sqlite3.connect(db_path) as dest:
            source.backup(dest)
    connections.close_all()
    settings.DATABASES["default"]["NAME"] = db_path
    connections["default"].settings_dict["NAME"] = db_path
    sync_court_profile_seeds(update_existing=True)
    sync_legal_rule_seeds(update_existing=True)

    state = record_state(directory, fixtures, args, models)
    (directory / "manifest.json").write_text(json.dumps(state, indent=2, default=str))
    user, _ = get_user_model().objects.get_or_create(username="lexis-mutation-benchmark")

    def file_prompt(key, **kwargs):
        # Recording the key here is what lets the client wrapper know which
        # stage is about to call it, without patching the Gym itself.
        note_prompt(key)
        kwargs["allow_database_override"] = False
        return render_prompt(key, **kwargs)

    results = []
    total = len(fixtures) * len(CONDITIONS)
    index = 0
    with override_settings(AI_DRAFTING_ENABLED=args.live), \
            patch("apps.argument_gym.pipeline.ai_enabled", return_value=args.live), \
            patch("apps.argument_gym.pipeline.render_prompt", side_effect=file_prompt), \
            patch("apps.sources.connectors.rag.render_prompt", side_effect=file_prompt):
        for fixture in fixtures:
            # Both conditions of a pair run back to back, so anything that drifts
            # over the course of the session drifts equally across the pair.
            for condition in CONDITIONS:
                index += 1
                close_old_connections()
                item = directory / f"{fixture['fixture_id']}-{condition}"
                item.mkdir()
                print(f"[{index}/{total}] {fixture['fixture_id']} {condition}", flush=True)
                try:
                    result = run_one(fixture, condition, user, directory=item,
                                     live=args.live, models=models, reasoning=args.reasoning,
                                     enabled_checks=enabled_checks)
                except Exception as exc:  # noqa: BLE001 - record and continue
                    result = {"fixture_id": fixture["fixture_id"], "condition": condition,
                              "status": "failed", "error_type": type(exc).__name__,
                              "error": str(exc)[:400]}
                results.append(result)
                (item / "result.json").write_text(json.dumps(result, indent=2, default=str))
                (directory / "report.json").write_text(
                    json.dumps({"manifest": state, "results": results}, indent=2, default=str))
                if result.get("degraded"):
                    print(f"      DEGRADED: {', '.join(result['degraded']['roles'])} stage "
                          f"call failed -- {result['degraded']['failures'][result['degraded']['roles'][0]][0]['error_type']}",
                          flush=True)
                tests = result.get("correctness_tests", [])
                counts = {value: sum(test.get("disposition") == value for test in tests)
                          for value in ("must_fix", "review", "pass")}
                print(f"      {result['status']}, {len(tests)} tests: "
                      f"{counts['must_fix']} must fix / {counts['review']} review / "
                      f"{counts['pass']} pass, {len(result.get('model_calls', []))} calls", flush=True)

    print(f"\nSaved {len(results)} runs to {directory}", flush=True)
    failed = [r for r in results if r["status"] not in ("complete",) or r.get("degraded")]
    if failed:
        degraded = [r for r in failed if r.get("degraded")]
        broken = [r for r in failed if not r.get("degraded")]
        if degraded:
            print(f"{len(degraded)} run(s) DEGRADED -- a stage under test fell back to the "
                  f"deterministic path and must not be counted: "
                  f"{', '.join(r['fixture_id'] + '/' + r['condition'] for r in degraded)}")
        if broken:
            print(f"{len(broken)} run(s) did not complete: "
                  f"{', '.join(r['fixture_id'] + '/' + r['condition'] for r in broken)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

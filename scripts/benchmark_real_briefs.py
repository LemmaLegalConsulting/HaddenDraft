"""Private, checkpointed live/offline experiments over local brief revisions."""

import argparse
import json
import os
import sys
import hashlib
import sqlite3
import subprocess
import tarfile
from collections import Counter
from unittest.mock import patch
from urllib.parse import urlsplit
from pathlib import Path

import django


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.contrib.auth import get_user_model
from django.conf import settings
from django.db import close_old_connections, connections
from django.test import override_settings
from django.utils.timezone import now

from apps.argument_gym import ingestion
from apps.argument_gym.models import GymDocument, GymRun, GymWorkspace
from apps.argument_gym.pipeline import execute_run
from apps.ai.benchmark_capture import CaptureCalls
from apps.ai.prompt_catalog import render_prompt
from apps.sources.models import SourceConfiguration
from apps.sources.registry import connector_registry
from apps.rules.court_profiles import sync_court_profile_seeds
from apps.rules.legal_rules import sync_legal_rule_seeds
from apps.rules.models import CourtProfile, LegalRuleProfile


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class RecordingRegistry:
    def __init__(self, live):
        self.live, self.calls = live, []

    def search(self, query, **kwargs):
        results = connector_registry.search(query, **kwargs) if self.live else []
        self.calls.append({"query": query, "source_ids": kwargs.get("source_ids"),
                           "results": [result.to_dict() for result in results]})
        return results


def files_for(root):
    paths = sorted(Path(root).rglob("*.docx"))
    return [path for path in paths if "word_versions" in path.parts]


def bucket(path):
    name = path.name.casefold()
    if "current_accepted" in name or "source_copy" in name:
        return "current_or_source"
    if "before" in name or "initial" in name:
        return "earlier"
    if "after" in name or "follow_up" in name:
        return "later"
    return "snapshot"


def run_one(path, user, *, directory, live, model, reasoning):
    content = path.read_bytes()
    ingested = ingestion.ingest_upload(content, filename=path.name, content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", split_exhibits=False)
    workspace = GymWorkspace.objects.create(owner=user, title=f"Benchmark: {path.stem}", jurisdiction="Ohio")
    brief = GymDocument.objects.create(workspace=workspace, role=GymDocument.BRIEF_UNDER_TEST, source_type=GymDocument.UPLOAD, title=path.name, extracted_text=ingested["text"], extraction_metadata=ingested["metadata"])
    run = GymRun.objects.create(workspace=workspace, brief=brief, configuration={
        "benchmark": "cle_real_briefs", "mode": "live" if live else "offline",
        "source": str(path.relative_to(ROOT)),
        "sourceIds": ["ohio-cases", "ohio-statutes", "ohio-ordinances", "treatise"],
    })
    registry = RecordingRegistry(live)
    with CaptureCalls(directory, live=live, model=model, reasoning=reasoning) as capture:
        run = execute_run(run, connector_registry=registry)
    findings = run.check_results or {}
    finding_counts = {key: len(value.get("findings", [])) for key, value in findings.items()}
    challenges = list(run.challenges.order_by("ordinal", "id").values(
        "ordinal", "category", "severity", "confidence", "opponent_argument", "why_it_matters",
        "target", "legal_sources", "record_sources", "judge_assessment", "judge_verdict",
        "suggested_response", "coaching_recommendation", "disposition"))
    return {
        "path": str(path.relative_to(ROOT)),
        "sha256": sha(path),
        "run_id": run.id,
        "group": "/".join(path.relative_to(ROOT / "cle_real_briefs/revision_snapshots/word_versions").parts[:-1]),
        "snapshot": path.stem,
        "bucket": bucket(path),
        "status": run.status,
        "error": "Pipeline failed; inspect private benchmark database" if run.error else "",
        "characters": len(ingested["text"]),
        "pages": ingested["metadata"].get("pageCount"),
        "paragraphs": ingested["metadata"].get("paragraphCount"),
        "units": len(brief.structure_units or []),
        "court": run.court_detection,
        "checks": finding_counts,
        "check_results": run.check_results,
        "checks_run": run.checks_run,
        "rule_audit": run.rule_audit,
        "compliance": run.compliance,
        "finding_outcomes": dict(Counter(f.get("outcome") for v in findings.values() for f in v.get("findings", []))),
        "retrieval": registry.calls,
        "research_trace": run.research_trace,
        "model_calls": [{k: v for k, v in call.items() if k not in {"messages", "response"}} for call in capture.calls],
        "total_findings": sum(finding_counts.values()),
        "challenges": challenges,
        "challenge_count": len(challenges),
        "assessment_verdict": run.assessment_verdict,
        "assessment": run.assessment,
        "stage_trace": run.stage_trace,
    }


def record_state(directory, paths, args):
    """Capture code, public check rules, and effective profiles without secrets."""
    def git(*argv):
        return subprocess.check_output(["git", *argv], cwd=ROOT).decode()
    names = git("ls-files", "-co", "--exclude-standard").splitlines()
    selected = sorted({name for name in names if name.startswith(("backend/", "prompts/", "scripts/", "content/drafting-rules/", "content/court-rules/", "content/legal-rules/", "content/argument-gym/")) or name == "requirements.txt"})
    with tarfile.open(directory / "code-snapshot.tar.gz", "w:gz") as archive:
        for name in selected:
            if (ROOT / name).is_file():
                archive.add(ROOT / name, arcname=name)
    (directory / "working-tree.patch").write_text(git("diff", "HEAD", "--binary"))
    (directory / "dependencies.txt").write_bytes(subprocess.check_output([sys.executable, "-m", "pip", "freeze"]))
    config = SourceConfiguration.effective_settings("openai", {
        "api_key": settings.OPENAI_API_KEY, "base_url": settings.OPENAI_BASE_URL,
    })
    if args.live and not config.get("api_key"):
        raise ValueError("No configured model credential")
    profiles = {"court": list(CourtProfile.objects.values()), "legal": list(LegalRuleProfile.objects.values())}
    (directory / "effective-profiles.json").write_text(json.dumps(profiles, indent=2, default=str))
    return dict(created_at=now().isoformat(), git_commit=git("rev-parse", "HEAD").strip(),
                git_status=git("status", "--short"), command=[sys.executable, *sys.argv],
                python=sys.version, code_sha256=sha(directory / "code-snapshot.tar.gz"),
                dependencies_sha256=sha(directory / "dependencies.txt"),
                profiles_sha256=sha(directory / "effective-profiles.json"),
                model=args.model, reasoning=args.reasoning, temperature=0,
                provider_host=urlsplit(config.get("base_url") or "https://api.openai.com").hostname,
                model_version_note="Requested model alias; provider snapshot identity is not available from the application client.",
                input_files=[{"path": str(p.relative_to(ROOT)), "sha256": sha(p)} for p in paths],
                source_ids=["ohio-cases", "ohio-statutes", "ohio-ordinances", "treatise"],
                case_record="No separate case documents supplied; record audit unavailable.",
                prompt_policy="File-backed catalog only; exact rendered requests saved per call.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(ROOT / "cle_real_briefs/revision_snapshots/word_versions"))
    parser.add_argument("--output-dir", required=True, help="New private directory; existing directories are refused")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--model", default="gpt-5.5")
    parser.add_argument("--reasoning", default="medium")
    parser.add_argument("--family", help="Revision family path filter, such as L_Moore")
    parser.add_argument("--endpoints", action="store_true", help="Only first and last snapshot in each family with >=3 versions")
    args = parser.parse_args()
    directory = Path(args.output_dir).resolve()
    # Results, model requests, and the DB copy can contain private case material.
    private_root = ROOT / "cle_real_briefs"
    if private_root not in directory.parents:
        parser.error("Output directory must be inside the ignored cle_real_briefs directory")
    directory.mkdir(mode=0o700, parents=True, exist_ok=False)
    paths = files_for(args.root)
    if args.family:
        paths = [p for p in paths if args.family in str(p)]
    if args.endpoints:
        groups = {}
        for path in paths:
            groups.setdefault(path.parent, []).append(path)
        paths = [p for group in groups.values() if len(group) >= 3 for p in (group[0], group[-1])]
    if not paths:
        parser.error("No matching inputs")
    # Preserve the application's catalog in an isolated local database. All
    # benchmark rows and seed refreshes stay in this copy, not the app database.
    if settings.DATABASES["default"]["ENGINE"] != "django.db.backends.sqlite3":
        parser.error("This local runner requires SQLite for an isolated database copy")
    db_path = directory / "benchmark.sqlite3"
    with sqlite3.connect(f"file:{settings.DATABASES['default']['NAME']}?mode=ro", uri=True) as source:
        with sqlite3.connect(db_path) as dest:
            source.backup(dest)
    connections.close_all()
    settings.DATABASES["default"]["NAME"] = db_path
    connections["default"].settings_dict["NAME"] = db_path
    sync_court_profile_seeds(update_existing=True)
    sync_legal_rule_seeds(update_existing=True)
    state = record_state(directory, paths, args)
    (directory / "manifest.json").write_text(json.dumps(state, indent=2, default=str))
    user, _ = get_user_model().objects.get_or_create(username="cle-real-brief-benchmark")
    results = []
    def file_prompt(key, **kwargs):
        kwargs["allow_database_override"] = False
        return render_prompt(key, **kwargs)
    with override_settings(AI_DRAFTING_ENABLED=args.live), patch("apps.argument_gym.pipeline.ai_enabled", return_value=args.live), \
            patch("apps.argument_gym.pipeline.render_prompt", side_effect=file_prompt), \
            patch("apps.sources.connectors.rag.render_prompt", side_effect=file_prompt):
        for index, path in enumerate(paths, 1):
            close_old_connections()
            item_dir = directory / f"document-{index:02}"
            item_dir.mkdir()
            print(f"Starting {index}/{len(paths)}: {path.name}", flush=True)
            try:
                result = run_one(path, user, directory=item_dir, live=args.live, model=args.model, reasoning=args.reasoning)
            except Exception as exc:
                result = {"path": str(path.relative_to(ROOT)), "status": "failed", "error_type": type(exc).__name__}
            results.append(result)
            (item_dir / "result.json").write_text(json.dumps(result, indent=2, default=str))
            (directory / "report.json").write_text(json.dumps({"manifest": state, "results": results}, indent=2, default=str))
            print(f"Finished: {result['status']}, {len(result.get('model_calls', []))} model calls", flush=True)
    print(f"Saved {len(results)} document reports to {directory}", flush=True)
    if any(r["status"] != "complete" or any(c["status"] != "complete" for c in r.get("model_calls", [])) for r in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()

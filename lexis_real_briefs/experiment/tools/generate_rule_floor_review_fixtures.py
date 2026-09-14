"""Generate a quarantined Llama-authored rule-elements micro corpus.

The generated briefs are legal-content proposals, not verified fixtures.  They
remain under the ignored experiment workspace until an attorney completes each
``attorney-review.json``.  The mutant is always made mechanically by deleting
one marked paragraph from the control.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import django
import yaml


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from apps.ai.openai_client import OpenAICompatibleClient  # noqa: E402


AUTHOR_MODEL = "llama-4-maverick"
OUTPUT = ROOT / "lexis_real_briefs" / "experiment" / "rule-floor-review-20260913"
MARKER = "[[TARGET_ELEMENT_PARAGRAPH]]"

SPECS = [
    {
        "id": "R001",
        "slug": "rc-1923-04-waiver-rent",
        "target": "future_rent",
        "scenario": "Tenant moves to dismiss after the landlord accepted a payment after serving a three-day notice; the payment covered the next occupancy month, not old arrears.",
    },
    {
        "id": "R002",
        "slug": "rc-5321-11-notice-to-cure",
        "target": "specific_act",
        "scenario": "Tenant opposes an eviction based on an R.C. 5321.05 health-and-safety breach because the written notice stated only a generic lease violation and did not identify any act or omission.",
    },
    {
        "id": "R003",
        "slug": "rc-5321-11-notice-to-cure",
        "target": "condition_not_remedied",
        "scenario": "Landlord seeks possession for an alleged health-and-safety breach and contends the tenant did not remedy a specifically noticed obstruction during the statutory period.",
    },
    {
        "id": "R004",
        "slug": "rc-5321-15-self-help",
        "target": "resulting_damage",
        "scenario": "Tenant seeks statutory damages and attorney fees after a residential landlord changed the locks without process, causing identified hotel and replacement-lock costs.",
    },
    {
        "id": "R005",
        "slug": "rc-5321-02-retaliation",
        "target": "causal_connection",
        "scenario": "Tenant raises retaliation after a code complaint known to the landlord was followed by an eviction; timing and a landlord message supply the causal connection, and no statutory exception is asserted.",
    },
    {
        "id": "R006",
        "slug": "rc-5321-04-landlord-duties",
        "target": "condition_described",
        "scenario": "Tenant seeks rent-abatement damages for breach of the fit-and-habitable duty and identifies a concrete heat defect, its location, and duration; no entry claim is involved.",
    },
    {
        "id": "R007",
        "slug": "vawa-eviction-protection",
        "target": "direct_result",
        "scenario": "Housing Choice Voucher tenant invokes VAWA against termination for property damage directly caused during domestic violence; no documentation request or VAWA exception was asserted.",
    },
    {
        "id": "R008",
        "slug": "hud-project-based-24-cfr-247-notice",
        "target": "ten_day_discussion_advisement",
        "scenario": "Project-based Section 8 tenant challenges a nonpayment termination notice that states all otherwise applicable content and timing but omits the ten-day opportunity to discuss termination.",
    },
    {
        "id": "R009",
        "slug": "hud-public-housing-termination-grievance",
        "target": "notice_content",
        "scenario": "Public-housing tenant challenges a nonpayment termination notice that gives the applicable period and grievance advisement but omits the specific grounds, reply right, and document-inspection right; no exclusion is claimed and no grievance was requested.",
    },
    {
        "id": "R010",
        "slug": "common-law-timely-rent-tender",
        "target": "timely_full_tender",
        "scenario": "Tenant opposes a nonpayment eviction after the landlord refused a full rent payment tendered within the lease grace period. The exhibit should reproduce the pertinent lease payment clause, the dated payment instrument and delivery receipt, and the landlord's dated refusal message.",
    },
]

SYSTEM = """You author synthetic Ohio housing-litigation unit-test material.
Use only the supplied verified rule profile. Do not invent legal requirements,
authorities, or quotations. Return JSON only. This is not client work."""


def load_rule(slug: str) -> dict:
    path = ROOT / "content" / "legal-rules" / f"{slug}.yaml"
    rule = yaml.safe_load(path.read_text())
    if rule.get("verification") != "verified":
        raise ValueError(f"{slug} is not verified")
    return rule


def prompt_for(spec: dict, rule: dict) -> str:
    elements = "\n".join(
        f"- {element['id']}: {element['requirement']}"
        + (f" Applicability: {element['required_when']}" if element.get("required_when") else "")
        for element in rule["elements"]
    )
    target = next(e for e in rule["elements"] if e["id"] == spec["target"])
    return f"""Write one compact, wholly fictional Ohio trial-court memorandum and one fictional record exhibit.

The memorandum must expressly invoke {rule['citation']} and ask the court to rule on this doctrine. Use exactly this verified profile:

Name: {rule['name']}
Summary: {rule['summary']}
Elements:
{elements}

Scenario: {spec['scenario']}
Target for the exact-deletion mutant: {target['id']}: {target['requirement']}

Return exactly one JSON object with four string fields: title, brief_template,
target_paragraph, and record_text.

The response must begin with that one object and end with it. Do not append a
second version, commentary, or another JSON object. Put the caption only inside
brief_template; never add a separate caption field or any fifth field.

Rules:
1. brief_template contains the literal marker {MARKER} exactly once, alone between blank lines, in Argument.
2. target_paragraph is one short standalone application paragraph devoted only to the target. The target is applied nowhere else.
3. Separately apply every other element that is applicable on these facts. Explicitly state when a conditional element is inapplicable; do not manufacture facts that trigger it.
4. record_text directly supports every factual assertion used in the application, including the target facts, and is identical for both arms.
5. Put target-specific facts only in target_paragraph and record_text, not elsewhere in the memorandum.
6. Include a caption, Statement of Facts, Argument, and Conclusion. Use natural filing prose and never mention this test, an element, a requirement, an internal identifier, a marker, a control, a mutant, or an omission. Do not print identifiers such as `{target['id']}` in the filing.
7. Use no legal authority beyond the supplied citation/profile and do not quote or embellish a holding.
8. brief_template must be 1,300–3,200 characters and record_text 250–1,600 characters. A concise exhibit is acceptable if it directly supplies every relied-on fact.
9. The filing must remain coherent after target_paragraph is deleted, but must then lack only the target's application.
10. Keep party labels, requested relief, and reasoning internally consistent. A tenant asserting a successful defense asks for dismissal or denial of possession; an owner who establishes its claim asks for possession.
11. Do not state which court issued a cited opinion. Do not call an appellate opinion an Ohio Supreme Court holding.
"""


def parse(raw: str) -> dict:
    text = raw.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, re.I | re.S)
    if fenced:
        text = fenced.group(1)
    return json.loads(text, strict=False)


def validate_authored(spec: dict, rule: dict, authored: dict) -> tuple[str, str, str]:
    keys = {"title", "brief_template", "target_paragraph", "record_text"}
    if set(authored) != keys or not all(isinstance(authored[k], str) for k in keys):
        raise ValueError(f"expected exactly four string fields: {sorted(keys)}")
    template = authored["brief_template"].strip()
    target = authored["target_paragraph"].strip()
    record = authored["record_text"].strip()
    if template.count(MARKER) != 1:
        raise ValueError("marker must occur exactly once")
    if not re.search(rf"\n\s*{re.escape(MARKER)}\s*\n", template):
        raise ValueError("marker must stand on its own line")
    if not target or "\n\n" in target:
        raise ValueError("target must be one nonempty paragraph")
    if not 650 <= len(template) <= 3800:
        raise ValueError(f"brief length {len(template)} outside tolerance")
    if not 200 <= len(record) <= 1900:
        raise ValueError(f"record length {len(record)} outside tolerance")
    for heading in ("statement of facts", "argument", "conclusion"):
        if heading not in template.lower():
            raise ValueError(f"missing {heading}")
    control = template.replace(MARKER, target)
    # Machine-like IDs containing underscores are genuine prompt leakage.
    # Single ordinary words such as "refusal" may be unavoidable legal prose
    # and are not evidence that the model exposed an internal identifier.
    leaked_ids = [
        element["id"]
        for element in rule["elements"]
        if "_" in element["id"]
        if re.search(rf"\b{re.escape(element['id'])}\b", control, re.I)
    ]
    if leaked_ids:
        raise ValueError(f"filing leaks internal identifiers: {leaked_ids}")
    if re.search(
        r"\b(?:unit[ -]?test|test fixture|target element|omitted element|"
        r"internal identifier|control arm|mutant arm)\b",
        control,
        re.I,
    ):
        raise ValueError("filing uses unit-test vocabulary")
    if "ohio supreme court" in control.lower():
        raise ValueError("filing characterizes the cited court")
    invokes_citation = rule["citation"] in control or any(
        re.search(pattern, control, re.I)
        for pattern in rule.get("citation_patterns", [])
    )
    if not invokes_citation:
        raise ValueError("filing does not invoke the supplied citation")
    mutant = re.sub(rf"\n\s*{re.escape(MARKER)}\s*\n", "\n\n", template, count=1)
    return control.strip() + "\n", mutant.strip() + "\n", record + "\n"


def digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def write_one(spec: dict, rule: dict, authored: dict, raw: str, prompt: str, attempt: int) -> None:
    control, mutant, record = validate_authored(spec, rule, authored)
    home = OUTPUT / spec["id"]
    for arm in ("normalized", "mutant"):
        (home / arm / "attachments").mkdir(parents=True, exist_ok=True)
        (home / arm / "attachments" / "record-01.txt").write_text(record)
    (home / "normalized" / "brief.txt").write_text(control)
    (home / "mutant" / "brief.txt").write_text(mutant)
    target = authored["target_paragraph"].strip()
    fixture = {
        "fixture_id": spec["id"],
        "case_family_id": f"synthetic-rule-review-{spec['id'].lower()}",
        "stratum": "synthetic_rule_elements_attorney_review",
        "document": {
            "title": authored["title"].strip(),
            "court": "Fictional Ohio trial court",
            "jurisdiction": "Ohio",
            "pleading_type": "trial_brief",
            "side": "",
            "filed": "2026-09-13",
        },
        "files": {
            "source": None,
            "source_scan": None,
            "control": "normalized/brief.txt",
            "mutant": "mutant/brief.txt",
            "attachments": ["attachments/record-01.txt"],
            "attachment_notes": ["Identical fictional record supplied to both arms."],
        },
        "mutation": {
            "type": "rule_element_omission",
            "subtype": spec["target"],
            "operation": "delete",
            "section": "Argument",
            "description": f"Deleted the only proposed paragraph applying {spec['target']}.",
            "gold_vulnerability": f"PROPOSED: the mutant invokes {rule['citation']} but omits application of {spec['target']}.",
            "expected_direction": "mutant_worse",
            "materiality": "proposed_high_unverified",
            "target_location": {"section": "Argument", "control_excerpt": target, "mutant_excerpt": ""},
            "characters_changed": len(control) - len(mutant),
            "control_chars": len(control),
            "mutant_chars": len(mutant),
            "fraction_of_brief_changed": round((len(control) - len(mutant)) / len(control), 6),
            "expected_check_id": "rule_elements",
            "expected_target_id": f"{spec['slug']}:{spec['target']}",
            "expected_disposition": "must_fix",
        },
        "gold": {
            "control_has_target_defect": False,
            "mutant_has_target_defect": True,
            "expected_direction": "mutant_worse",
            "materiality": "proposed_high_unverified",
            "verified_by": [],
            "verification_status": "proposed_unverified",
            "verification_note": "Llama-authored proposal; do not run or score until attorney review is complete.",
        },
        "provenance": {
            "control_sha256": digest(control),
            "mutant_sha256": digest(mutant),
            "attachment_sha256": {"record-01.txt": digest(record)},
            "mutation_version": "exact-paragraph-deletion-1.0",
            "generator": {
                "provider": "Azure AI Services",
                "deployment": AUTHOR_MODEL,
                "family": "Meta Llama",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "attempts": attempt,
                "researcher_edits": "None; whitespace normalization and deletion only.",
            },
        },
    }
    (home / "fixture.json").write_text(json.dumps(fixture, indent=2) + "\n")
    (home / "authorship.json").write_text(json.dumps({
        "provider": "Azure AI Services",
        "model": AUTHOR_MODEL,
        "system": SYSTEM,
        "prompt": prompt,
        "raw_response": raw,
        "parsed_response": authored,
    }, indent=2) + "\n")
    review = {
        "fixtureId": spec["id"],
        "ruleSlug": spec["slug"],
        "targetElement": spec["target"],
        "reviewer": "",
        "reviewedAt": "",
        "controlCorrectlyAppliesEveryApplicableElement": None,
        "recordSupportsEveryAppliedElement": None,
        "deletionRemovesOnlyTargetApplication": None,
        "mutantClearlyOmitsTargetApplication": None,
        "ruleAndExpectedDispositionAreCorrect": None,
        "approved": False,
        "notes": "",
    }
    (home / "attorney-review.json").write_text(json.dumps(review, indent=2) + "\n")


def audit() -> int:
    failures = []
    for spec in SPECS:
        home = OUTPUT / spec["id"]
        try:
            fixture = json.loads((home / "fixture.json").read_text())
            authorship = json.loads((home / "authorship.json").read_text())
            rule = load_rule(spec["slug"])
            saved_control, saved_mutant, saved_record = validate_authored(
                spec, rule, authorship["parsed_response"]
            )
            review = json.loads((home / "attorney-review.json").read_text())
            control = (home / "normalized" / "brief.txt").read_text()
            mutant = (home / "mutant" / "brief.txt").read_text()
            record_a = (home / "normalized" / "attachments" / "record-01.txt").read_text()
            record_b = (home / "mutant" / "attachments" / "record-01.txt").read_text()
            if (control, mutant, record_a) != (saved_control, saved_mutant, saved_record):
                raise ValueError("saved files do not match validated authored response")
            excerpt = fixture["mutation"]["target_location"]["control_excerpt"]
            expected_mutant = re.sub(r"\n{3,}", "\n\n", control.replace(excerpt, "", 1)).strip()
            actual_mutant = re.sub(r"\n{3,}", "\n\n", mutant).strip()
            if expected_mutant != actual_mutant:
                raise ValueError("pair is not exact target-paragraph deletion")
            if record_a != record_b:
                raise ValueError("record differs between arms")
            checks = [
                "controlCorrectlyAppliesEveryApplicableElement",
                "recordSupportsEveryAppliedElement",
                "deletionRemovesOnlyTargetApplication",
                "mutantClearlyOmitsTargetApplication",
                "ruleAndExpectedDispositionAreCorrect",
                "approved",
            ]
            pending = [key for key in checks if review.get(key) is not True]
            state = "APPROVED" if not pending else "PENDING_ATTORNEY_REVIEW"
            print(f"{spec['id']}: {state}" + (f" ({', '.join(pending)})" if pending else ""))
        except (FileNotFoundError, KeyError, ValueError, json.JSONDecodeError) as exc:
            failures.append(f"{spec['id']}: {exc}")
    if failures:
        print("\nMechanical failures:\n" + "\n".join(failures), file=sys.stderr)
        return 1
    return 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit", action="store_true")
    parser.add_argument("--regenerate", action="append", default=[])
    parser.add_argument(
        "--promote-attempt",
        action="append",
        default=[],
        metavar="ID=PATH",
        help="Promote a preserved Llama response if it passes the current validator.",
    )
    args = parser.parse_args()
    if args.audit:
        raise SystemExit(audit())
    OUTPUT.mkdir(parents=True, exist_ok=True)
    if args.promote_attempt:
        specs_by_id = {spec["id"]: spec for spec in SPECS}
        for value in args.promote_attempt:
            fixture_id, separator, path_value = value.partition("=")
            if not separator or fixture_id not in specs_by_id:
                raise SystemExit(f"invalid --promote-attempt value: {value}")
            spec = specs_by_id[fixture_id]
            rule = load_rule(spec["slug"])
            saved_call = json.loads(Path(path_value).read_text())
            authored = parse(saved_call["raw_response"])
            validate_authored(spec, rule, authored)
            write_one(
                spec, rule, authored, saved_call["raw_response"],
                saved_call["prompt"], 1,
            )
            print(f"{fixture_id}: promoted preserved Llama response {path_value}")
        raise SystemExit(audit())
    client = OpenAICompatibleClient(model=AUTHOR_MODEL)
    failures = []
    for position, spec in enumerate(SPECS, 1):
        home = OUTPUT / spec["id"]
        if (home / "fixture.json").exists() and spec["id"] not in args.regenerate:
            print(f"[{position}/10] {spec['id']} already exists", flush=True)
            continue
        rule = load_rule(spec["slug"])
        prompt = prompt_for(spec, rule)
        if spec["id"] in args.regenerate and (home / "authorship.json").exists():
            archive = home / "generation-attempts"
            archive.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            shutil.copy2(home / "authorship.json", archive / f"pre-regenerate-{stamp}.json")
        last_error = ""
        for attempt in range(1, 7):
            repair = "" if not last_error else f"\nYour prior answer failed mechanical validation: {last_error}. Return a corrected complete JSON object."
            raw = client.complete(system=SYSTEM, user=prompt + repair, model=AUTHOR_MODEL, temperature=0.2)
            call_stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            attempt_dir = home / "generation-attempts"
            attempt_dir.mkdir(parents=True, exist_ok=True)
            attempt_path = attempt_dir / f"call-{call_stamp}.json"
            try:
                authored = parse(raw)
                validate_authored(spec, rule, authored)
                attempt_path.write_text(json.dumps({
                    "provider": "Azure AI Services",
                    "model": AUTHOR_MODEL,
                    "system": SYSTEM,
                    "prompt": prompt + repair,
                    "raw_response": raw,
                    "validation": "accepted",
                }, indent=2) + "\n")
                write_one(spec, rule, authored, raw, prompt, attempt)
                print(f"[{position}/10] {spec['id']} generated in {attempt} attempt(s)", flush=True)
                break
            except (ValueError, json.JSONDecodeError) as exc:
                last_error = str(exc)
                attempt_path.write_text(json.dumps({
                    "provider": "Azure AI Services",
                    "model": AUTHOR_MODEL,
                    "system": SYSTEM,
                    "prompt": prompt + repair,
                    "raw_response": raw,
                    "validation": "rejected",
                    "validation_error": last_error,
                }, indent=2) + "\n")
        else:
            failures.append(f"{spec['id']}: {last_error}")
    if failures:
        raise SystemExit("Generation failures:\n" + "\n".join(failures))
    print(f"Review workspace: {OUTPUT}")
    audit()


if __name__ == "__main__":
    main()

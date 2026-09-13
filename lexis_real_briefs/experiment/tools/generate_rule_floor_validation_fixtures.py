"""Generate a fresh, model-authored validation set for the rule-elements floor.

Each control/mutant pair differs only by deletion of one paragraph.  The author
model receives the verified rule contract but never executes or sees the
Argument Gym checker.  Generated material is synthetic and unadjudicated.
"""

import hashlib
import argparse
import json
import os
import re
import sys
from pathlib import Path

import django


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from apps.ai.openai_client import OpenAICompatibleClient  # noqa: E402


OUTPUT = ROOT / "lexis_real_briefs" / "experiment" / "fixtures-rule-floor-validation"
AUTHOR_MODEL = "llama-4-maverick"
MARKER = "[[TARGET_ELEMENT_PARAGRAPH]]"


SPECS = [
    {
        "id": "Q005",
        "slug": "common-law-late-rent-course-of-dealing",
        "rule": "Finkbeiner v. Lutz, 44 Ohio App.2d 223 (1st Dist. 1975)",
        "target": "no_advance_change_notice",
        "scenario": "Write for the tenant opposing an eviction for one allegedly late March rent tender. Prior late tenders were accepted, and the landlord gave no advance change notice.",
        "outside_forbidden": ["gave no effective advance", "no notice of changed", "without warning"],
        "elements": [
            "established_pattern: timing and frequency of prior late payments accepted by landlord",
            "no_advance_change_notice: landlord gave no effective advance notice requiring strict future compliance",
            "conforming_tender: disputed tender's date and amount complied with the established practice",
        ],
    },
    {
        "id": "Q006",
        "slug": "common-law-timely-rent-tender",
        "rule": "Pinewood Gardens Apts. v. Whiteside, 2014-Ohio-2305",
        "target": "refusal",
        "scenario": "Write for the tenant seeking dismissal of the owner's nonpayment eviction after a timely full tender that the owner returned uncashed.",
        "outside_forbidden": ["refus", "return", "not accept", "chose not to accept"],
        "elements": [
            "nonpayment_ground: eviction is for nonpayment of the tendered rent period",
            "timely_full_tender: tenant tendered the full amount by the due date or grace-period deadline",
            "refusal: landlord refused or did not accept that tender",
        ],
    },
    {
        "id": "Q007",
        "slug": "rc-1923-061-b-counterclaim-offset",
        "rule": "R.C. 1923.061(B)",
        "target": "no_rent_remains",
        "scenario": "Write for the tenant in a pending residential nonpayment eviction, seeking judgment after a stipulated Chapter 5321 counterclaim and court-ordered deposits leave no rent due.",
        "outside_forbidden": ["no rent remains", "nothing remains", "no remaining", "leave no", "resolved the alleged", "net balance", "exceeds the alleged"],
        "elements": [
            "covered_action: residential nonpayment action while tenant remains in possession",
            "qualifying_counterclaim: tenant asserts monetary recovery under the rental agreement or R.C. Chapter 4781 or 5321",
            "deposit_compliance: tenant complied with a court rent-deposit order (make the order applicable in this scenario)",
            "no_rent_remains: calculations show no rent remains due after counterclaim judgment and credited deposits",
        ],
    },
    {
        "id": "Q008",
        "slug": "hcv-notice-copy-to-pha",
        "rule": "24 C.F.R. § 982.310(e)(2)(ii)",
        "target": "simultaneous_pha_copy",
        "scenario": "Write for the voucher tenant seeking dismissal of the owner's eviction because the owner served the tenant first and sent the same notice to the PHA days later.",
        "outside_forbidden": ["failed to provide", "did not provide", "days after", "noncompliance", "breach of the regulatory"],
        "elements": [
            "voucher_tenancy: identify the Housing Choice Voucher tenancy and PHA",
            "owner_eviction_notice: identify the notice and date it was served on tenant",
            "simultaneous_pha_copy: identify evidence that the owner did not give the PHA the same notice at the same time",
        ],
    },
    {
        "id": "Q009",
        "slug": "hcv-hap-nonpayment",
        "rule": "24 C.F.R. § 982.310(b)",
        "target": "pha_shortfall_basis",
        "scenario": "Write for the voucher tenant opposing the private owner's nonpayment eviction. Tenant paid the tenant share; the only unpaid amount was the PHA's delayed HAP share.",
        "outside_forbidden": ["shortfall", "termination notice rested", "termination rests", "only unpaid", "basis for termination", "nonpayment is the basis", "based on the pha", "pha's delayed", "pha delayed"],
        "elements": [
            "hap_contract_term: identify the HCV lease and HAP-contract period",
            "tenant_share_status: state tenant share due and payment separately from the PHA share",
            "pha_shortfall_basis: identify the amount and show termination rests on PHA assistance nonpayment",
        ],
    },
    {
        "id": "Q010",
        "slug": "hud-project-based-24-cfr-247-notice",
        "rule": "24 C.F.R. § 247.4",
        "target": "judicial_defense_advisement",
        "scenario": "Write for the owner seeking possession and arguing that its project-based Section 8 nonpayment termination notice complied with every listed requirement.",
        "outside_forbidden": ["enforcement is judicial", "enforcement will be judicial", "may defend", "right to defend"],
        "elements": [
            "covered_program: identify a project-based Section 8 tenancy governed by the regulation",
            "termination_date: quote the notice's termination date",
            "specific_reasons: quote concrete factual grounds with dates and amounts",
            "ten_day_discussion_advisement: quote the notice's ten-day opportunity to discuss termination",
            "judicial_defense_advisement: quote the notice's statement that enforcement is judicial and tenant may defend",
            "nonpayment_accounting: identify arrearage, covered period, and computation date (use nonpayment facts)",
            "applicable_timing: apply the governing notice period using service and termination dates",
        ],
    },
    {
        "id": "Q011",
        "slug": "hud-project-based-ten-day-meeting",
        "rule": "HUD Handbook 4350.3 REV-1 ¶ 8-13.B",
        "target": "timely_request_honored",
        "scenario": "Write for a project-based assisted tenant opposing the owner's termination and eviction because the tenant requested the offered discussion within ten days and the owner filed without holding it.",
        "outside_forbidden": ["failed to honor", "did not honor", "without holding", "never held", "owner ignored", "required to honor", "failure to comply"],
        "elements": [
            "covered_program: identify project-based assistance and applicable HUD lease/handbook provision",
            "written_advisement: quote the notice's ten-day discussion advisement",
            "timely_request_honored: show tenant timely requested discussion and owner did not honor it (make request applicable)",
        ],
    },
    {
        "id": "Q012",
        "slug": "hud-public-housing-termination-grievance",
        "rule": "24 C.F.R. §§ 966.4(l)(3), 966.51-.57",
        "target": "process_completed",
        "scenario": "Write for a public-housing tenant opposing termination where a grievable dispute and timely hearing request are undisputed, but the PHA terminated before the available process ended.",
        "outside_forbidden": ["was not completed", "without completing", "before the hearing", "process ended", "process was complete"],
        "elements": [
            "public_housing: identify PHA-operated public housing",
            "timely_written_notice: state service date, termination date, and ground and apply the proper period",
            "notice_content: quote specific grounds, reply right, and document-inspection right",
            "grievance_advisement: quote accurate grievance-right language",
            "process_completed: show a timely requested, available grievance process was not completed before termination (make it applicable)",
            "valid_exclusion is conditional: expressly state the PHA claims no exclusion, so do not treat it as applicable",
        ],
    },
    {
        "id": "Q013",
        "slug": "fha-reasonable-accommodation-eviction",
        "rule": "42 U.S.C. § 3604(f)(3)(B)",
        "target": "necessity_nexus",
        "scenario": "Write for a tenant opposing eviction for disability-related housekeeping conduct after requesting a short extension plus cleaning assistance as an accommodation.",
        "outside_forbidden": ["directly addresses", "resulted in", "would have resolved", "connected to", "nexus"],
        "elements": [
            "disability: allege an impairment meeting the governing definition without unnecessary diagnosis detail",
            "provider_notice_request: show how provider knew of disability and accommodation need",
            "necessity_nexus: connect the disability, requested accommodation, and eviction-producing conduct/equal use",
            "reasonable_accommodation: state a concrete facially reasonable accommodation",
            "denial: identify provider denial or failure to act",
            "provider_defense is conditional: expressly state provider asserts no direct-threat, undue-burden, or fundamental-alteration defense",
        ],
    },
    {
        "id": "Q014",
        "slug": "rc-5321-16-security-deposit",
        "rule": "R.C. 5321.16",
        "target": "forwarding_address",
        "scenario": "Write for a former tenant seeking division C damages and attorney fees after the landlord failed to itemize or return a security deposit within thirty days. The tenant gave a written forwarding address.",
        "outside_forbidden": ["forwarding address", "new address", "address in writing", "provided her address", "provided his address", "provided their address"],
        "elements": [
            "deposit_paid: state the security-deposit amount and payment date",
            "tenancy_terminated: state when tenancy ended and possession was returned",
            "forwarding_address: say how and when tenant gave landlord a written forwarding address",
            "failure_to_itemize_or_return: state what landlord failed to do and when the thirty-day period expired",
            "amount_claimed: compute division C damages and identify attorney fees sought",
            "statutory_interest is conditional: expressly state tenant claims no statutory interest",
        ],
    },
]

# The author model is used for scenario and prose creation.  Before any Gym run,
# a researcher removes target-specific restatements the model left outside the
# marked paragraph and one inaccurate court-level characterization.  Exact
# substitutions keep that curation reproducible and visible in provenance.
NORMALIZATIONS = {
    "Q005": [
        ("\n\nAs the court applies the Finkbeiner doctrine, it is clear that Evergreen Properties' failure to provide effective advance notice precludes eviction for the allegedly late March rent tender. The court should rule in favor of Harrison.", ""),
    ],
    "Q006": [
        (" Burton Properties returned the uncashed check on July 3, 2022, stating 'rent not accepted.'", ""),
        ("The Ohio Supreme Court has held that", "Ohio law provides that"),
    ],
    "Q007": [
        (" The Court should enter judgment for Defendant as the deposits and counterclaim judgment resolve the alleged nonpayment.", ""),
    ],
    "Q008": [
        ("The regulation at 24 C.F.R. § 982.310(e)(2)(ii) requires that the owner give the PHA a copy of any notice to vacate at the same time it is served on the tenant. ", "The regulation at 24 C.F.R. § 982.310(e)(2)(ii) requires that the owner give the PHA a copy of any notice to vacate at the same time it is served on the tenant."),
        ("\n\nThe owner served Patel with the notice to vacate on February 10, 2023. The same notice was sent to CMHA on February 14, 2023. Under 24 C.F.R. § 982.310(e)(2)(ii), this delay is a separate and independent ground for dismissal.", ""),
    ],
    "Q009": [
        (" Arborcrest Properties served Owens a termination notice dated March 10, 2022, citing nonpayment of rent.", " Arborcrest Properties served Owens a termination notice dated March 10, 2022."),
        (" The PHA made the March 2022 HAP payment on April 15, 2022.", ""),
    ],
    "Q010": [
        (" Furthermore, the notice informed Defendant, 'If we proceed to enforce this termination in court, you have the right to present a defense.'", ""),
    ],
    "Q011": [
        (" Cedarbrook Housing did not respond or hold a discussion.", ""),
    ],
    "Q012": [
        (" CMHA scheduled the hearing for May 5, 2023. On April 11, 2023, CMHA terminated Harrison's tenancy.", ""),
        (" Harrison timely requested a hearing. CMHA did not complete the grievance process before terminating Harrison's tenancy.", " Harrison timely requested a hearing."),
    ],
}


SYSTEM = """You write synthetic Ohio housing-litigation qualification fixtures.
Follow the supplied verified rule contract exactly. Do not add legal tests,
citations, cases, statutes, defenses, or factual disputes. Return JSON only."""


def author_prompt(spec):
    requirements = [value.split(": ", 1)[1] for value in spec["elements"]]
    elements = "\n".join(f"- {value}" for value in requirements)
    target_requirement = next(
        value.split(": ", 1)[1]
        for value in spec["elements"]
        if value.startswith(spec["target"] + ":")
    )
    return f"""Write one compact, entirely fictional Ohio trial-court memorandum and one fictional record exhibit.

This is a matched-pair unit-test fixture, not client work. The memorandum must expressly invoke {spec['rule']} and ask the court to rule on that doctrine. Apply only this supplied contract:
{elements}

Target requirement for an exact-deletion mutation: {target_requirement}.
Required procedural posture and facts: {spec['scenario']}

Hard requirements:
1. Return one JSON object with exactly these string keys: title, brief_template, target_paragraph, record_text.
2. brief_template must contain the literal marker {MARKER} exactly once, on its own line between blank lines.
3. target_paragraph must be one short standalone argument paragraph that clearly applies ONLY the target element. It must not introduce a fact needed by another element.
4. Every nonconditional nontarget element must be expressly and separately applied in the argument. The target element must not be applied anywhere except target_paragraph. Mere facts in the statement-of-facts section do not count as application.
5. record_text must directly support every fact used for every element, including the target. The record will be identical in both arms.
6. Include concrete dates, amounts, notices, and actions sufficient to make the analysis unambiguous.
7. Keep brief_template between 1,400 and 2,800 characters and record_text between 500 and 1,500 characters.
8. Do not mention this experiment, the marker, a mutation, omitted text, a control, or a mutant in the filing or record.
9. Use no authority except {spec['rule']} and authorities literally embedded in the supplied element descriptions.
10. Invent names and facts distinct from common examples; do not use Maple Apartments, Jordan Lee, Oak Street Homes, Morgan Taylor, Lakeview Rentals, Alex Rivera, or Mei Chen.
11. Use a caption/title, Statement of Facts, Argument, and Conclusion. The party's requested ruling must match the required procedural posture.
12. Do not use the words "element," "requirement," "satisfy," or any internal identifier in the filing. Write natural legal argument. Do not repeat, paraphrase, summarize, or draw the conclusion of target_paragraph after the marker. Outside target_paragraph, avoid these target-only phrases: {', '.join(spec['outside_forbidden'])}.
13. Do not characterize which court issued a cited decision and do not add a quotation or holding beyond the supplied rule contract.
14. Concrete facts that uniquely establish the target requirement must appear in target_paragraph and record_text only. Do not put those target-specific facts in Statement of Facts or any other brief paragraph. Facts independently needed for a different requirement may remain.

The mutant will be derived mechanically by removing target_paragraph. Do not write two briefs."""


def parse_json(raw):
    text = raw.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.S | re.I)
    if fenced:
        text = fenced.group(1)
    # Some Azure catalog models place literal newlines inside JSON strings even
    # when instructed to return JSON.  ``strict=False`` accepts only those JSON
    # control characters; the schema and exact-deletion checks still run below.
    return json.loads(text, strict=False)


def normalize_authored(spec, authored):
    normalized = dict(authored)
    brief = normalized["brief_template"]
    applied = []
    for old, new in NORMALIZATIONS.get(spec["id"], []):
        if old not in brief:
            raise ValueError(f"normalization source text not found for {spec['id']}: {old[:80]}")
        brief = brief.replace(old, new, 1)
        applied.append({"removed": old, "replacement": new})
    normalized["brief_template"] = brief
    return normalized, applied


def validate(spec, authored):
    expected = {"title", "brief_template", "target_paragraph", "record_text"}
    if set(authored) != expected or not all(isinstance(authored[k], str) for k in expected):
        raise ValueError(f"expected exactly string keys {sorted(expected)}")
    brief = authored["brief_template"]
    target = authored["target_paragraph"].strip()
    record = authored["record_text"].strip()
    if brief.count(MARKER) != 1:
        raise ValueError("brief_template must contain marker exactly once")
    if not target or "\n\n" in target:
        raise ValueError("target_paragraph must be one nonempty paragraph")
    control = brief.replace(MARKER, target)
    authority_name = spec["rule"].split(",", 1)[0]
    invokes_rule = spec["rule"] in brief or authority_name in brief or (
        spec["id"] == "Q012" and "24 C.F.R." in brief and "966." in brief
    )
    if not invokes_rule:
        raise ValueError("brief does not literally invoke supplied rule")
    internal_ids = [
        value.split(":", 1)[0] for value in spec["elements"]
        if "_" in value.split(":", 1)[0]
    ]
    leaked_ids = [value for value in internal_ids if value.lower() in control.lower()]
    if leaked_ids:
        raise ValueError(f"filing exposes internal element ids: {leaked_ids}")
    if target.lower() in brief.replace(MARKER, "").lower():
        raise ValueError("target paragraph is duplicated in brief_template")
    for heading in ("statement of facts", "argument", "conclusion"):
        if heading not in brief.lower():
            raise ValueError(f"filing lacks {heading} heading")
    argument_match = re.search(
        r"(?is)(?:^|\n)\s*#+\s*argument\s*\n|(?:^|\n)\s*argument\s*\n",
        brief,
    )
    argument_text = brief[argument_match.end():] if argument_match else brief
    argument_without_target = argument_text.replace(MARKER, "").lower()
    leaked = [phrase for phrase in spec["outside_forbidden"] if phrase in argument_without_target]
    if leaked:
        raise ValueError(f"target application leaked elsewhere in Argument: {leaked}")
    if not 650 <= len(brief) <= 3400:
        raise ValueError(f"brief_template length {len(brief)} outside validation tolerance")
    if not 350 <= len(record) <= 1900:
        raise ValueError(f"record_text length {len(record)} outside validation tolerance")
    mutant = brief.replace(f"\n\n{MARKER}\n\n", "\n\n")
    if MARKER in mutant:
        mutant = brief.replace(MARKER, "")
    expected_mutant = control.replace(target, "", 1)
    if "\n\n\n\n" in expected_mutant:
        expected_mutant = expected_mutant.replace("\n\n\n\n", "\n\n", 1)
    if re.sub(r"\n{3,}", "\n\n", expected_mutant).strip() != re.sub(r"\n{3,}", "\n\n", mutant).strip():
        raise ValueError("pair is not an exact target-paragraph deletion")
    return control.strip() + "\n", re.sub(r"\n{3,}", "\n\n", mutant).strip() + "\n", record + "\n"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_fixture(spec, authored, raw, prompt, attempts, *, normalization=None, model_parsed=None):
    control, mutant, record = validate(spec, authored)
    home = OUTPUT / spec["id"]
    for side in ("normalized", "mutant"):
        (home / side / "attachments").mkdir(parents=True, exist_ok=True)
    control_path = home / "normalized" / "brief.txt"
    mutant_path = home / "mutant" / "brief.txt"
    control_record = home / "normalized" / "attachments" / "record-01.txt"
    mutant_record = home / "mutant" / "attachments" / "record-01.txt"
    control_path.write_text(control)
    mutant_path.write_text(mutant)
    control_record.write_text(record)
    mutant_record.write_text(record)
    target = authored["target_paragraph"].strip()
    fixture = {
        "fixture_id": spec["id"],
        "case_family_id": f"synthetic-rule-floor-validation-{spec['id'].lower()}",
        "stratum": "synthetic_rule_floor_fresh_validation",
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
            "description": f"Deleted the only argument paragraph applying {spec['target']}.",
            "gold_vulnerability": f"The mutant invokes {spec['rule']} but omits application of {spec['target']}; the identical record supports it.",
            "expected_direction": "mutant_worse",
            "materiality": "high",
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
            "materiality": "high",
            "verified_by": [],
            "verification_status": "synthetic_unadjudicated",
            "verification_note": "Fresh qualification fixture authored by Azure llama-4-maverick and mechanically paired; it was not used to tune the checker and has not been attorney-adjudicated.",
        },
        "provenance": {
            "source_sha256": None,
            "source_scan_sha256": None,
            "control_sha256": sha(control_path),
            "mutant_sha256": sha(mutant_path),
            "attachment_sha256": {"record-01.txt": sha(control_record)},
            "normalization_version": "synthetic-rule-floor-validation-1.0",
            "mutation_version": "exact-paragraph-deletion-1.0",
            "generator": {
                "model_provider": "Azure AI Services",
                "model_deployment": AUTHOR_MODEL,
                "model_family": "Meta Llama",
                "authored_on": "2026-09-13",
                "attempts": attempts,
                "researcher_edits": (
                    "Reproducible pre-run removal of target-specific duplicate prose; see authorship.json."
                    if normalization else
                    "None to filing prose; script performed whitespace normalization and exact deletion only."
                ),
            },
            "built_on": "2026-09-13",
        },
    }
    (home / "fixture.json").write_text(json.dumps(fixture, indent=2) + "\n")
    (home / "authorship.json").write_text(json.dumps({
        "model": AUTHOR_MODEL,
        "system": SYSTEM,
        "prompt": prompt,
        "raw_response": raw,
        "model_parsed_response": model_parsed or authored,
        "parsed_response": authored,
        "researcher_normalization": normalization or [],
    }, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--regenerate", action="append", default=[])
    parser.add_argument("--renormalize-existing", action="store_true")
    args = parser.parse_args()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    client = OpenAICompatibleClient(model=AUTHOR_MODEL)
    failures = []
    for index, spec in enumerate(SPECS, 1):
        if args.renormalize_existing:
            authorship_path = OUTPUT / spec["id"] / "authorship.json"
            prior = json.loads(authorship_path.read_text())
            model_parsed = parse_json(prior["raw_response"])
            authored, applied = normalize_authored(spec, model_parsed)
            validate(spec, authored)
            attempts = json.loads((OUTPUT / spec["id"] / "fixture.json").read_text())["provenance"]["generator"]["attempts"]
            write_fixture(
                spec, authored, prior["raw_response"], prior["prompt"], attempts,
                normalization=applied, model_parsed=model_parsed,
            )
            print(f"[{index}/{len(SPECS)}] {spec['id']} normalized", flush=True)
            continue
        if (OUTPUT / spec["id"] / "fixture.json").exists() and spec["id"] not in args.regenerate:
            print(f"[{index}/{len(SPECS)}] {spec['id']} already generated", flush=True)
            continue
        prompt = author_prompt(spec)
        last_error = ""
        for attempt in range(1, 7):
            repair = "" if not last_error else f"\n\nYour previous response failed mechanical validation: {last_error}. Return a corrected complete JSON object."
            raw = client.complete(system=SYSTEM, user=prompt + repair, model=AUTHOR_MODEL, temperature=0.2)
            try:
                authored = parse_json(raw)
                validate(spec, authored)
                write_fixture(spec, authored, raw, prompt, attempt)
                print(f"[{index}/{len(SPECS)}] {spec['id']} generated in {attempt} attempt(s)", flush=True)
                break
            except (ValueError, json.JSONDecodeError) as exc:
                last_error = str(exc)
        else:
            failures.append(f"{spec['id']}: {last_error}")
    if failures:
        raise SystemExit("Generation failures:\n" + "\n".join(failures))


if __name__ == "__main__":
    main()

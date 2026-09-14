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
from concurrent.futures import ThreadPoolExecutor, as_completed
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
        "extra_constraints": "Write for the tenant in support of dismissal. The Statement of Facts may allege service and a later accepted payment, but must not say which rental period the payment covered. Only target_paragraph and record_text may identify March, a future occupancy period, or that the payment was not for arrears. The Conclusion must request dismissal or denial of possession.",
    },
    {
        "id": "R002",
        "slug": "rc-5321-11-notice-to-cure",
        "target": "specific_act",
        "scenario": "Tenant opposes an eviction based on an R.C. 5321.05 health-and-safety breach because the written notice stated only a generic lease violation and did not identify any act or omission.",
        "extra_constraints": "Write for the tenant and request only dismissal or denial of possession. Outside target_paragraph, do not characterize the notice as generic, vague, nonspecific, defective, noncompliant, or as failing to identify an act or omission; do not describe its contents at all. Put its generic wording only in record_text. Do not make any ultimate statement outside target_paragraph that prerequisites were unmet or the notice failed R.C. 5321.11. The Conclusion must request relief without giving a reason. In its own non-target application paragraph, state: 'Trash blocking the common fire-exit route violated R.C. 5321.05 and materially affected fire safety.' In another non-target paragraph, state exactly that a March 5 inspection showed the trash remained after the February 1 receipt and thirty-day cure period; never say it was remedied. record_text must support the fire-exit breach, health/safety effect, continued condition, signed delivery/receipt on February 1, 2023, and termination date March 15, 2023.",
    },
    {
        "id": "R003",
        "slug": "rc-5321-11-notice-to-cure",
        "target": "condition_not_remedied",
        "scenario": "Landlord seeks possession for an alleged health-and-safety breach and contends the tenant did not remedy a specifically noticed obstruction during the statutory period.",
        "extra_constraints": "Write for the landlord and request possession. Outside target_paragraph, do not allege or imply that the defendant failed to remedy, that the obstruction remained or continued, or that it was still present after notice. The general rule may say that failure to remedy is required, but no application or ultimate statement that all prerequisites were met may appear outside target_paragraph. Put the post-deadline inspection or photograph only in record_text and apply it only in target_paragraph. record_text must expressly support delivery and signed receipt date, identify the R.C. 5321.05 obligation, explain why the obstruction materially affects health or safety, quote both the notice's specific act and a clearly labeled termination date at least thirty days after receipt, and establish the post-deadline condition. A cure deadline is not a termination date.",
    },
    {
        "id": "R004",
        "slug": "rc-5321-15-self-help",
        "target": "resulting_damage",
        "scenario": "Tenant seeks damages caused by a residential landlord's lockout and reasonable attorney fees under R.C. 5321.15(C); the lockout caused identified hotel and locksmith costs.",
        "extra_constraints": "Never call the remedy statutory damages, a statutory-damages award, a penalty, automatic damages, or mandated damages. Say R.C. 5321.15(C) allows the tenant to recover actual damages caused by the violation and reasonable attorney fees. Request only those. Outside target_paragraph, do not identify any cost, loss, harm, injury, amount, hotel stay, or locksmith expense; those facts belong only in target_paragraph and record_text. record_text must expressly support the parties' residential landlord-tenant relationship, the landlord's lockout to recover possession, that no eviction case or court order existed, and the caused expenses.",
    },
    {
        "id": "R005",
        "slug": "rc-5321-02-retaliation",
        "target": "causal_connection",
        "scenario": "Tenant raises retaliation after a code complaint known to the landlord was followed by an eviction; timing and a landlord message supply the causal connection, and no statutory exception is asserted.",
        "extra_constraints": "Use exact roles everywhere: landlord Jane Doe is plaintiff; tenant John Smith is defendant. Write for John Smith and request dismissal or denial of possession. Outside target_paragraph, call the eviction only a prohibited act, never a retaliatory act, and do not apply motive, causation, response, or temporal closeness; do not include the dates or quote the landlord message. The abstract rule may use the word retaliation. Do not use gendered pronouns. The Statement of Facts may identify the complaint, knowledge, and later eviction without dates or causal characterization. target_paragraph and record_text must both give these exact facts and exact quote: complaint January 10, 2023; Jane Doe acknowledged it January 15; Jane messaged January 18, 'You will regret involving the city'; Jane filed eviction February 20. The target must use the exact phrase 'because the tenant complained' and explain the dates and message. The Conclusion must request relief generically and must not say retaliation or a valid defense was established.",
    },
    {
        "id": "R006",
        "slug": "rc-5321-04-landlord-duties",
        "target": "condition_described",
        "scenario": "In a tenant's rent-escrow proceeding, the tenant seeks an order reducing rent under R.C. 5321.07(B)(2) because the landlord breached the R.C. 5321.04 fit-and-habitable duty; a concrete heat defect, its location, and duration are documented, and no entry claim is involved.",
        "extra_constraints": "You may cite R.C. 5321.07(A) and (B)(2) solely as the remedy-specific basis. Do not cite R.C. 5321.09, call relief damages, or suggest R.C. 5321.04 alone creates rent reduction. Use a landlord-controlled broken furnace, not a blocked vent or tenant-caused condition. Outside target_paragraph, do not identify heat, furnace, temperature, rooms, dates, duration, or any concrete defect; put those only in target_paragraph and record_text. Separately connect the asserted breach to R.C. 5321.07(B)(2)'s express rent-reduction remedy. Use coherent dates: defect January 1, 2023; written notice January 5 sent where rent is normally paid; unrepaired through February 15; tenant current and deposited all rent then due with clerk on February 16. Both the memorandum and affidavit record must expressly say the tenant was current when escrow began, all rent due was deposited, the notice went to the usual rent-payment place, and the dwelling is not student housing and not within the three-or-fewer-unit noticed exception.",
    },
    {
        "id": "R007",
        "slug": "vawa-eviction-protection",
        "target": "direct_result",
        "scenario": "Housing Choice Voucher tenant invokes VAWA against termination for property damage directly caused during domestic violence; no documentation request or VAWA exception was asserted.",
        "extra_constraints": "Use exact roles: Jennings Property Management is plaintiff/landlord; Jessica Wilson is defendant/voucher tenant and domestic-violence victim. record_text must include three labeled items: (1) police report expressly stating perpetrator directly caused the charged door damage during violence against Wilson; (2) voucher record naming Wilson and Jennings; (3) docket certification expressly stating complete record contains no documentation request and Jennings asserted no VAWA exception. Outside target_paragraph—including Statement of Facts and Conclusion—do not allege that the damage resulted from, was caused by, occurred during, or was connected to the violence; outside target_paragraph say only that eviction is for alleged property damage. Request dismissal or denial of possession.",
    },
    {
        "id": "R008",
        "slug": "hud-project-based-24-cfr-247-notice",
        "target": "ten_day_discussion_advisement",
        "scenario": "Project-based Section 8 tenant challenges a nonpayment termination notice that states all otherwise applicable content and timing but omits the ten-day opportunity to discuss termination.",
        "extra_constraints": "Write for the tenant as defendant and the project owner as plaintiff, and request dismissal or denial of possession. The identical record must reproduce the complete termination notice, which must actually OMIT every ten-day discussion advisement. Outside target_paragraph, do not say or imply that this advisement is missing, and do not quote it. Apply all other elements, including a 30-day nonpayment period supplied by an attached lease clause; do not assert a universal 30-day rule. record_text must reproduce that lease clause and proof of the actual service date. Choose service and termination dates at least 30 calendar days apart and calculate them correctly. The Conclusion must not identify the missing advisement.",
    },
    {
        "id": "R009",
        "slug": "hud-public-housing-termination-grievance",
        "target": "notice_content",
        "scenario": "Public-housing tenant challenges a nonpayment termination notice that gives the applicable period and grievance advisement but omits the specific grounds, reply right, and document-inspection right; no exclusion is claimed and no grievance was requested.",
        "extra_constraints": "TWO NONNEGOTIABLE SENTENCES: brief_template must include 'The notice advised Mr. Smith that he could request a grievance hearing by February 10, 2023.' record_text must include 'January rent was due January 1, 2023.' Use exact roles: Cuyahoga Metropolitan Housing Authority is plaintiff; John Smith is its public-housing tenant and defendant. Conclusion says only dismiss or deny CMHA possession. Outside target_paragraph, never describe missing notice content. target_paragraph must expressly list omissions of: specific grounds; reply right; inspection right; '30-day cure instructions'; rent and other allowed arrearages 'itemized by month'; a 'payment deadline' before filing; income recertification; hardship exemption; and switching from flat rent to income-based rent. A non-target Argument paragraph must cite 24 C.F.R. sections 966.4(l)(3) and 966.51-.57 and state: 'The 42-day period from February 1, 2023, to March 15, 2023, satisfied the 30-day minimum.' and 'Because January rent was due January 1, 2023, service on February 1, 2023, was not before the day after rent was due.' Say completion is inapplicable because no grievance was requested and no exclusion was asserted. record_text must name CMHA and public housing, give the February 10 grievance deadline, include 'CERTIFICATE OF SERVICE: Served on John Smith on February 1, 2023.' and 'DOCKET CERTIFICATION: No grievance was requested, and CMHA asserted no exclusion.' No placeholders or internal IDs.",
    },
    {
        "id": "R010",
        "slug": "common-law-timely-rent-tender",
        "target": "timely_full_tender",
        "scenario": "Tenant opposes a nonpayment eviction after the landlord refused a full rent payment tendered within the lease grace period. The exhibit should reproduce the pertinent lease payment clause, the dated payment instrument and delivery receipt, and the landlord's dated refusal message.",
        "extra_constraints": "Use exact roles and caption: John Smith, landlord, is plaintiff; Jane Doe, tenant, is defendant. Write for Jane Doe and request denial of possession. The Statement of Facts and Conclusion must not say timely, full, entire amount, amount due, within the grace period, or give the tender's amount, date, or method; they may say only that the tenant attempted payment, the landlord refused it, and the landlord seeks eviction for nonpayment. In Argument, state the abstract Pinewood Gardens rule in its accurate form: a landlord may not refuse timely full rent, including during an applicable grace period, and then evict for nonpayment of that rent. Use exact facts: the lease itself says full monthly rent is $800 due March 1, 2023, with five-day grace period through March 5; an $800 cashier's check was delivered March 3. Put those facts and the express application that this was the full amount and March 3 was within the grace period only in target_paragraph and record_text. target_paragraph must apply only amount/date/method/due-date/grace-period facts and must not also apply refusal, nonpayment-ground identity, or the ultimate result.",
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
Additional scenario constraint: {spec.get('extra_constraints', 'None.')}

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
7. Use no legal authority beyond the supplied citation/profile, except for any
   remedy-specific authority expressly allowed in the additional scenario
   constraint, and do not quote or embellish a holding.
8. brief_template must be 1,300–3,200 characters and record_text 100–1,600 characters. A concise exhibit is acceptable if it directly supplies every relied-on fact.
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
    if not 100 <= len(record) <= 1900:
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

    # The omission is semantic, not merely mechanical.  These gates reject the
    # recurring ways a target was duplicated in facts, a non-target argument,
    # or the conclusion.  `template` is the entire brief with the target absent.
    forbidden_outside_target = {
        "R002": r"\b(?:generic|vague|nonspecific|defective|noncompliant|did not specify|failed to specify|fails to specify|without (?:identifying|specifying)|lack(?:s|ed)? specificity)\b",
        "R003": r"\b(?:defendant|tenant|condition|obstruction).{0,35}(?:not remedied|unremedied|failed to remedy|still present|remained|continued)|\b(?:all|every) (?:statutory )?(?:prerequisite|requirement).{0,25}(?:met|satisfied|established)\b",
        "R004": r"\b(?:hotel|locksmith|replacement lock|cost|loss|harm|injur|\$\s*\d|statutory damages|penalt|automatic damages)\b",
        "R005": r"\b(?:retaliation was|motivated|caused|prompted|connected|in response|shortly after|weeks? after|months? after|troublemakers?|valid defense)\b",
        "R006": r"\b(?:heat|heating|furnace|temperature|living room|bedroom|three weeks|concrete defect)\b",
        "R007": r"\b(?:damage|ground).{0,90}(?:resulted|caused|occurred during|connected|during (?:the )?(?:incident|altercation))|\b(?:violence|assault|perpetrator|altercation).{0,90}(?:resulted|caused|damage)\b",
        "R008": r"\b(?:ten|10)[ -]?day.{0,60}(?:discuss|meeting)|\b(?:discussion|meeting).{0,35}(?:missing|omit|absent|fail)\b",
        "R009": r"\b(?:vague|generic|deficient|noncompliant|omit|missing|fail(?:s|ed)? to (?:state|include|specify|advise)|right to reply|inspect documents?|examine documents?|recertif|hardship exemption|amount owed|dates? of (?:the )?nonpayment)\b",
    }
    pattern = forbidden_outside_target.get(spec["id"])
    if pattern and re.search(pattern, template, re.I | re.S):
        raise ValueError(f"{spec['id']} duplicates or implies the target outside target_paragraph")

    required_target = {
        "R002": r"\b(?:generic|vague|did not specify|failed to specify|without identifying)\b",
        "R003": r"\b(?:not remedied|unremedied|failed to remedy|still present|remained)\b",
        "R004": r"\b(?:hotel|locksmith|replacement lock).{0,90}(?:\$|dollar|cost|expense)|(?:\$|dollar).{0,90}(?:hotel|locksmith|replacement lock)\b",
        "R005": r"\b(?:days?|weeks?|months?) after\b|\bin response to\b|\bbecause .{0,40}(?:complain(?:ed|ing)?|report(?:ed|ing)?)\b",
        "R006": r"\b(?:heat|heating|furnace)\b.{0,250}\b(?:day|week|month|from|since)\b",
        "R007": r"\b(?:direct result|directly resulted|directly caused)\b",
        "R008": r"(?:ten|10) days?.{0,100}(?:discuss|meeting)|(?:discuss|meeting).{0,100}(?:ten|10) days?",
        "R009": r"\b(?:right to reply|inspect documents?|examine documents?)\b",
        "R010": r"\b(?:grace period|within .{0,30}(?:grace|deadline))\b",
    }
    target_pattern = required_target.get(spec["id"])
    if target_pattern and not re.search(target_pattern, target, re.I | re.S):
        raise ValueError(f"{spec['id']} target does not expressly apply the target fact")

    if spec["id"] == "R005":
        if len(re.findall(r"\b(?:19|20)\d{2}\b", target)) < 2 or not re.search(r"['\"]", target):
            raise ValueError("R005 target must apply exact dates and the landlord's exact message")
    if spec["id"] == "R008":
        if not (re.search(r"\b(?:ten|10) days?\b", target, re.I) and re.search(r"\bdiscuss", target, re.I)):
            raise ValueError("R008 target must apply the missing ten-day discussion advisement")
    if spec["id"] == "R010":
        tender_details = [
            re.search(r"\$\s*\d|\b\d+ dollars?\b", target, re.I),
            re.search(r"\b(?:19|20)\d{2}\b", target),
            re.search(r"\b(?:check|money order|cash)\b", target, re.I),
            re.search(r"\bgrace period\b", target, re.I),
        ]
        if not all(tender_details):
            raise ValueError("R010 target must apply amount, date, method, and grace period")

    if spec["id"] == "R004" and re.search(r"\bstatutory damages\b", control, re.I):
        raise ValueError("R004 incorrectly requests fixed statutory damages")
    if spec["id"] == "R002" and re.search(r"(?<!not )\bremedied within\b", template, re.I):
        raise ValueError("R002 contradicts the stipulated non-remedy fact")
    if spec["id"] == "R006":
        if "R.C. 5321.07" not in control:
            raise ValueError("R006 omits the remedy-specific rent-escrow authority")
        if "R.C. 5321.09" in control:
            raise ValueError("R006 incorrectly invokes the landlord release-of-rent statute")
        if re.search(r"\bdamages\b", control, re.I):
            raise ValueError("R006 mischaracterizes rent-escrow relief as damages")
        for required_record_phrase in ("current", "all rent", "student", "three"):
            if required_record_phrase not in record.lower():
                raise ValueError(f"R006 record omits escrow prerequisite: {required_record_phrase}")
    if spec["id"] == "R008" and re.search(r"\b(?:ten|10)[ -]?day.{0,60}(?:discuss|meeting)", record, re.I | re.S):
        raise ValueError("R008 record proves the advisement exists instead of its omission")
    if spec["id"] == "R009":
        if not re.search(r"\b(?:30|thirty)[ -]?days?\b", target, re.I):
            raise ValueError("R009 target omits the current nonpayment cure/filing content")
        if not re.search(r"\brecertif", target, re.I) or not re.search(r"\bhardship exemption\b", target, re.I):
            raise ValueError("R009 target omits current recertification/hardship content")
        if not re.search(r"\bflat rent\b", target, re.I) or not re.search(r"\bitemiz", target, re.I):
            raise ValueError("R009 target omits current flat-rent or itemized-cure content")
        if not re.search(r"\b(?:payment )?deadline\b", target, re.I):
            raise ValueError("R009 target omits the pre-filing payment deadline")
        if "42" not in template or not re.search(r"rent (?:was )?due", template, re.I):
            raise ValueError("R009 omits the current service-timing application")
        if not re.search(r"rent (?:was )?due", record, re.I):
            raise ValueError("R009 record omits the rent due date needed for service timing")
        if "February 10, 2023" not in template or "February 10, 2023" not in record:
            raise ValueError("R009 omits the concrete grievance-request deadline")
        if "docket certification" not in record.lower():
            raise ValueError("R009 record omits support for grievance/exclusion posture")
        if "cuyahoga metropolitan housing authority" not in record.lower() or "public housing" not in record.lower():
            raise ValueError("R009 record omits PHA/public-housing support")
        if "February 1, 2023" not in record or "March 15, 2023" not in record:
            raise ValueError("R009 record omits service or termination date")
        if re.search(r"process was completed|process was complete", template, re.I):
            raise ValueError("R009 misstates an unrequested grievance as completed")
        if "no exclusion" not in template.lower():
            raise ValueError("R009 does not dispose of the conditional exclusion branch")
        if "certificate of service" not in record.lower():
            raise ValueError("R009 record omits proof of the service date")
        conclusion = re.split(r"\bConclusion\b", template, maxsplit=1, flags=re.I)[-1]
        if re.search(r"\bgrant.{0,30}(?:CMHA|housing authority|plaintiff).{0,30}possession\b", conclusion, re.I):
            raise ValueError("R009 conclusion requests relief for the wrong party")
    if spec["id"] == "R001":
        facts = re.split(r"\bArgument\b", template, maxsplit=1, flags=re.I)[0]
        if re.search(
            r"\b(?:march|future occupancy|upcoming month|not (?:old )?arrears)\b",
            facts,
            re.I,
        ):
            raise ValueError("R001 leaks the future-rent application into Statement of Facts")
        conclusion = re.split(r"\bConclusion\b", template, maxsplit=1, flags=re.I)[-1]
        if not re.search(r"\b(?:dismiss|deny possession)\b", conclusion, re.I):
            raise ValueError("R001 requested relief conflicts with the tenant's waiver defense")
        if not re.search(
            r"\b(?:march|future occupancy|period after|not (?:old )?arrears)\b",
            target,
            re.I,
        ):
            raise ValueError("R001 target does not uniquely apply future-rent attribution")
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
        "--candidate-pool", action="append", default=[], metavar="ID",
        help="Generate ten preserved Llama candidates without promoting one.",
    )
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
    if args.candidate_pool:
        specs_by_id = {spec["id"]: spec for spec in SPECS}
        client = OpenAICompatibleClient(model=AUTHOR_MODEL)
        for fixture_id in args.candidate_pool:
            if fixture_id not in specs_by_id:
                raise SystemExit(f"invalid --candidate-pool value: {fixture_id}")
            spec = specs_by_id[fixture_id]
            rule = load_rule(spec["slug"])
            prompt = prompt_for(spec, rule)
            attempt_dir = OUTPUT / fixture_id / "generation-attempts"
            attempt_dir.mkdir(parents=True, exist_ok=True)

            def generate_candidate(number: int) -> tuple[int, str]:
                try:
                    raw = client.complete(
                        system=SYSTEM, user=prompt, model=AUTHOR_MODEL, temperature=0.35
                    )
                except Exception as exc:  # preserve provider failures; do not abort other calls
                    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
                    path = attempt_dir / f"pool-{stamp}-{number:02d}.json"
                    path.write_text(json.dumps({
                        "provider": "Azure AI Services",
                        "model": AUTHOR_MODEL,
                        "system": SYSTEM,
                        "prompt": prompt,
                        "raw_response": "",
                        "validation": "provider_error",
                        "validation_error": str(exc),
                        "candidate_pool_size": 10,
                        "candidate_number": number,
                    }, indent=2) + "\n")
                    return number, f"provider_error: {path} ({exc})"
                try:
                    authored = parse(raw)
                    validate_authored(spec, rule, authored)
                    validation = "accepted"
                    error = None
                except (ValueError, json.JSONDecodeError) as exc:
                    validation = "rejected"
                    error = str(exc)
                stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
                path = attempt_dir / f"pool-{stamp}-{number:02d}.json"
                payload = {
                    "provider": "Azure AI Services",
                    "model": AUTHOR_MODEL,
                    "system": SYSTEM,
                    "prompt": prompt,
                    "raw_response": raw,
                    "validation": validation,
                    "validation_error": error,
                    "candidate_pool_size": 10,
                    "candidate_number": number,
                }
                path.write_text(json.dumps(payload, indent=2) + "\n")
                return number, f"{validation}: {path}" + (f" ({error})" if error else "")

            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = [executor.submit(generate_candidate, number) for number in range(1, 11)]
                for future in as_completed(futures):
                    number, result = future.result()
                    print(f"{fixture_id} candidate {number}: {result}", flush=True)
        raise SystemExit(0)
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

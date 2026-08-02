"""Seed selection criteria telling the picker which section fits which tenant.

The catalog says what a section is about. It does not say when to send it, and
that is the judgment an advocate makes in the twenty minutes before a hearing.
These hints make that judgment explicit and reviewable: what fact triggers the
section, what must be true for it to apply, and what it must not be paired with.

They are a starting point, not an authority. `seed_selection_hints` writes them
to `selection-hints.yaml` beside the catalog on first ingest and never
overwrites that file again, so an advocate's edits survive re-ingestion. Scoring
runs through the same pathway that ranks litigation templates.

`triggers` are matched against case facts and the advocate's stated goal.
`requires` are conditions that must hold. `excludes` name sections that
contradict this one -- advising a client both that the notice was defective and
that they should negotiate a move-out reads as indecision.
"""

from __future__ import annotations

from pathlib import Path

import yaml


SELECTION_HINTS = {
    # ---------------------------------------------------------------- defenses
    "decarlo": {
        "triggers": [
            "3-day notice names a different landlord than the complaint",
            "notice and complaint name different entities",
            "wrong landlord name on notice",
        ],
        "requires": ["has_3_day_notice", "has_complaint"],
        "excludes": ["notice-waived-for-accepting-future-rent"],
        "summary": "The 3-Day Notice and the complaint name different parties.",
    },
    "3-day-conspicuousness-of-statutory-language": {
        "triggers": [
            "statutory language on the 3-day notice is not conspicuous",
            "required notice wording is not bold or set apart",
        ],
        "requires": ["has_3_day_notice"],
        "excludes": [],
        "summary": "The notice has the required words but does not make them stand out.",
    },
    "notice-waived-for-accepting-future-rent": {
        "triggers": [
            "landlord accepted rent after serving the 3-day notice",
            "rent paid and kept after notice",
        ],
        "requires": ["has_3_day_notice", "rent_paid_after_notice"],
        "excludes": ["decarlo"],
        "summary": "Accepting rent for a later period cancels the notice.",
    },
    "vawa": {
        "triggers": [
            "subsidized tenant did not receive VAWA notices",
            "voucher or project-based tenant evicted without VAWA notice",
        ],
        "requires": ["is_subsidized"],
        "excludes": [],
        "summary": "Subsidized housing requires extra notices the landlord skipped.",
    },
    "532117": {
        "triggers": [
            "month-to-month tenancy ended by 30-day notice",
            "30-day notice served on a month-to-month tenant",
        ],
        "requires": ["is_month_to_month"],
        "excludes": [],
        "summary": "Rights and duties when a month-to-month tenancy is ended.",
    },
    "client-not-named-as-defendant-rtc": {
        "triggers": [
            "client is not a named defendant",
            "case filed against John Doe or Jane Doe",
        ],
        "requires": ["client_not_named"],
        "excludes": [],
        "summary": "The caller lives in the home but is not on the case.",
    },
    # ---------------------------------------------------------------- outcomes
    "negotiate-move-out-neo": {
        "triggers": [
            "no defense to the eviction",
            "client is willing to move",
            "client wants more time to move",
        ],
        "requires": [],
        "excludes": ["decarlo", "3-day-conspicuousness-of-statutory-language"],
        "summary": "Settle without a judgment when there is no defense to raise.",
    },
    "motion-to-seal-cle": {
        "triggers": [
            "eviction already on the client's record",
            "client wants the case hidden from the court website",
            "case dismissed or resolved",
        ],
        "requires": ["region_cleveland"],
        "excludes": [],
        "summary": "Ask the court to hide a closed case from its website.",
    },
    "file-motion-for-relief-from-judgment": {
        "triggers": [
            "judgment already entered against the client",
            "client moved before the set-out but the eviction stands",
            "client never received the court papers",
        ],
        "requires": ["judgment_entered"],
        "excludes": [],
        "summary": "Ask the court to undo a ruling already entered.",
    },
    "objections": {
        "triggers": [
            "magistrate decided the case",
            "client disagrees with the magistrate's decision",
        ],
        "requires": ["magistrate_decision"],
        "excludes": [],
        "summary": "Challenge a magistrate's decision within 14 days.",
    },
    # ---------------------------------------------------------------- how-to
    "getting-zoom-info-cle": {
        "triggers": [
            "client needs to attend a Cleveland housing court hearing",
            "hearing is upcoming and client is pro se",
        ],
        "requires": ["region_cleveland", "hearing_scheduled"],
        "excludes": [],
        "summary": "How to get the Zoom link, or attend in person.",
        "usually_paired": True,
    },
    "exhibits-and-evidence": {
        "triggers": [
            "client will represent themselves at a hearing",
            "client has documents or photos to show the court",
        ],
        "requires": ["hearing_scheduled"],
        "excludes": [],
        "summary": "How to file evidence and bring witnesses.",
        "usually_paired": True,
    },
    "requesting-a-continuance-non-rtc": {
        "triggers": [
            "client needs more time before the hearing",
            "client contacted Legal Aid too close to the hearing",
        ],
        "requires": ["hearing_scheduled"],
        "excludes": [],
        "summary": "Ask the judge for one more week.",
    },
    "answer-and-cc": {
        "triggers": [
            "client wants to file an answer",
            "client may have money claims against the landlord",
        ],
        "requires": [],
        "excludes": ["answer-with-ccs-neo"],
        "summary": "How to file an answer and counterclaims.",
    },
    "answer-with-ccs-neo": {
        "triggers": [
            "client wants to file an answer outside Cleveland",
            "client may have money claims against the landlord",
        ],
        "requires": ["region_neo"],
        "excludes": ["answer-and-cc"],
        "summary": "How to file an answer and counterclaims outside Cleveland.",
    },
    "rent-depositing-neo-draft": {
        "triggers": [
            "client wants to pay rent to the court over conditions",
            "landlord will not make repairs",
        ],
        "requires": ["has_conditions_issues"],
        "excludes": [],
        "summary": "Depositing rent with the court over bad conditions.",
    },
    "conditions-issues": {
        "triggers": [
            "client reports repairs the landlord will not make",
            "bad conditions in the home",
        ],
        "requires": ["has_conditions_issues"],
        "excludes": [],
        "summary": "What a tenant can do about conditions the landlord ignores.",
    },
    "security-deposit": {
        "triggers": [
            "client moved out and the deposit was not returned",
            "landlord kept the security deposit",
        ],
        "requires": [],
        "excludes": [],
        "summary": "Getting a security deposit back.",
    },
    # ---------------------------------------------------------------- subsidy
    "2506-admin-appeal": {
        "triggers": [
            "housing authority terminated the client's voucher",
            "client received a hearing decision ending the voucher",
        ],
        "requires": ["voucher_terminated"],
        "excludes": [],
        "summary": "Appeal a voucher termination to the Common Pleas court.",
    },
    "holdover-tenant": {
        "triggers": [
            "client has a voucher and needs to move",
            "lease not renewed and client holds a voucher",
        ],
        "requires": ["has_voucher"],
        "excludes": [],
        "summary": "Moving to a new home with a Housing Choice Voucher.",
    },
    "admissions-denial-past-time": {
        "triggers": [
            "client denied subsidized housing over criminal record",
            "deadline to ask for a review has passed",
        ],
        "requires": ["admission_denied"],
        "excludes": [],
        "summary": "Options after the deadline to appeal a denial has passed.",
    },
    "key-return-in-fed-actions-draft": {
        "triggers": [
            "client has moved out but has not returned the keys",
            "client wants the case dismissed because they left",
        ],
        "requires": [],
        "excludes": [],
        "summary": "Returning keys so the landlord cannot evict.",
    },
    "advice-letter-np": {
        "triggers": [
            "nonpayment eviction with no defense",
            "client completed intake too late for representation",
        ],
        "requires": [],
        "excludes": [],
        "summary": "General nonpayment advice when Legal Aid cannot represent.",
    },
}

HINTS_FILENAME = "selection-hints.yaml"

HEADER = """# Selection hints for the client advice-letter picker.
#
# Written once at first ingest and never overwritten, so edits here survive
# re-ingestion. Each entry says when to send a section:
#
#   triggers  free-text facts matched against the case and the advocate's goal
#   requires  conditions that must hold before the section is offered
#   excludes  sections that contradict this one
#   summary   one line shown next to the section in the picker
#
# Delete an entry to fall back to topic and region matching alone.
"""


def load_selection_hints(root: Path) -> dict:
    path = Path(root) / HINTS_FILENAME
    if not path.is_file():
        return {}
    return yaml.safe_load(path.read_text()) or {}


def seed_selection_hints(root: Path, *, force=False) -> Path:
    """Write the starting hints once; never clobber an advocate's edits."""
    path = Path(root) / HINTS_FILENAME
    if path.is_file() and not force:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(HEADER + yaml.safe_dump(SELECTION_HINTS, sort_keys=True, allow_unicode=True))
    return path

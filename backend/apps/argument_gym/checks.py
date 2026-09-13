"""The catalog of checks a session can run, and the author's choice among them.

Every check the gym can make is declared here with what it needs to run. The
author picks; nothing is added to a run because it seemed useful. A check that
was turned off and a check that could not apply are different things and are
reported differently, because "no findings" from a check that never ran is the
one result that must never look like a clean bill.

Checks belong to a **category**, and the category is not decoration: it is the
order an advocate can act in. Getting the law wrong is not the same kind of
problem as burying the strongest argument on page nine, and a revision pass that
mixes the two produces neither. So the catalog separates:

* **Correctness** -- is the law right, is the authority controlling, are the
  required elements present.
* **Argumentative completeness** -- does the brief connect its rules to its
  facts, work the hard element instead of restating the rule, confront adverse
  authority, and answer the objection a court will think of on its own.
* **Persuasive communication** -- whether a reader who is neither hostile nor
  patient can follow the argument and be moved by it.

The first two are about whether the brief is right. The third is about whether
it lands, and it is deliberately kept apart so an author can decide which of the
three they are ready to work on rather than reading one undifferentiated list.

`requires` names a precondition the session either has or does not:

* ``native_draft`` -- the brief is a HaddenDraft document, so the drafting
  validation rules have a template and a session to read.
* ``court_profile`` -- a court's filing rules are selected or detected.
* ``case_record`` -- there are case materials to check the brief against.
* ``checklist`` -- the author attached one of their own checklists.
"""

from dataclasses import dataclass, field


DETERMINISTIC = "deterministic"
MODEL = "model"


@dataclass(frozen=True)
class CheckCategory:
    """A group of checks an advocate can decide to work on as one pass."""

    id: str
    label: str
    description: str

    def to_dict(self):
        return {"id": self.id, "label": self.label, "description": self.description}


CATEGORY_CATALOG = (
    CheckCategory(
        id="correctness",
        label="Correctness",
        description=(
            "Is the law right? Is the authority controlling? Are the required elements present, "
            "and does the record establish what the brief says it does?"
        ),
    ),
    CheckCategory(
        id="completeness",
        label="Argumentative completeness",
        description=(
            "Does the brief connect its rules to its facts? Does it work the difficult element "
            "instead of restating the rule? Does it confront adverse authority and answer the "
            "counterargument a court will think of on its own?"
        ),
    ),
    CheckCategory(
        id="persuasion",
        label="Persuasive communication",
        description=(
            "Not whether the brief is right, but whether it lands: how the question is framed, "
            "how the argument is ordered and emphasized, and whether a busy judge can follow it "
            "and believe it."
        ),
    ),
    CheckCategory(
        id="custom",
        label="Your own checks",
        description="Review questions you wrote, in your words, applied to this brief.",
    ),
    CheckCategory(
        id="form",
        label="Form of the filing",
        description="Whether the paper meets this court's rules and the conventions of practice.",
    ),
    CheckCategory(
        id="language",
        label="Language",
        description="Sentence-level mechanics, reported as nudges rather than as defects in the argument.",
    ),
)
CATEGORIES_BY_ID = {category.id: category for category in CATEGORY_CATALOG}


# The persuasive communication suite. Each dimension is a check of its own, so an
# author can run the two or three they are ready to act on; they are answered in
# one model call rather than twelve, because the answers depend on each other --
# what belongs in the roadmap depends on what the emphasis should be.
PERSUASION_PREFIX = "persuasion_"
PERSUASION_DIMENSIONS = (
    (
        "issue_framing",
        "Issue framing",
        "Does the brief identify the real dispute early and frame it around the favorable legal question?",
    ),
    (
        "macro_organization",
        "Macro-organization",
        "Are arguments ordered logically and by importance? Can the reader see the roadmap?",
    ),
    (
        "paragraph_organization",
        "Paragraph-level organization",
        "Do paragraphs have discernible propositions or topic sentences, and develop one point at a time?",
    ),
    (
        "rule_synthesis",
        "Rule synthesis",
        "Does the writer synthesize authorities into a rule rather than serially summarize cases?",
    ),
    (
        "rule_application",
        "Rule-to-fact application",
        'Is the reasoning explicit -- "because X fact satisfies Y element" -- rather than leaving the '
        "inferential step to the court?",
    ),
    (
        "fact_selection",
        "Fact selection and narrative coherence",
        "Are legally significant facts foregrounded and organized in a comprehensible chronology or theory?",
    ),
    (
        "use_of_authority",
        "Use of authority",
        "Are important propositions backed by strong authorities placed where they actually matter, "
        "rather than citation dumping?",
    ),
    (
        "counterarguments",
        "Handling counterarguments",
        "Does the brief acknowledge and answer the strongest objection rather than arguing past it?",
    ),
    (
        "concision",
        "Concision and reader burden",
        "Does it say the same thing once, in the right place, without unnecessary throat-clearing?",
    ),
    (
        "calibration",
        "Calibrated confidence and credibility",
        "Does it distinguish strong propositions from uncertain ones and avoid overclaiming?",
    ),
    (
        "relief_alignment",
        "Requested-relief alignment",
        "Does the argument actually lead to the precise thing the brief asks the court to do?",
    ),
    (
        "emphasis",
        "Emphasis",
        "Does the document devote its space to the issues that matter rather than treating every point "
        "as equally important?",
    ),
)


@dataclass(frozen=True)
class CheckDefinition:
    id: str
    label: str
    description: str
    kind: str
    category: str
    default_enabled: bool = True
    requires: tuple = ()
    settings_help: str = ""

    def to_dict(self):
        return {
            "id": self.id,
            "label": self.label,
            "description": self.description,
            "kind": self.kind,
            "category": self.category,
            "categoryLabel": CATEGORIES_BY_ID[self.category].label,
            "categoryDescription": CATEGORIES_BY_ID[self.category].description,
            "defaultEnabled": self.default_enabled,
            "requires": list(self.requires),
            "settingsHelp": self.settings_help,
        }


_DECLARED_CHECKS = (
    CheckDefinition(
        id="adversarial",
        label="Opposing counsel, a judge, and a coach",
        description=(
            "The core of the gym: opposing counsel makes the strongest arguments available "
            "against the brief, a judge weighs them, and a coach proposes answers."
        ),
        kind=MODEL,
        category="completeness",
        default_enabled=False,
    ),
    CheckDefinition(
        id="record_support",
        label="Test material facts against the record",
        description=(
            "Opponent tests only atomic, record-verifiable, material claims; Judge sustains a defect "
            "only when the supplied evidence and record coverage establish it."
        ),
        kind=MODEL,
        category="correctness",
        requires=("case_record",),
    ),
    CheckDefinition(
        id="rule_elements",
        label="Audit the elements of the rules invoked",
        description=(
            "Detects the rules the brief cites or invokes by name, then audits each element "
            "of those rules: is it pleaded, and is it supported."
        ),
        kind=MODEL,
        category="correctness",
    ),
    CheckDefinition(
        id="authority_support",
        label="Test cited authority support",
        description=(
            "Whether each cited authority supports the material legal proposition for which the brief uses it."
        ),
        kind=MODEL,
        category="correctness",
    ),
    CheckDefinition(
        id="custom_checklist",
        label="Custom checklist",
        description=(
            "Applies review questions you wrote. An item can look things up -- authority, the "
            "case record, passages of the brief -- rather than answering from the brief alone. "
            "Attach a checklist for this to run."
        ),
        kind=MODEL,
        category="custom",
        default_enabled=False,
        requires=("checklist",),
    ),
    CheckDefinition(
        id="court_formatting",
        label="This court's filing rules",
        description="Required elements, type size, spacing, margins, and page limits for the selected court.",
        kind=DETERMINISTIC,
        category="form",
        default_enabled=False,
        requires=("court_profile",),
    ),
    CheckDefinition(
        id="pleading_form",
        label="Form of the pleading",
        description=(
            "Conventions of practice rather than any one court's rules: numbered paragraphs "
            "running in order, a prayer for relief, a signature block, exhibit references that "
            "resolve, no placeholder left in the text."
        ),
        kind=DETERMINISTIC,
        category="form",
        default_enabled=False,
    ),
    CheckDefinition(
        id="draft_validation",
        label="Draft-mode validation",
        description=(
            "The same checks Draft mode runs: unresolved template data and placeholders, draft "
            "structure, rendered Word consistency, citation linting, source support, and "
            "filing-package consistency."
        ),
        kind=DETERMINISTIC,
        category="form",
        default_enabled=False,
        requires=("native_draft",),
    ),
    CheckDefinition(
        id="grammar",
        label="Grammar and mechanics",
        description="Doubled words, missing sentence spacing, unbalanced quotes and parentheses.",
        kind=DETERMINISTIC,
        category="language",
        default_enabled=False,
    ),
    CheckDefinition(
        id="confused_words",
        label="Misspelled and easily confused words",
        description=(
            "Not a dictionary spell check, on purpose: a general dictionary flags half of every "
            "case name. This looks for the words legal writing actually gets wrong, and for real "
            "words used in place of other real words."
        ),
        kind=DETERMINISTIC,
        category="language",
        default_enabled=False,
    ),
    CheckDefinition(
        id="passive_voice",
        label="Passive voice",
        description=(
            "Reported as a nudge, never an error. Phrases a court expects to read are on an "
            "accepted list you can add to for this session."
        ),
        kind=DETERMINISTIC,
        category="language",
        default_enabled=False,
        settings_help="acceptedPassivePhrases: phrases this court expects, which the check stays quiet about.",
    ),
    CheckDefinition(
        id="readability",
        label="Readability",
        description="Sentence length and reading-level measures, reported as several formulas rather than one score.",
        kind=DETERMINISTIC,
        category="language",
        default_enabled=False,
    ),
)


def _persuasion_checks():
    """One check per dimension of the persuasive communication suite.

    They are declared from `PERSUASION_DIMENSIONS` rather than written out again
    so a dimension cannot exist as a selectable check the reviewing stage does
    not ask about, or the reverse.
    """
    return tuple(
        CheckDefinition(
            id=f"{PERSUASION_PREFIX}{slug}",
            label=label,
            description=question,
            kind=MODEL,
            category="persuasion",
            default_enabled=False,
        )
        for slug, label, question in PERSUASION_DIMENSIONS
    )


# Ordered by category, so the panel offers the groups in the order an advocate
# can work in: get it right, then make it complete, then make it land.
_CATEGORY_ORDER = {category.id: index for index, category in enumerate(CATEGORY_CATALOG)}
CHECK_CATALOG = tuple(
    sorted(
        (*_DECLARED_CHECKS, *_persuasion_checks()),
        key=lambda check: _CATEGORY_ORDER.get(check.category, len(_CATEGORY_ORDER)),
    )
)

CHECKS_BY_ID = {check.id: check for check in CHECK_CATALOG}
PERSUASION_CHECK_IDS = [check.id for check in CHECK_CATALOG if check.category == "persuasion"]
CORRECTNESS_CHECK_IDS = ["rule_elements", "record_support", "authority_support"]
# Stored when the author turns every check off. An empty list cannot carry that:
# a new session also has an empty list, and there it means "the defaults". Making
# the two the same would silently re-enable everything the author switched off.
NONE_SELECTED = "__none__"
DEFAULT_CHECK_IDS = list(CORRECTNESS_CHECK_IDS)
CHECK_MODES = [
    {
        "id": "correctness",
        "label": "Correctness",
        "description": "Bounded Opponent → Judge → Coach tests. Zero findings is allowed.",
        "checkIds": CORRECTNESS_CHECK_IDS,
    },
    {
        "id": "stress_test",
        "label": "Stress test",
        "description": "Optional open-ended adversarial and persuasion review.",
        "checkIds": ["adversarial", *PERSUASION_CHECK_IDS],
    },
]
REQUIREMENT_REASONS = {
    "native_draft": "This brief was uploaded rather than drafted here, so there is no template or draft session to validate.",
    "court_profile": "No court is selected for this session, so there are no filing rules to apply.",
    "case_record": "No case materials are in scope for this session.",
    "checklist": "No checklist is attached to this session.",
}


def catalog():
    return [check.to_dict() for check in CHECK_CATALOG]


def category_catalog():
    return [category.to_dict() for category in CATEGORY_CATALOG]


def persuasion_dimensions(selected_ids):
    """The dimensions of the suite the author left on, in catalog order."""
    chosen = set(selected_ids)
    return [
        {"id": f"{PERSUASION_PREFIX}{slug}", "label": label, "question": question}
        for slug, label, question in PERSUASION_DIMENSIONS
        if f"{PERSUASION_PREFIX}{slug}" in chosen
    ]


def normalize_selection(selected):
    """The author's explicit choice, keeping only checks that exist.

    An empty selection means the catalog defaults. It never means "run
    everything": widening a choice the author made is the same error as
    narrowing it.
    """
    if selected and NONE_SELECTED in selected:
        return []
    if not selected:
        return list(DEFAULT_CHECK_IDS)
    return [check_id for check_id in dict.fromkeys(selected) if check_id in CHECKS_BY_ID]


def plan_checks(selected, capabilities):
    """Decide, before anything runs, which checks will run and why the rest will not."""
    chosen = set(normalize_selection(selected))
    plan = []
    for check in CHECK_CATALOG:
        if check.id not in chosen:
            plan.append({**check.to_dict(), "status": "off", "reason": "You turned this check off for this session."})
            continue
        unmet = [name for name in check.requires if not capabilities.get(name)]
        if unmet:
            plan.append(
                {
                    **check.to_dict(),
                    "status": "unavailable",
                    "reason": " ".join(REQUIREMENT_REASONS.get(name, name) for name in unmet),
                }
            )
            continue
        plan.append({**check.to_dict(), "status": "on", "reason": ""})
    return plan


def will_run(plan, check_id):
    return any(entry["id"] == check_id and entry["status"] == "on" for entry in plan)

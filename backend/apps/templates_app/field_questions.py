"""Which template blanks are questions for the advocate, and which are drafting.

A prepared template's blanks are not all the same kind of thing:

* Some name a fact only the advocate can supply -- the hearing date, the time on
  the notice. Those are worth asking about.
* Some are the template author's note to whoever drafts the document --
  "[describe occupants]", "[how, when?]". That is drafting work, and the model
  has the case record it needs to do it. Asking "What is the describe
  occupants?" turns an instruction into a nonsense question.
* Some are artifacts of converting a Word original, where a run of underscores
  on a signature line became `fields.law_argument_32_blank`. Nobody can answer
  those, and they should never reach a person.

Classifying them here keeps the pre-draft questions short and answerable, and
lets everything else be filled from the case record or drafted.

Nothing here invents a value. Classification decides *who* answers a blank; the
answer itself comes from the case record, the advocate, or constrained
generation, all of which are the caller's business.
"""

from __future__ import annotations

from dataclasses import dataclass
import re

from apps.templates_app.placeholders import field_name_for_label
from apps.templates_app.template_variables import (
    LEGACY_LITERAL_FIELDS,
    declared_template_fields,
    is_unusable_field_key,
    normalize_field_path,
    template_field_label,
)


#: A blank the advocate should be asked about.
KIND_VALUE = "value"
#: A blank the draft writes from the case record.
KIND_NARRATIVE = "narrative"
#: A blank that conversion produced by accident.
KIND_UNUSABLE = "unusable"


# Two bindings for the same fact, which a Word original acquires when different
# paragraphs word it differently. One question fills both.
FIELD_KEY_ALIASES = {
    "landlord": "plaintiff_name",
    "landlord_name": "plaintiff_name",
    "plaintiff": "plaintiff_name",
}

# Instruction verbs the template author writes when the blank is prose to be
# written rather than a value to be looked up.
NARRATIVE_HEADS = {
    "describe",
    "explain",
    "summarize",
    "summarise",
    "list",
    "detail",
    "state",
    "how",
    "why",
    "what",
    "when",
    "where",
    "who",
    "anything",
}

# Blocks whose prose the model writes outright: a blank inside one is never
# rendered literally, so asking about it produces an answer nothing consumes.
GENERATED_FILL_MODES = {"constrained_generation"}

# Wording for the blanks that recur across housing templates. The generic
# "What is the <label>?" is fine for a well-named field and poor for the rest,
# so the common ones are written out as questions a person can actually answer.
FIELD_QUESTIONS = {
    "case_caption": "What caption should appear on this filing?",
    "filing_date": "On what date was this case filed?",
    "filing_year": "In what year was this case filed?",
    "hearing_date": "What is the date of the hearing this document concerns?",
    "hearing_time": "What time is the hearing scheduled for?",
    "housing_authority": "Which housing authority administers the subsidy?",
    "magistrate": "Which magistrate or judge is assigned?",
    "move_in_date": "When did the client move into the premises?",
    "opposing_counsel_address": "What is the address for opposing counsel?",
    "other_occupants": "Who else lives in the unit with the client?",
    "plaintiff_address": "What is the plaintiff's address?",
    "plaintiff_email": "What is the plaintiff's email address?",
    "plaintiff_name": "What is the plaintiff's full name, as it appears on the complaint?",
    "premises_address": "What is the address of the rental unit?",
    "service_date": "On what date was this document served?",
    "service_recipients": "Who was served, and at what address or email?",
    "termination_date": "What date did the notice give to terminate the tenancy?",
    "time": "What time is the hearing scheduled for?",
}

FIELD_TOKEN_RE_CACHE: dict[str, re.Pattern] = {}
# Legal prose is full of abbreviations ("Civ.R. 5(B)(4)", "R.C. 5321.04"), so a
# sentence only ends where an ordinary word does.
SENTENCE_SPLIT_RE = re.compile(r"(?<=[a-z0-9)\]”\"][.!?])\s+(?=[A-Z“\"(\[])|\n+")
CONTEXT_MAX_CHARS = 240
ANY_TOKEN_RE = re.compile(r"\{\{(.+?)\}\}|\{%.+?%\}", re.DOTALL)
BLANK_MARKER = "\x00blank\x00"


@dataclass(frozen=True)
class TemplateFieldRequest:
    """One template blank, and who should fill it."""

    key: str
    path: str
    label: str
    kind: str
    question: str
    context: str = ""
    block_key: str = ""
    block_label: str = ""


def canonical_field_key(key):
    """The field name a question is asked under, collapsing duplicate bindings."""
    name = str(key or "")
    return FIELD_KEY_ALIASES.get(name, name)


def field_keys_for_answer(key):
    """Every field name one answer should fill, canonical name first."""
    canonical = canonical_field_key(key)
    return [canonical, *sorted(name for name, target in FIELD_KEY_ALIASES.items() if target == canonical)]


def _looks_narrative(key) -> bool:
    parts = str(key or "").split("_")
    return bool(parts) and parts[0] in NARRATIVE_HEADS


def _field_token_re(key) -> re.Pattern:
    pattern = FIELD_TOKEN_RE_CACHE.get(key)
    if pattern is None:
        escaped = re.escape(key)
        pattern = re.compile(
            r"\{\{\s*fields(?:\.%s|\[\"%s\"\])\s*(?:\|[^}]*)?\}\}" % (escaped, escaped)
        )
        FIELD_TOKEN_RE_CACHE[key] = pattern
    return pattern


def _readable_token(match):
    """Render a neighbouring binding as the value it stands for."""
    expression = " ".join((match.group(1) or "").split())
    if not expression:
        return "____"
    name = expression.split("|")[0].strip()
    if name.startswith("fields"):
        name = normalize_field_path(name.replace('"', "").replace("[", ".").replace("]", ""))
    return f"[{template_field_label(name.split('.')[-1])}]"


def _context_sentence(body, key):
    """The template sentence around a blank, with the blank shown as a rule.

    Advocates recognize their own template wording faster than they recognize a
    field name, and "set for a first cause hearing on [Filing Date] at ____" is
    the difference between "What is the time?" and a question someone can answer
    without reopening the original.
    """
    marked = _field_token_re(key).sub(BLANK_MARKER, body or "")
    if BLANK_MARKER not in marked:
        return ""
    readable = ANY_TOKEN_RE.sub(_readable_token, marked)
    sentence = next(
        (part for part in SENTENCE_SPLIT_RE.split(readable) if BLANK_MARKER in part),
        readable,
    )
    return _around_blank(" ".join(sentence.replace(BLANK_MARKER, "\x00").split()))


def _around_blank(sentence):
    """Trim a long sentence to the wording either side of the blank."""
    if len(sentence) <= CONTEXT_MAX_CHARS:
        return sentence.replace("\x00", "____")
    position = sentence.find("\x00")
    start = max(0, position - CONTEXT_MAX_CHARS // 2)
    end = min(len(sentence), start + CONTEXT_MAX_CHARS)
    excerpt = sentence[start:end].replace("\x00", "____")
    return f"{'…' if start else ''}{excerpt}{'…' if end < len(sentence) else ''}"


def _instruction_index(blocks):
    """Map each field name back to the drafting instruction that produced it."""
    index = {}
    for block in blocks:
        for instruction in block.ai_instructions or []:
            text = " ".join(str(instruction or "").split())
            if not text:
                continue
            name = field_name_for_label(text)
            if name and name not in index:
                index[name] = (text, block)
    return index


def _as_directive(text):
    """Turn a template author's note into a sentence a reader can follow."""
    cleaned = " ".join(str(text or "").split()).strip(" .:;,")
    if not cleaned:
        return ""
    if cleaned.isupper():
        cleaned = cleaned.capitalize()
    else:
        cleaned = cleaned[0].upper() + cleaned[1:]
    return cleaned if cleaned.endswith("?") else f"{cleaned}."


def template_field_requests(template):
    """Classify every blank a template declares.

    Returns one :class:`TemplateFieldRequest` per declared field, in the order
    the template declares them, including the unusable ones so a caller can log
    or repair them rather than silently losing track.
    """
    if not template:
        return []
    blocks = list(template.blocks.all())
    instructions = _instruction_index(blocks)

    # A canonical field can be declared under more than one name, and the
    # template sentence worth showing may sit under either of them.
    declared = {}
    for path in declared_template_fields(template):
        raw_key = normalize_field_path(path)
        if raw_key in LEGACY_LITERAL_FIELDS:
            continue
        declared.setdefault(canonical_field_key(raw_key), []).append(raw_key)

    requests = []
    for key, raw_keys in declared.items():
        label = template_field_label(key)
        using_blocks = [
            block
            for block in blocks
            if any(_field_token_re(raw_key).search(block.body or "") for raw_key in raw_keys)
        ]
        context = ""
        block = using_blocks[0] if using_blocks else None
        if block:
            context = next(
                (found for raw_key in raw_keys if (found := _context_sentence(block.body, raw_key))),
                "",
            )

        instruction_text, instruction_block = "", None
        for raw_key in raw_keys:
            if raw_key in instructions:
                instruction_text, instruction_block = instructions[raw_key]
                break
        if is_unusable_field_key(key):
            kind, question = KIND_UNUSABLE, ""
        elif instruction_text:
            kind = KIND_NARRATIVE
            question = _as_directive(instruction_text)
            block = block or instruction_block
        elif _looks_narrative(key):
            kind = KIND_NARRATIVE
            question = _as_directive(label)
        elif using_blocks and all(item.ai_fill_mode in GENERATED_FILL_MODES for item in using_blocks):
            # The model writes this block's prose outright, so the blank never
            # reaches the page as a placeholder.
            kind = KIND_NARRATIVE
            question = _as_directive(label)
        else:
            kind = KIND_VALUE
            question = FIELD_QUESTIONS.get(key) or f"What is the {label.lower()}?"

        requests.append(
            TemplateFieldRequest(
                key=key,
                path=f"fields.{key}",
                label=label,
                kind=kind,
                question=question,
                context=context,
                block_key=getattr(block, "key", ""),
                block_label=getattr(block, "label", ""),
            )
        )
    return requests

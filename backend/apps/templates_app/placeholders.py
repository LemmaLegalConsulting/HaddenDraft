"""Turn fill-in language into Jinja bindings without disturbing run formatting.

Advocates mark "you must supply this" three ways in the maintained originals:
square brackets, a run of underscores, and yellow highlighting. All three are
converted here so a prepared template keeps the original wording and formatting
and varies only where the author intended it to vary.

Substitution happens over the paragraph's concatenated text and is written back
run by run. Placeholders regularly straddle runs -- Word splits `[DATE] at
[TIME]` into `[`, `DATE] at [TIME]`, `.` after a spell-check pass -- so a
run-at-a-time regex would miss most of them. Rebuilding run by run is what keeps
bold, italics, underline, and superscript intact on the surrounding literal
text, which paragraph-level rewriting destroys.
"""

from __future__ import annotations

from copy import deepcopy
import re
from dataclasses import dataclass, field

from django.utils.text import slugify


BRACKET_RE = re.compile(r"\[([^\[\]]*)\]")
UNDERSCORE_RE = re.compile(r"_{3,}")
# "202__" and "20__" are year stubs; the digits are part of the placeholder.
YEAR_STUB_RE = re.compile(r"\b20\d?_{2,}")
JINJA_TOKEN_RE = re.compile(r"\{\{.*?\}\}|\{%.*?%\}")

EDITORIAL_BRACKETS = {"her", "his", "or", "s", "section", "x", "sic", "and"}
PLACEHOLDER_CUE_RE = re.compile(
    r"address|applicant|application|attorney|bar|case|caption|client|copy|count|court|date|deadline|"
    r"defendant|describe|document|email|eviction|fax|filing|hearing|housing|insert|judge|landlord|lease|list|magistrate|"
    r"mail|month|name|notice|number|occupant|opposing|payment|phone|plaintiff|premises|program|rent|"
    r"section|select|signature|subsidy|term|time|tenancy|title|voucher|what|when|where|who|why",
    re.I,
)
# Bracketed text that instructs the drafter rather than naming a value.
INSTRUCTION_CUE_RE = re.compile(
    r"\b(?:insert|describe|synopsis|summari[sz]e|explain|list|copy from|state|detail|anything|"
    r"what|who|when|where|how)\b",
    re.I,
)

PLACEHOLDER_ALIASES = {
    "client name": "defendant",
    "defendant": "defendant",
    "defendant name": "defendant",
    "attorney name": "advocate_name",
    "attorney name & bar no": "advocate_name_and_bar",
    "attorney name and bar no": "advocate_name_and_bar",
    "insert signature block": "advocate_signature_block",
    "signature block": "advocate_signature_block",
    "email": "advocate_email",
    "attorney email": "advocate_email",
    "phone": "advocate_phone",
    "phone number": "advocate_phone",
    "attorney telephone": "advocate_phone",
    "case number": "case_number",
    "case no.": "case_number",
    "case name": "case_caption",
    "plaintiff": "fields.plaintiff_name",
    "plaintiff's email": "fields.plaintiff_email",
    "plaintiff's address": "fields.plaintiff_address",
    "other occupants": "fields.other_occupants",
    "copy from noa": "fields.service_recipients",
    # The wrapper's "help with your [eviction/housing issue]" names what the
    # case is about, which the case record already knows.
    "eviction/housing issue": "matter_subject",
    "eviction/housing matter": "matter_subject",
    "pha": "fields.housing_authority",
    "magistrate": "fields.magistrate",
}
# "date", "time", and "address" are deliberately absent: which date or address a
# placeholder means depends on the sentence around it, so they are resolved by
# context below rather than by a fixed alias.

CONTEXT_FIELD_HINTS = (
    ("hearing", "date", "fields.hearing_date"),
    ("served", "date", "fields.service_date"),
    ("service", "date", "fields.service_date"),
    ("certify", "date", "fields.service_date"),
    ("move-in", "date", "fields.move_in_date"),
    ("moved in", "date", "fields.move_in_date"),
    ("filed", "date", "fields.filing_date"),
    ("terminate", "date", "fields.termination_date"),
)

# Wording that puts a blank on the signature rule rather than in a sentence.
# "/s/" is deliberately absent: it introduces the signer's name on the same
# line, so a blank after it is the name, not the whole block.
SIGNATURE_CUE_RE = re.compile(
    r"respectfully submitted|attorney for|counsel for|signature of", re.I
)

# A highlighted span this long with no fill-in cue is alternative wording the
# advocate keeps or deletes, not a value to supply.
OPTIONAL_PROSE_MIN_WORDS = 8


@dataclass
class ParagraphConversion:
    """What a paragraph contributed to the template's variable surface."""

    fields: set[str] = field(default_factory=set)
    flags: set[str] = field(default_factory=set)
    instructions: list[str] = field(default_factory=list)
    changed: bool = False


# Sentence scaffolding that names nothing. "The 3-Day Notice is from ____"
# should yield `notice_from`, not `the_3_day_notice_is`.
NAME_STOPWORDS = {
    "a", "an", "and", "at", "but", "by", "for", "from", "in", "is", "it", "of",
    "on", "or", "so", "than", "that", "the", "then", "to", "was", "were", "with",
    "you", "your", "i", "we", "they", "this", "these", "there",
}


def _field_name(label: str, fallback: str) -> str:
    clean = re.sub(r"[^\w\s-]", " ", label).strip()
    name = slugify(clean).replace("-", "_") or fallback.replace("-", "_")
    name = re.sub(r"_+", "_", name).strip("_")
    if not name:
        name = fallback.replace("-", "_")
    parts = [part for part in name.split("_") if part]
    # Drop leading filler, but never everything: a label made only of stopwords
    # still has to produce an identifier.
    meaningful = [part for part in parts if part not in NAME_STOPWORDS]
    parts = meaningful or parts
    # Long instruction text makes an unusable identifier; keep the leading terms.
    name = "_".join(parts[:4])
    return f"field_{name}" if name[:1].isdigit() else name


def field_name_for_label(label: str) -> str:
    """The `fields.<name>` a piece of fill-in text converts to.

    Exposed so a caller holding a block's recorded drafting instruction can find
    the field that instruction produced, and treat it as drafting work rather
    than as a question of fact.
    """
    return _field_name(label, "")


def _normalize(label: str) -> str:
    # Word autocorrects quotes, so alias lookups must see the straight forms.
    text = str(label or "").replace("’", "'").replace("‘", "'")
    text = text.replace("“", '"').replace("”", '"')
    return " ".join(text.split()).strip(" .:_-[]()")


def looks_like_placeholder(label: str) -> bool:
    normalized = _normalize(label)
    lowered = normalized.casefold()
    if not normalized:
        return True
    if lowered in EDITORIAL_BRACKETS or normalized.isdigit() or len(normalized) == 1:
        return False
    if normalized.isupper() and len(normalized) <= 80:
        return True
    return bool(PLACEHOLDER_CUE_RE.search(normalized))


def is_instruction(label: str) -> bool:
    """True when bracketed text tells the drafter what to write."""
    normalized = _normalize(label)
    if not normalized:
        return False
    if "?" in normalized or "/" in normalized and len(normalized.split()) > 4:
        return True
    return bool(INSTRUCTION_CUE_RE.search(normalized)) and len(normalized.split()) >= 2


def context_label(text: str, start: int, fallback: str) -> str:
    """The words leading up to a fill-in, used to name and type it."""
    prefix = text[:start].strip()
    # Abbreviations end sentences too ("Case No. ____"), so fall back through
    # empty trailing segments instead of losing the label to the split.
    segments = [segment.strip(" :,-–—()") for segment in re.split(r"[.;!?]", prefix)]
    for segment in reversed(segments):
        if 1 <= len(segment) <= 80:
            return segment
    return fallback


def placeholder_expression(label: str, fallback: str, *, context: str = "", nearby: str = "") -> str:
    """Map one fill-in to the Jinja path that should replace it.

    ``nearby`` is the wording of the surrounding lines. It is deliberately not
    used for naming -- a blank is named after the sentence it sits in, and
    borrowing the neighbours' words produces fields like `fields.sincerely` --
    but a blank standing alone on its own line has no sentence, and the lines
    around it are the only thing that says whether it is a signature rule.
    """
    normalized = _normalize(label).casefold()
    context_normalized = " ".join(str(context or "").lower().split())
    nearby_normalized = " ".join(str(nearby or "").lower().split())

    alias = PLACEHOLDER_ALIASES.get(normalized)
    if alias:
        return "{{ " + alias + " }}"

    if not normalized:
        if SIGNATURE_CUE_RE.search(context_normalized) or (
            context == fallback and SIGNATURE_CUE_RE.search(nearby_normalized)
        ):
            # The rule an advocate signs on, not a value anyone types.
            return "{{ advocate_signature_block }}"
        if "defendant" in context_normalized or "client" in context_normalized:
            return "{{ defendant }}"
        if "plaintiff" in context_normalized or "landlord" in context_normalized:
            return "{{ fields.plaintiff_name }}"
        if "magistrate" in context_normalized:
            return "{{ fields.magistrate }}"
        if "case no" in context_normalized or "case number" in context_normalized:
            return "{{ case_number }}"
        if "served" in context_normalized or "service" in context_normalized:
            return "{{ fields.service_date }}"
        if "attorney" in context_normalized or "counsel" in context_normalized:
            return "{{ advocate_name }}"
        if "ph." in context_normalized or "phone" in context_normalized or "tel" in context_normalized:
            return "{{ advocate_phone }}"
        return "{{ fields." + _field_name(context, fallback) + " }}"

    if normalized == "name":
        if "defendant" in context_normalized or "client" in context_normalized:
            return "{{ defendant }}"
        if "attorney" in context_normalized or "counsel" in context_normalized:
            return "{{ advocate_name }}"
        return "{{ fields." + _field_name(context, fallback) + " }}"

    if normalized in {"insert", "fill in", "blank"}:
        return "{{ fields." + _field_name(context, fallback) + " }}"

    if "address" in normalized and "attorney" not in normalized:
        if "opposing" in context_normalized or "landlord" in context_normalized or "plaintiff" in context_normalized:
            return "{{ fields.opposing_counsel_address }}"
        return "{{ fields.premises_address }}"

    if normalized == "date" or normalized.endswith(" date") or normalized.startswith("date"):
        for context_cue, label_cue, path in CONTEXT_FIELD_HINTS:
            if context_cue in context_normalized and label_cue in normalized:
                return "{{ " + path + " }}"
        return "{{ fields.filing_date }}"

    if normalized == "time" or normalized.endswith(" time"):
        return "{{ fields.hearing_time }}" if "hearing" in context_normalized else "{{ fields.time }}"

    if "case caption" in normalized:
        return "{{ fields.case_caption }}"
    if "plaintiff" in normalized:
        return "{{ fields.plaintiff_name }}"
    if "signature block" in normalized:
        return "{{ advocate_signature_block }}"

    return "{{ fields." + _field_name(label, fallback) + " }}"


def _run_spans(paragraph):
    """Return (run, start, end) for every run, over the paragraph's full text."""
    spans = []
    cursor = 0
    for run in paragraph.runs:
        length = len(run.text)
        spans.append((run, cursor, cursor + length))
        cursor += length
    return spans


def _is_highlighted(run):
    return run.font.highlight_color is not None


def _highlight_spans(spans):
    """Contiguous character ranges covered by highlighted runs."""
    ranges = []
    for run, start, end in spans:
        if start == end or not _is_highlighted(run):
            continue
        if ranges and ranges[-1][1] == start:
            ranges[-1][1] = end
        else:
            ranges.append([start, end])
    return [(start, end) for start, end in ranges]


def _clear_highlight(run):
    run.font.highlight_color = None


def _clear_highlight_over(paragraph, start, end):
    """Drop the author's "fill this in" marking without touching the text."""
    for run, run_start, run_end in _run_spans(paragraph):
        if run_end > start and run_start < end and _is_highlighted(run):
            _clear_highlight(run)


@dataclass
class _Replacement:
    start: int
    end: int
    text: str
    drop_highlight: bool = True


def _bracket_replacements(text, fallback_prefix, conversion, protected=(), nearby=""):
    replacements = []
    for index, match in enumerate(BRACKET_RE.finditer(text), start=1):
        if any(match.start() >= start and match.end() <= end for start, end in protected):
            continue
        label = match.group(1)
        if not looks_like_placeholder(label):
            continue
        fallback = f"{fallback_prefix}_{index}"
        context = context_label(text, match.start(), fallback)
        if is_instruction(label):
            conversion.instructions.append(_normalize(label))
        expression = placeholder_expression(label, fallback, context=context, nearby=nearby)
        _record(conversion, expression)
        replacements.append(_Replacement(match.start(), match.end(), expression))
    return replacements


def _underscore_replacements(text, fallback_prefix, conversion, taken, nearby=""):
    replacements = []
    index = 0
    for pattern in (YEAR_STUB_RE, UNDERSCORE_RE):
        for match in pattern.finditer(text):
            if any(match.start() < end and start < match.end() for start, end in taken):
                continue
            index += 1
            fallback = f"{fallback_prefix}_blank_{index}"
            context = context_label(text, match.start(), fallback)
            label = "" if pattern is UNDERSCORE_RE else "year"
            if label == "year":
                expression = "{{ fields.filing_year }}"
            else:
                expression = placeholder_expression("", fallback, context=context, nearby=nearby)
            _record(conversion, expression)
            replacements.append(_Replacement(match.start(), match.end(), expression))
            taken.append((match.start(), match.end()))
    return replacements


def _flag_name(text, fallback):
    words = [word for word in re.findall(r"[A-Za-z]+", text.lower()) if len(word) > 2][:5]
    return "include_" + ("_".join(words) if words else fallback)


def _highlight_replacements(paragraph, text, fallback_prefix, conversion, taken, nearby=""):
    """Highlighted spans become values, or keep their wording behind a toggle."""
    replacements = []
    for index, (start, end) in enumerate(_highlight_spans(_run_spans(paragraph)), start=1):
        segment = text[start:end]
        stripped = segment.strip()
        if not stripped:
            continue
        if any(start < covered_end and covered_start < end for covered_start, covered_end in taken):
            # Already handled as a bracket or underscore fill-in.
            continue
        if _normalize(stripped).casefold().startswith("case caption"):
            # An editorial marker for "the filing caption goes here". Export
            # builds the real caption from it, so it must stay literal text.
            _clear_highlight_over(paragraph, start, end)
            taken.append((start, end))
            continue
        fallback = f"{fallback_prefix}_hl_{index}"
        words = stripped.split()
        if len(words) >= OPTIONAL_PROSE_MIN_WORDS:
            # A sentence this long is wording, not a value, even though it is
            # bound to mention a cue word like "plaintiff" or "date". Collapsing
            # it into one variable would silently delete the author's text.
            flag = _flag_name(stripped, fallback)
            conversion.flags.add(flag)
            leading = segment[: len(segment) - len(segment.lstrip())]
            trailing = segment[len(segment.rstrip()) :]
            expression = f"{leading}{{% if {flag} %}}{stripped}{{% endif %}}{trailing}"
            replacements.append(_Replacement(start, end, expression, drop_highlight=True))
            taken.append((start, end))
            continue
        if not looks_like_placeholder(stripped):
            continue
        context = context_label(text, start, fallback)
        if is_instruction(stripped):
            conversion.instructions.append(_normalize(stripped))
        expression = placeholder_expression(stripped, fallback, context=context, nearby=nearby)
        _record(conversion, expression)
        replacements.append(_Replacement(start, end, expression))
        taken.append((start, end))
    return replacements


def _record(conversion, expression):
    inner = expression.strip("{} ").strip()
    if inner.startswith("fields."):
        conversion.fields.add(inner)


def _apply_replacements(paragraph, replacements):
    """Write substitutions back run by run, keeping every run's formatting."""
    if not replacements:
        return False
    spans = _run_spans(paragraph)
    if not spans:
        return False
    replacements = sorted(replacements, key=lambda item: item.start)

    for run, run_start, run_end in spans:
        pieces = []
        cursor = run_start
        dropped_highlight = False
        for replacement in replacements:
            if replacement.end <= run_start or replacement.start >= run_end:
                continue
            overlap_start = max(replacement.start, run_start)
            if overlap_start > cursor:
                pieces.append(run.text[cursor - run_start : overlap_start - run_start])
            if replacement.start >= run_start:
                # The run where the placeholder opens carries the whole binding.
                pieces.append(replacement.text)
                if replacement.drop_highlight:
                    dropped_highlight = True
            cursor = max(cursor, min(replacement.end, run_end))
        if cursor == run_start and not pieces:
            continue
        if cursor < run_end:
            pieces.append(run.text[cursor - run_start :])
        run.text = "".join(pieces)
        if dropped_highlight and _is_highlighted(run):
            _clear_highlight(run)
    return True


def convert_paragraph(paragraph, fallback_prefix, nearby=""):
    """Replace every fill-in in one paragraph, preserving run formatting.

    ``nearby`` carries the wording of the surrounding paragraphs, which is the
    only context a fill-in standing alone on its own line has.
    """
    conversion = ParagraphConversion()
    text = paragraph.text
    if not text.strip():
        return conversion
    # A paragraph can contain both an already-prepared binding and an older
    # bracket placeholder.  Converting only the latter is safe: the bracket
    # and underscore patterns do not match Jinja syntax.  The old early return
    # made mixed paragraphs impossible to repair on re-ingest.

    protected = [match.span() for match in JINJA_TOKEN_RE.finditer(text)]
    taken: list[tuple[int, int]] = list(protected)
    replacements = _bracket_replacements(text, fallback_prefix, conversion, protected, nearby)
    taken.extend((item.start, item.end) for item in replacements)
    replacements += _underscore_replacements(text, fallback_prefix, conversion, taken, nearby)
    replacements += _highlight_replacements(paragraph, text, fallback_prefix, conversion, taken, nearby)

    conversion.changed = _apply_replacements(paragraph, replacements)
    return conversion


def convert_text(text, fallback_prefix, nearby=""):
    """Placeholder conversion for plain strings (block `body` previews)."""
    conversion = ParagraphConversion()
    if not text:
        return text, conversion
    protected = [match.span() for match in JINJA_TOKEN_RE.finditer(text)]
    replacements = _bracket_replacements(text, fallback_prefix, conversion, protected, nearby)
    taken = [*protected, *((item.start, item.end) for item in replacements)]
    replacements += _underscore_replacements(text, fallback_prefix, conversion, taken, nearby)
    pieces = []
    cursor = 0
    for replacement in sorted(replacements, key=lambda item: item.start):
        if replacement.start < cursor:
            continue
        pieces.append(text[cursor : replacement.start])
        pieces.append(replacement.text)
        cursor = replacement.end
    pieces.append(text[cursor:])
    converted = "".join(pieces)
    conversion.changed = converted != text
    return converted, conversion


def convert_editor_state(state, fallback_prefix):
    """Convert legacy bracket fill-ins inside a Lexical JSON document.

    Catalogs created before mixed Jinja/bracket repair can carry the old text
    in their saved editor state even after the plain body is normalized.  Walk
    text nodes only, so formatting, paragraph spacing, and every other Lexical
    property remain unchanged.
    """
    if not isinstance(state, dict) or not isinstance(state.get("root"), dict):
        return state, ParagraphConversion()

    converted_state = deepcopy(state)
    conversion = ParagraphConversion()
    text_index = 0

    def visit(node):
        nonlocal text_index
        if not isinstance(node, dict):
            return
        if node.get("type") == "text":
            text_index += 1
            converted, node_conversion = convert_text(
                node.get("text", ""), f"{fallback_prefix}_{text_index}"
            )
            node["text"] = converted
            conversion.fields.update(node_conversion.fields)
            conversion.flags.update(node_conversion.flags)
            conversion.instructions.extend(node_conversion.instructions)
            conversion.changed = conversion.changed or node_conversion.changed
        for child in node.get("children") or []:
            visit(child)

    visit(converted_state["root"])
    return converted_state, conversion

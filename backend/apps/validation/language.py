"""Grammar, easily-confused words, and passive voice in a filing.

Three deliberate limits, each of them the reason this module exists separately
from ``apps.validation.readability``:

* **No dictionary spell check.** A general dictionary flags "replevin",
  "forcible entry and detainer", "estoppel", and half of every case name. An
  advocate who has to dismiss forty false positives stops reading the check. What
  runs instead is a curated list of the words legal writing actually gets wrong,
  where a hit is nearly always a real error, plus real-word confusions reported
  as something to look at rather than as a mistake.
* **Passive voice is not an error.** "Service was perfected" and "judgment is
  hereby granted" are the register a court expects. Accepted phrases are
  file-backed and extendable per session, and everything else is reported at
  info severity.
* **Only high-precision grammar.** Doubled words, a missing space after a
  sentence, unbalanced delimiters. Subject-verb agreement and the like are left
  out because getting them wrong on legal prose is worse than not checking.

Rule codes: E/W/I1100-1199.
"""

import functools
import re

import yaml

from apps.core.content_library import content_path
from apps.validation.findings import make_finding, sort_and_condense_findings


RULES_PATH = ("drafting-rules", "checks", "legal-language.yaml")
CATEGORY = "language"
SEVERITY_PREFIX = {"error": "E", "warning": "W", "info": "I"}

CODE_CONFUSED = 1100
CODE_CONFUSABLE_PAIR = 1110
CODE_GRAMMAR = 1120
CODE_PASSIVE = 1130

# "was granted", "is hereby ordered", "were given" -- the same construction the
# plain-language check looks for, applied to a different audience.
PASSIVE_RE = re.compile(
    r"\b(?:is|are|was|were|be|been|being|will be|has been|have been|had been)\s+"
    r"(?:\w+ly\s+)?(\w+(?:ed|en))\b",
    re.IGNORECASE,
)
DOUBLED_WORD_RE = re.compile(r"\b(\w{2,})\s+\1\b", re.IGNORECASE)
MISSING_SPACE_RE = re.compile(r"\b[a-z]{2,}[.!?][A-Z][a-z]{2,}")
EG_IE_RE = re.compile(r"\b(e\.g\.|i\.e\.)(?!,)", re.IGNORECASE)
CITATION_LIKE_RE = re.compile(r"\b(?:v\.|§|R\.C\.|U\.S\.C\.|C\.F\.R\.|No\.|Nos\.|Ohio App\.|Ohio St\.)")
DELIMITERS = [("(", ")", "parenthesis"), ("[", "]", "bracket"), ("{", "}", "brace")]

# A period in a brief is usually not the end of a sentence. Case names,
# reporters, courts, parties and dates are all abbreviated -- "Ohio App.",
# "Hous. Auth.", "Inc.", "F." -- and splitting on every period manufactures a
# "sentence" starting mid-citation. Across fifteen real filings, every single
# lowercase-sentence-start finding came from one of those splits and not one was
# a real error.
#
# What separates the two is the word before the period, not a list of
# abbreviations to keep up to date: a legal abbreviation is short and
# capitalized, and an English sentence ends on an ordinary lowercase word. So a
# period only ends a sentence when a run of lowercase letters precedes it; ! and
# ? always do.
# The word before the period has to be an ordinary lowercase word: "Invests.",
# "Assoc." and "Freed." are abbreviations even though they end in lowercase
# letters, so the token must not begin with a capital either.
_CLOSERS = "[\u201d\u2019\"')\]]*"
SENTENCE_BOUNDARY_RE = re.compile(rf"(?:(?<![A-Za-z])[a-z]{{4,}}\.|[!?]){_CLOSERS}\s+")
# A fragment that opens with a subsection marker, a citation signal, or a
# pinpoint is not a sentence that forgot its capital.
SENTENCE_START_EXEMPT_RE = re.compile(
    r"^(?:"
    r"[a-z0-9]{1,4}[.)](?:\s|[A-Z])"  # a. / 2) / iii. subsection headings
    r"|(?:see|accord|cf|e\.g|i\.e|id|but see|compare|contra|accord|quoting|citing|v|vs)\b\.?"
    r"|\S+@\S+|https?://\S+|c/o\s"
    r"|at\s+(?:\d|§|¶|p\.)"  # a pinpoint citation, not "at trial ..."
    r")",
    re.IGNORECASE,
)

# A closing parenthesis with nothing opened is usually not an unbalanced
# delimiter. It is an enumerator -- "1)", "a)", "iii)" -- or the column of ')'
# down the side of a caption, and every filing has both. Neither is checked by
# removing them from the text first: "(Attached as Appendix A)" would lose its
# closer and the check would then report the opening parenthesis as unclosed.
# They are recognized only at a closer the scan could not match.
ENUMERATOR_RE = re.compile(r"(?:^|[\s(\u201c\"';:,.])(?:\d{1,2}|[a-zA-Z]|[ivxlcIVXLC]{1,5})\)$")
CAPTION_COLUMN_RE = re.compile(r"(?m)(?:^[ \t]*\)[ \t]*\n(?:[ \t]*\n)*){2,}")


def load_rules():
    path = content_path(*RULES_PATH)
    if not path.is_file():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


@functools.lru_cache(maxsize=1)
def _cached_rules():
    return load_rules()


def split_sentences(text):
    """Sentences, treating a period inside a citation as part of the citation."""
    sentences = []
    current = 0
    for boundary in SENTENCE_BOUNDARY_RE.finditer(text):
        sentences.append(text[current : boundary.end()])
        current = boundary.end()
    sentences.append(text[current:])
    return sentences


# A drafting note left in the text -- "[from who?]", "[Add facts here]" -- carries
# its own punctuation and splits the sentence it interrupts. The placeholder
# check already reports the note; the grammar check must not report the split as
# a second, different problem. Short brackets are alterations in a quotation
# ("[t]he act"), not notes, and are left alone.
DRAFTING_NOTE_RE = re.compile(r"\[[^\]]{8,300}\]")


def strip_delimiter_conventions(text):
    """Remove the one piece of layout that is punctuation only by accident."""
    return CAPTION_COLUMN_RE.sub("", text)


def unmatched_delimiters(text, opener, closer):
    """Where a delimiter is actually unbalanced, rather than how many are.

    Counting says "6 closing parenthesis(s) with nothing opened", which an
    advocate cannot act on and which an enumerated list produces without
    anything being wrong. Scanning says which passage to look at, and lets an
    unmatched closer be recognized as an enumerator where a count cannot.
    """
    open_positions = []
    unmatched = []
    for index, char in enumerate(text):
        if char == opener:
            open_positions.append(index)
        elif char == closer:
            if open_positions:
                open_positions.pop()
            elif not (closer == ")" and ENUMERATOR_RE.search(text[max(0, index - 8) : index + 1])):
                unmatched.append(("close", index))
    return unmatched + [("open", index) for index in open_positions]


def _around(text, index, width=60):
    return re.sub(r"\s+", " ", text[max(0, index - width) : index + width]).strip()


def _finding(document_id, severity, number, *, target, message, label, details=None):
    severity = severity if severity in SEVERITY_PREFIX else "info"
    return make_finding(
        draft_id=document_id,
        rule_code=f"{SEVERITY_PREFIX[severity]}{number}",
        severity=severity,
        category=CATEGORY,
        target=target,
        message=re.sub(r"\s+", " ", message).strip(),
        details=details or {},
        action={"type": "human_review", "label": label, "payload": {}},
        manual_review=severity != "info",
    )


def check_confused_words(text, rules, document_id):
    """Words legal writing gets wrong often enough that a hit is nearly always real."""
    findings = []
    for entry in rules.get("confused_words") or []:
        if not isinstance(entry, dict):
            continue
        wrong = str(entry.get("wrong") or "").strip()
        right = str(entry.get("right") or "").strip()
        if not wrong or not right:
            continue
        for match in re.finditer(rf"\b{re.escape(wrong)}\b", text, flags=re.IGNORECASE):
            note = f" {entry['note']}" if entry.get("note") else ""
            findings.append(
                _finding(
                    document_id,
                    "warning",
                    CODE_CONFUSED,
                    target=wrong,
                    message=f'"{match.group(0)}" is almost always "{right}" in a filing.{note}',
                    label="Correct the spelling.",
                    details={"wrong": wrong, "right": right, "excerpt": _excerpt(text, match)},
                )
            )
            break  # One finding per word; a repeated typo is one correction.
    return findings


def check_confusable_pairs(text, rules, document_id):
    """Real words used for the wrong real word: reported to check, never as an error."""
    findings = []
    lowered = text.casefold()
    for entry in rules.get("easily_confused_pairs") or []:
        words = [str(word).casefold() for word in (entry or {}).get("words") or []]
        present = [word for word in words if re.search(rf"\b{re.escape(word)}\b", lowered)]
        # Only worth raising when both of a pair appear: one on its own is
        # almost certainly the word that was meant.
        if len(present) < 2:
            continue
        note = f" {entry['note']}" if entry.get("note") else ""
        findings.append(
            _finding(
                document_id,
                "info",
                CODE_CONFUSABLE_PAIR,
                target=" / ".join(words),
                message=f'Both "{present[0]}" and "{present[1]}" appear. Check that each is the word meant.{note}',
                label="Check which word was meant.",
                details={"words": words},
            )
        )
    return findings


def _excerpt(text, match, *, width=60):
    start = max(match.start() - width, 0)
    return re.sub(r"\s+", " ", text[start : match.end() + width]).strip()


def _grammar_spec(rules, check_id):
    for spec in rules.get("grammar") or []:
        if isinstance(spec, dict) and spec.get("id") == check_id:
            return spec
    return {}


def check_grammar(text, rules, document_id):
    findings = []

    spec = _grammar_spec(rules, "doubled_word")
    if spec:
        for match in list(DOUBLED_WORD_RE.finditer(text))[:10]:
            findings.append(
                _finding(
                    document_id,
                    spec.get("severity", "warning"),
                    CODE_GRAMMAR,
                    target="doubled word",
                    message=str(spec.get("message", "")).format(match=match.group(1)),
                    label=spec.get("label", "Remove the repeated word."),
                    details={"excerpt": _excerpt(text, match)},
                )
            )

    spec = _grammar_spec(rules, "missing_space_after_period")
    if spec:
        for match in list(MISSING_SPACE_RE.finditer(text))[:10]:
            # A citation is full of periods that are not sentence ends.
            if CITATION_LIKE_RE.search(_excerpt(text, match)):
                continue
            findings.append(
                _finding(
                    document_id,
                    spec.get("severity", "warning"),
                    CODE_GRAMMAR,
                    target="sentence spacing",
                    message=str(spec.get("message", "")).format(match=match.group(0)),
                    label=spec.get("label", "Add the missing space."),
                    details={"excerpt": _excerpt(text, match)},
                )
            )

    spec = _grammar_spec(rules, "unbalanced_delimiters")
    if spec:
        delimiter_text = strip_delimiter_conventions(text)
        for opener, closer, name in DELIMITERS:
            unmatched = unmatched_delimiters(delimiter_text, opener, closer)
            for kind, index in unmatched[:3]:
                detail = (
                    f"An opening {name} is never closed."
                    if kind == "open"
                    else f"A closing {name} has nothing opened before it."
                )
                findings.append(
                    _finding(
                        document_id,
                        spec.get("severity", "warning"),
                        CODE_GRAMMAR,
                        target=f"{name}s",
                        # A count on its own ("6 closing parenthesis(s)") cannot be
                        # acted on. The passage can.
                        message=str(spec.get("message", "{detail}")).format(detail=detail)
                        + f' Near: "{_around(delimiter_text, index)}"',
                        label=spec.get("label", "Balance the delimiters."),
                        details={"opener": opener, "kind": kind, "excerpt": _around(delimiter_text, index)},
                    )
                )
        quotes = delimiter_text.count('"')
        if quotes % 2:
            findings.append(
                _finding(
                    document_id,
                    spec.get("severity", "warning"),
                    CODE_GRAMMAR,
                    target="quotation marks",
                    message=str(spec.get("message", "{detail}")).format(
                        detail=f"An odd number of quotation marks ({quotes}); one quotation is unclosed."
                    ),
                    label=spec.get("label", "Close the quotation."),
                    details={"count": quotes},
                )
            )

    spec = _grammar_spec(rules, "eg_ie_comma")
    if spec:
        for match in list(EG_IE_RE.finditer(text))[:5]:
            findings.append(
                _finding(
                    document_id,
                    spec.get("severity", "info"),
                    CODE_GRAMMAR,
                    target=match.group(1),
                    message=str(spec.get("message", "")).format(match=match.group(1)),
                    label=spec.get("label", "Add the comma."),
                    details={"excerpt": _excerpt(text, match)},
                )
            )

    spec = _grammar_spec(rules, "lowercase_sentence_start")
    if spec:
        reported = 0
        sentences = split_sentences(DRAFTING_NOTE_RE.sub(" ", text))
        for sentence in sentences:
            stripped = sentence.strip()
            if reported >= 5 or len(stripped) < 12 or not stripped[:1].islower():
                continue
            # A citation signal, a subsection heading, an address or a pinpoint
            # is conventional, not a slip.
            if SENTENCE_START_EXEMPT_RE.match(stripped):
                continue
            reported += 1
            findings.append(
                _finding(
                    document_id,
                    spec.get("severity", "info"),
                    CODE_GRAMMAR,
                    target="sentence start",
                    message=str(spec.get("message", "")).format(match=stripped[:40]),
                    label=spec.get("label", "Check the sentence start."),
                    details={"excerpt": stripped[:120]},
                )
            )
    return findings


def accepted_passive_phrases(rules, extra=()):
    configured = (rules.get("passive_voice") or {}).get("accepted_phrases") or []
    return {str(phrase).casefold().strip() for phrase in [*configured, *extra] if str(phrase).strip()}


def check_passive_voice(text, rules, document_id, *, accepted_extra=(), limit=12):
    """Report passive constructions a court is not already expecting to read."""
    spec = rules.get("passive_voice") or {}
    accepted = accepted_passive_phrases(rules, accepted_extra)
    findings = []
    for match in PASSIVE_RE.finditer(text):
        phrase = re.sub(r"\s+", " ", match.group(0)).casefold()
        if any(allowed in phrase or phrase in allowed for allowed in accepted):
            continue
        findings.append(
            _finding(
                document_id,
                spec.get("severity", "info"),
                CODE_PASSIVE,
                target=phrase,
                message=str(spec.get("message", 'Passive voice: "{match}".')).format(match=match.group(0)),
                label="Consider naming who acted.",
                details={"excerpt": _excerpt(text, match), "phrase": phrase},
            )
        )
        if len(findings) >= limit:
            break
    return findings


def check_language(
    text,
    *,
    document_id=0,
    rules=None,
    include=("confused_words", "confusable_pairs", "grammar", "passive_voice"),
    accepted_passive=(),
):
    """Run the selected language checks. Each one is independently selectable."""
    rules = rules if rules is not None else _cached_rules()
    text = str(text or "")
    findings = []
    if "confused_words" in include:
        findings.extend(check_confused_words(text, rules, document_id))
    if "confusable_pairs" in include:
        findings.extend(check_confusable_pairs(text, rules, document_id))
    if "grammar" in include:
        findings.extend(check_grammar(text, rules, document_id))
    if "passive_voice" in include:
        findings.extend(check_passive_voice(text, rules, document_id, accepted_extra=accepted_passive))
    return sort_and_condense_findings(findings)

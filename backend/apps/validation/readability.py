"""Readability checking for letters written to clients.

Invoked deliberately -- from review, from a management command, or from the
advice-letter ingest -- rather than folded into generation. A letter is not
better because a number moved; the point is to show an advocate which sentences
a client is likely to stumble over.

No single formula is treated as authoritative. Grade-level scores count
syllables and sentence length and cannot tell whether a word is familiar, so
several run together and disagreement between them is surfaced rather than
averaged away. The organization's own concrete rules -- sentence length, jargon
substitutions, terms that must be defined -- carry more weight than any score,
because they were written by the people who answer the phone when a client does
not understand the letter.

Rules are file-backed in `content/drafting-rules/checks/plain-language.yaml` so
they can be changed without a deploy.
"""

from __future__ import annotations

import functools
import math
import re
from dataclasses import dataclass, field

import yaml

from apps.core.content_library import content_path


RULES_PATH = ("drafting-rules", "checks", "plain-language.yaml")

VOWELS = "aeiouy"
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")
WORD_RE = re.compile(r"[A-Za-z][A-Za-z'’-]*")
# "was granted", "will be removed", "were given" -- the checklist's own examples.
PASSIVE_RE = re.compile(
    r"\b(?:is|are|was|were|be|been|being|will be|has been|have been|had been)\s+"
    r"(?:\w+ly\s+)?(\w+(?:ed|en))\b",
    re.I,
)
# A binding or a bracketed marker is not prose the client will read.
TEMPLATE_TOKEN_RE = re.compile(r"\{\{.*?\}\}|\{%.*?%\}|\[[^\]]*\]|_{3,}")


def load_rules():
    """Read the plain-language rules, private library overriding public."""
    path = content_path(*RULES_PATH)
    if not path.is_file():
        return {}
    return yaml.safe_load(path.read_text()) or {}


@functools.lru_cache(maxsize=1)
def _cached_rules():
    return load_rules()


def count_syllables(word: str) -> int:
    """Approximate English syllables by counting vowel groups."""
    cleaned = re.sub(r"[^a-z]", "", word.lower())
    if not cleaned:
        return 0
    count = 0
    previous_vowel = False
    for character in cleaned:
        is_vowel = character in VOWELS
        if is_vowel and not previous_vowel:
            count += 1
        previous_vowel = is_vowel
    if cleaned.endswith("e") and count > 1:
        count -= 1
    return max(count, 1)


def strip_template_tokens(text: str) -> str:
    """Remove bindings and fill-in markers before scoring.

    An unrendered `{{ fields.plaintiff_name }}` is not something a client reads,
    and counting its syllables makes a letter look harder than it is.
    """
    return TEMPLATE_TOKEN_RE.sub(" ", text or "")


@dataclass
class Finding:
    rule: str
    severity: str
    message: str
    excerpt: str = ""

    def as_dict(self):
        return {
            "rule": self.rule,
            "severity": self.severity,
            "message": self.message,
            "excerpt": self.excerpt,
        }


@dataclass
class ReadabilityReport:
    metrics: dict = field(default_factory=dict)
    findings: list = field(default_factory=list)
    sentences: int = 0
    words: int = 0
    estimated_pages: float = 0.0

    @property
    def warnings(self):
        return [finding for finding in self.findings if finding.severity == "warning"]

    @property
    def passed(self):
        return not self.warnings

    def as_dict(self):
        return {
            "metrics": self.metrics,
            "findings": [finding.as_dict() for finding in self.findings],
            "sentences": self.sentences,
            "words": self.words,
            "estimatedPages": self.estimated_pages,
            "passed": self.passed,
        }


def _sentences_and_words(text):
    cleaned = strip_template_tokens(text)
    sentences = [
        sentence.strip()
        for sentence in SENTENCE_SPLIT_RE.split(cleaned)
        if len(WORD_RE.findall(sentence)) > 1
    ]
    words = WORD_RE.findall(cleaned)
    return sentences, words


def compute_metrics(text) -> dict:
    """Several formulas, reported side by side rather than reconciled."""
    sentences, words = _sentences_and_words(text)
    if not sentences or not words:
        return {}
    syllable_counts = [count_syllables(word) for word in words]
    total_syllables = sum(syllable_counts)
    polysyllables = sum(1 for count in syllable_counts if count >= 3)
    words_per_sentence = len(words) / len(sentences)
    syllables_per_word = total_syllables / len(words)

    metrics = {
        "flesch_kincaid_grade": round(
            0.39 * words_per_sentence + 11.8 * syllables_per_word - 15.59, 1
        ),
        "flesch_reading_ease": round(
            206.835 - 1.015 * words_per_sentence - 84.6 * syllables_per_word, 1
        ),
        # SMOG is defined over 30 sentences; scale when the passage is shorter.
        "smog_index": round(
            1.0430 * math.sqrt(polysyllables * (30 / len(sentences))) + 3.1291, 1
        ),
        "gunning_fog": round(
            0.4 * (words_per_sentence + 100 * (polysyllables / len(words))), 1
        ),
        "words_per_sentence": round(words_per_sentence, 1),
        "polysyllable_percent": round(100 * polysyllables / len(words), 1),
    }
    return metrics


def _check_metrics(metrics, rules, findings):
    for spec in rules.get("metrics", []) or []:
        value = metrics.get(spec.get("id"))
        if value is None:
            continue
        label = spec.get("label", spec.get("id"))
        severity = spec.get("severity", "warning")
        maximum, minimum = spec.get("target_max"), spec.get("target_min")
        if maximum is not None and value > maximum:
            findings.append(
                Finding(spec["id"], severity, f"{label} is {value}; target is at most {maximum}.")
            )
        if minimum is not None and value < minimum:
            findings.append(
                Finding(spec["id"], severity, f"{label} is {value}; target is at least {minimum}.")
            )


def _rule_specs(rules):
    raw = rules.get("rules") or []
    if isinstance(raw, dict):
        return raw
    merged = {}
    for entry in raw:
        if isinstance(entry, dict) and "id" in entry:
            merged.setdefault("checks", []).append(entry)
        elif isinstance(entry, dict):
            merged.update(entry)
    return merged


def _check_sentence_length(sentences, spec, findings):
    limit = spec.get("max_words", 14)
    for sentence in sentences:
        count = len(WORD_RE.findall(sentence))
        if count > limit:
            findings.append(
                Finding(
                    spec.get("id", "sentence_length"),
                    spec.get("severity", "warning"),
                    f"Sentence runs to {count} words; the limit is {limit}.",
                    sentence[:160],
                )
            )


def _check_polysyllables(sentences, words, spec, findings):
    if not sentences:
        return
    window = spec.get("window_sentences", 30)
    allowed_per_window = spec.get("max_per_sentences", 6)
    polysyllables = [word for word in words if count_syllables(word) >= 3]
    allowed = allowed_per_window * (len(sentences) / window)
    if len(polysyllables) > max(allowed, allowed_per_window * 0.5):
        findings.append(
            Finding(
                spec.get("id", "polysyllable_density"),
                spec.get("severity", "warning"),
                f"{len(polysyllables)} words of three or more syllables across "
                f"{len(sentences)} sentences; the guideline allows about {allowed:.0f}.",
                ", ".join(sorted({word.lower() for word in polysyllables})[:12]),
            )
        )


def _check_passive(sentences, spec, findings):
    for sentence in sentences:
        match = PASSIVE_RE.search(sentence)
        if match:
            findings.append(
                Finding(
                    spec.get("id", "passive_voice"),
                    spec.get("severity", "info"),
                    f'"{match.group(0)}" reads as passive. Name who acts.',
                    sentence[:160],
                )
            )


def _check_substitutions(text, substitutions, findings):
    lowered = text.lower()
    for entry in substitutions or []:
        term = str(entry.get("from", "")).lower()
        replacement = entry.get("to", "")
        if not term:
            continue
        if re.search(rf"\b{re.escape(term)}\b", lowered):
            findings.append(
                Finding(
                    "substitution",
                    "warning",
                    f'Use "{replacement}" instead of "{term}".',
                    term,
                )
            )


def _check_define_or_avoid(text, terms, findings):
    lowered = text.lower()
    for term in terms or []:
        term = str(term).lower()
        if not re.search(rf"\b{re.escape(term)}\b", lowered):
            continue
        # A term the letter explains in the same breath is fine; the working
        # group's own sections write 'seal (hide)' and '"vacate" (reverse)'.
        defined = re.search(
            rf"\b{re.escape(term)}\b[^.]{{0,40}}?[(“\"']", lowered
        ) or re.search(rf"[(“\"'][^.]{{0,40}}?\b{re.escape(term)}\b", lowered)
        if not defined:
            findings.append(
                Finding(
                    "define_or_avoid",
                    "info",
                    f'"{term}" is legal jargon. Avoid it, or define it where it first appears.',
                    term,
                )
            )


def check_readability(text, *, rules=None, kind="advice") -> ReadabilityReport:
    """Score a letter and list what a client is likely to stumble over."""
    rules = rules if rules is not None else _cached_rules()
    report = ReadabilityReport()
    sentences, words = _sentences_and_words(text or "")
    report.sentences, report.words = len(sentences), len(words)
    if not sentences:
        return report

    report.metrics = compute_metrics(text)
    _check_metrics(report.metrics, rules, report.findings)

    specs = _rule_specs(rules)
    for spec in specs.get("checks", []):
        kind_name = spec.get("kind")
        if kind_name == "sentence_length":
            _check_sentence_length(sentences, spec, report.findings)
        elif kind_name == "polysyllable_density":
            _check_polysyllables(sentences, words, spec, report.findings)
        elif kind_name == "passive_voice":
            _check_passive(sentences, spec, report.findings)

    _check_substitutions(strip_template_tokens(text), specs.get("substitutions"), report.findings)
    _check_define_or_avoid(strip_template_tokens(text), specs.get("define_or_avoid"), report.findings)

    length = rules.get("length") or {}
    per_page = length.get("words_per_page") or 450
    report.estimated_pages = round(len(words) / per_page, 2)
    limit_key = "advice_letter_max_pages" if kind == "advice" else "action_letter_max_pages"
    page_limit = length.get(limit_key)
    if page_limit and report.estimated_pages > page_limit:
        report.findings.append(
            Finding(
                "length",
                "warning",
                f"About {report.estimated_pages} pages; the target for a "
                f"{kind} letter is {page_limit}.",
            )
        )
    return report


def summarize(report: ReadabilityReport) -> str:
    """One line an advocate can read at a glance."""
    if not report.metrics:
        return "Not enough text to score."
    grade = report.metrics.get("flesch_kincaid_grade")
    smog = report.metrics.get("smog_index")
    warnings = len(report.warnings)
    return (
        f"Flesch-Kincaid {grade}, SMOG {smog}, "
        f"{report.sentences} sentences, {warnings} warning(s)."
    )

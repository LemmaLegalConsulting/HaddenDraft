"""Copy-editing text that came out of an unaccepted tracked-changes document.

Accepting an editor's marks reproduces exactly what they left behind, including
their mistakes. In the maintained security-deposit section the editor deleted
"returning some or all of" and inserted "all", so accepting yields "explain why
they're not all the deposit to you". The text is faithful and ungrammatical at
the same time.

So this module separates two jobs. Whitespace and punctuation damage is
mechanical and gets repaired: non-breaking spaces, doubled spaces, a space
before a comma, a missing space after one. Anything that needs judgment is
reported and left alone -- above all the sentences that sat on a merge boundary,
which are exactly where an editor's half-finished edit shows up.

Nothing here rewrites wording. A copy-edit that quietly changed the advice would
be worse than the artifact it fixed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


NBSP = " "

# Legal citations are full of internal periods; a space must not be inserted
# into "R.C. 5321.04" or "Civ.R. 5(B)". Matching happens on the token directly
# before a period, so "Civ.R." needs "Civ" here as well as the whole form --
# without the prefix the repair produced "Civ. R.".
ABBREVIATIONS = {
    "Civ", "Loc", "Sup", "Crim", "Evid", "Cod", "Admin", "Rev",
    "R.C", "Civ.R", "Loc.R", "Sup.R", "Crim.R", "Evid.R", "Cod.Ord", "Ord",
    "U.S", "U.S.C", "C.F.R", "No", "Nos", "Mr", "Mrs", "Ms", "Mx", "Dr",
    "St", "Ave", "Rd", "Apt", "Ste", "Inc", "LLC", "Co", "Dist", "App",
    "Jr", "Sr", "vs", "v", "etc", "e.g", "i.e", "a.m", "p.m", "Hous", "Metro",
    "Corp", "Mgmt", "Auth", "Div", "Cty", "Cuyahoga",
}

SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
DOUBLED_WORD_RE = re.compile(r"\b(\w+)(\s+)\1\b", re.I)
QUOTE_PAIRS = {"“": "”", "(": ")", "[": "]"}


@dataclass
class CopyEditResult:
    text: str = ""
    fixes: list = field(default_factory=list)
    flags: list = field(default_factory=list)

    @property
    def changed(self):
        return bool(self.fixes)

    def as_dict(self):
        return {"fixes": self.fixes, "flags": self.flags}


def _record(bucket, kind, before, after=""):
    entry = {"kind": kind, "excerpt": before[:120]}
    if after:
        entry["replacement"] = after[:120]
    bucket.append(entry)


def _fix_spacing(text, fixes):
    original = text

    if NBSP in text:
        text = text.replace(NBSP, " ")
        _record(fixes, "non_breaking_space", original)

    # A space before closing punctuation, or inside brackets.
    if re.search(r"\s+[,.;:!?](?!\S)", text) or re.search(r"\s+[,;:]", text):
        text = re.sub(r"[ \t]+([,.;:!?])", r"\1", text)
        _record(fixes, "space_before_punctuation", original)
    if re.search(r"\(\s+|\s+\)", text):
        text = re.sub(r"\(\s+", "(", text)
        text = re.sub(r"\s+\)", ")", text)
        _record(fixes, "space_inside_parentheses", original)

    # A missing space after a comma, semicolon, or colon.
    if re.search(r"[,;:](?=[A-Za-z])", text):
        text = re.sub(r"([,;:])(?=[A-Za-z])", r"\1 ", text)
        _record(fixes, "missing_space_after_punctuation", original)

    # A missing space after a sentence period, skipping legal abbreviations:
    # "R.C. 5321.04" and "Civ.R. 5(B)" must survive untouched.
    def space_after_period(match):
        head, following = match.group(1), match.group(2)
        word = head.rstrip(".").split()[-1] if head.strip(". ") else head
        if word in ABBREVIATIONS or len(word) <= 1:
            return match.group(0)
        return f"{head}. {following}"

    spaced = re.sub(r"([A-Za-z)\"'’”]+)\.([A-Z])", space_after_period, text)
    if spaced != text:
        text = spaced
        _record(fixes, "missing_space_after_period", original)

    if re.search(r"\S[ \t]{2,}\S", text):
        text = re.sub(r"(?<=\S)[ \t]{2,}(?=\S)", " ", text)
        _record(fixes, "double_space", original)

    stripped = text.strip()
    if stripped != text:
        text = stripped
        _record(fixes, "surrounding_whitespace", original)

    # Doubled punctuation left where a deletion met an insertion.
    collapsed = re.sub(r"([,;:])\1+", r"\1", text)
    collapsed = re.sub(r"(?<![.\w])\.{2}(?!\.)", ".", collapsed)
    if collapsed != text:
        text = collapsed
        _record(fixes, "doubled_punctuation", original)

    return text


LIST_MARKER_RE = re.compile(r"^\s*(?:[-•*]|\d+[.)])\s+")
# "1)" and "2)" in running prose are enumerations, not brackets. "(216)" and
# "(1)" are ordinary parentheses, so a digit-paren preceded by "(" is left alone.
ENUMERATION_RE = re.compile(r"(?<!\()\b\d+\)")


def _flag_suspicious(text, flags, *, touched_by_edit=False):
    if touched_by_edit:
        _record(flags, "merge_boundary", text)

    match = DOUBLED_WORD_RE.search(text)
    if match and match.group(1).lower() not in {"that", "had"}:
        _record(flags, "doubled_word", match.group(0))

    # Prose that stops without terminal punctuation usually lost it to a
    # deletion. A list item is supposed to stop that way, so only
    # sentence-shaped lines that are not list items are flagged.
    stripped = text.rstrip()
    if LIST_MARKER_RE.match(stripped):
        return
    body = stripped
    # A run-in heading carries no sentence punctuation at all; requiring a
    # period there would flag every section title.
    if "." not in body and len(body.split()) <= 12:
        return
    if (
        len(body.split()) >= 8
        and not body.endswith((".", "!", "?", ":", ";", "”", '"', ")"))
        and "{{" not in body[-30:]
        and "{%" not in body[-30:]
    ):
        _record(flags, "missing_terminal_punctuation", body)


def _flag_unbalanced(text, flags):
    """Check paired marks across the whole section, not line by line.

    A script the client reads aloud in court opens its quotation on one line and
    closes it four lines later. Checking each line alone reports both ends as
    broken.
    """
    cleaned = ENUMERATION_RE.sub("", text)
    for opener, closer in QUOTE_PAIRS.items():
        if cleaned.count(opener) != cleaned.count(closer):
            _record(flags, "unbalanced_marks", f"{opener} … {closer}")
    if cleaned.count('"') % 2:
        _record(flags, "unbalanced_marks", '"')


def copyedit_line(text, *, touched_by_edit=False) -> CopyEditResult:
    """Repair mechanical damage in one paragraph; report the rest."""
    result = CopyEditResult()
    if not text or not text.strip():
        result.text = text
        return result
    result.text = _fix_spacing(text, result.fixes)
    _flag_suspicious(result.text, result.flags, touched_by_edit=touched_by_edit)
    return result


def copyedit_lines(lines, *, touched=None) -> tuple[list[str], CopyEditResult]:
    """Copy-edit a section's paragraphs, keeping one combined report."""
    touched = touched or set()
    combined = CopyEditResult()
    output = []
    for index, line in enumerate(lines):
        result = copyedit_line(line, touched_by_edit=index in touched)
        output.append(result.text)
        combined.fixes.extend(result.fixes)
        combined.flags.extend(result.flags)
    combined.text = "\n".join(output)
    _flag_unbalanced(combined.text, combined.flags)
    return output, combined


def summarize(result: CopyEditResult) -> str:
    if not result.fixes and not result.flags:
        return "clean"
    parts = []
    if result.fixes:
        kinds = sorted({fix["kind"] for fix in result.fixes})
        parts.append(f"{len(result.fixes)} fix(es): {', '.join(kinds)}")
    if result.flags:
        kinds = sorted({flag["kind"] for flag in result.flags})
        parts.append(f"{len(result.flags)} to check: {', '.join(kinds)}")
    return "; ".join(parts)

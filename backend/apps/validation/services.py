"""Structured, rule-based draft validation.

Rule code ranges:
    E/W/I100-199: template data, unresolved placeholders, Jinja/render syntax
    E/W/I200-299: draft structure and selected block consistency
    E/W/I300-399: rendered DOCX consistency
    E/W/I400-499: citation linting
    E/W/I500-599: selected fact/source support
    E/W/I600-699: filing/jurisdiction/profile checks

This is intentionally a linter, not a full fact/claim graph or a legal-reasoning
engine: rules look at selected facts, selected sources, template blocks, and
rendered output as validation anchors, not an extracted claim/citation graph.
"""

import re

from jinja2 import TemplateSyntaxError

from apps.templates_app.template_variables import (
    LEGACY_LITERAL_FIELDS,
    extract_template_variables_from_text,
    template_field_label,
)
from apps.validation.findings import error_finding, sort_and_condense_findings, warning_finding
from apps.validation.rendered import extract_docx_text

try:
    import textstat
except ImportError:  # pragma: no cover - optional dependency
    textstat = None


CITATION_RE = re.compile(r"\b\d+\s+[A-Z][A-Za-z.]+\s+\d+\b")
SHORT_FORM_CITATION_RE = re.compile(r"\b(Id\.|Ibid\.|supra\b)", re.IGNORECASE)
JINJA_RE = re.compile(r"\{\{.*?\}\}|\{%.*?%\}", re.DOTALL)

FILING_PLACEHOLDER_RE = re.compile(
    r"\[(?:court|case number|court case number|plaintiff name|defendant name|insert\b[^\]\n]{0,80}"
    r"|describe\b[^\]\n]{0,80}|attorney review required[^\]\n]{0,80})\]",
    re.IGNORECASE,
)
GENERIC_PLACEHOLDER_RE = re.compile(r"\[[^\]\n]{2,80}\]")
NUMERIC_BRACKET_RE = re.compile(r"^\[\d[\d\s,.\-]*\]$")

DOLLAR_RE = re.compile(r"\$\s?\d[\d,]*(?:\.\d{2})?")
DATE_RE = re.compile(
    r"\b\d{1,2}/\d{1,2}/\d{2,4}\b"
    r"|\b(?:Jan\.?|Feb\.?|Mar\.?|Apr\.?|May|Jun\.?|Jul\.?|Aug\.?|Sep\.?|Sept\.?|Oct\.?|Nov\.?|Dec\.?"
    r"|January|February|March|April|June|July|August|September|October|November|December)"
    r"\s+\d{1,2},?\s+\d{2,4}\b",
    re.IGNORECASE,
)
HIGH_RISK_KEYWORDS = {
    "rent", "balance", "arrears", "hearing", "notice", "service", "served", "disability",
    "accommodation", "repair", "repairs", "condition", "address", "deadline",
}
CRITICAL_KEYWORDS = {"case number", "docket", "court", "deadline", "plaintiff", "defendant"}
CONCLUSION_CUES = ("should", "must", "therefore", "entitled", "warrants", "grant", "deny", "dismiss")

WORD_RE = re.compile(r"[A-Za-z0-9']+")


# --- snapshot -----------------------------------------------------------------


def build_validation_snapshot(draft, *, include_docx=True):
    snapshot = {
        "draftId": draft.id,
        "title": draft.title,
        "sections": draft.sections or [],
        "plainText": draft.plain_text or "",
        "editorState": draft.editor_state or {},
        "docxBytes": b"",
        "docxText": "",
        "docxParagraphs": [],
        "docxTables": [],
        "docxProfile": {},
        "docxRenderError": None,
    }
    if not include_docx:
        return snapshot
    try:
        from apps.exporting.services import render_docx_bytes

        docx_bytes = render_docx_bytes(draft)
        profile = extract_docx_text(docx_bytes)
        snapshot["docxBytes"] = docx_bytes
        snapshot["docxText"] = profile["text"]
        snapshot["docxParagraphs"] = profile["paragraphs"]
        snapshot["docxTables"] = profile["tables"]
        snapshot["docxProfile"] = profile
    except Exception as exc:  # noqa: BLE001 - rendering is a validation boundary, not internal logic
        snapshot["docxRenderError"] = str(exc)
    return snapshot


# --- shared helpers -------------------------------------------------------------


def _significant_words(text):
    return {word.casefold() for word in WORD_RE.findall(text or "") if len(word) > 3}


def _text_overlap_ratio(candidate, reference):
    candidate_words = _significant_words(candidate)
    if not candidate_words:
        return 1.0
    reference_words = _significant_words(reference)
    if not reference_words:
        return 0.0
    return len(candidate_words & reference_words) / len(candidate_words)


def _sentences(text):
    return [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", text or "") if sentence.strip()]


def _session_and_template(draft):
    session = getattr(draft, "session", None)
    template = getattr(session, "template", None) if session else None
    return session, template


def _section_block_type(draft, key):
    _, template = _session_and_template(draft)
    if not template:
        return ""
    block = next((block for block in template.blocks.all() if block.key == key), None)
    return block.block_type if block else ""


def _view_for(in_json, in_docx):
    if in_json and in_docx:
        return "both"
    return "docx" if in_docx else "json"


# --- 3.1 template data rules ------------------------------------------------


def validate_template_data(draft, snapshot):
    findings = []
    session, template = _session_and_template(draft)
    template_data = getattr(session, "template_data", {}) or {}
    declared_fields = list((getattr(template, "metadata", {}) or {}).get("fields", [])) if template else []
    if template:
        for block in template.blocks.all():
            try:
                paths = extract_template_variables_from_text(block.body or "")
            except TemplateSyntaxError:
                paths = []
            for path in paths:
                if str(path).startswith(("fields.", 'fields["')) and path not in declared_fields:
                    declared_fields.append(path)

    plain_text = snapshot["plainText"]
    docx_text = snapshot["docxText"]

    for path in declared_fields:
        value = str(path)
        bracketed = re.fullmatch(r'fields\["([^"]+)"\]', value)
        key = bracketed.group(1) if bracketed else value.removeprefix("fields.")
        if key in LEGACY_LITERAL_FIELDS or str(template_data.get(key, "")).strip():
            continue
        label = template_field_label(key)
        marker = f"[{label}]"
        in_json = marker.casefold() in plain_text.casefold()
        in_docx = marker.casefold() in docx_text.casefold()
        affects_output = in_json or in_docx
        builder = error_finding if affects_output else warning_finding
        rule_code = "E110" if affects_output else "W110"
        findings.append(
            builder(
                draft_id=draft.id,
                rule_code=rule_code,
                category="template",
                target=f"field:{key}",
                message=(
                    f"Template field '{label}' is missing template data and is still visible in the output."
                    if affects_output
                    else f"Template field '{label}' is missing template data."
                ),
                location={"view": _view_for(in_json, in_docx) if affects_output else "json", "excerpt": marker},
                action={
                    "type": "fill_template_field",
                    "label": "Fill the missing template field before regenerating the draft.",
                    "payload": {"field": key},
                },
            )
        )

    applicability = (getattr(template, "metadata", {}) or {}).get("applicability", {}) if template else {}
    required_template_data = applicability.get("requiredTemplateData", {})
    unmet_applicability = [
        key for key, expected in required_template_data.items() if template_data.get(key) != expected
    ]
    if unmet_applicability:
        findings.append(
            warning_finding(
                draft_id=draft.id,
                rule_code="W120",
                category="template",
                target="template:applicability",
                message="Confirm this template's threshold applicability requirements before drafting or filing.",
                location={"view": "json", "excerpt": ", ".join(unmet_applicability)},
                action={
                    "type": "confirm_template",
                    "label": "Confirm this template is appropriate for the matter before filing.",
                    "payload": {"fields": unmet_applicability},
                },
            )
        )

    json_jinja = JINJA_RE.findall(plain_text)
    if json_jinja:
        findings.append(
            error_finding(
                draft_id=draft.id,
                rule_code="E130",
                category="template",
                target="draft:jinja-syntax",
                message="The draft contains unresolved template syntax that must be fixed before filing.",
                location={"view": "json", "excerpt": json_jinja[0][:120]},
                action={
                    "type": "regenerate_block",
                    "label": "Regenerate the affected block after fixing template data.",
                    "payload": {"blockKey": _section_key_containing(snapshot["sections"], json_jinja[0])},
                },
            )
        )
    docx_jinja = JINJA_RE.findall(docx_text)
    if docx_jinja:
        findings.append(
            error_finding(
                draft_id=draft.id,
                rule_code="E131",
                category="template",
                target="docx:jinja-syntax",
                message="The rendered Word document still contains unresolved template syntax.",
                location={"view": "docx", "excerpt": docx_jinja[0][:120]},
                action={
                    "type": "inspect_docx_template",
                    "label": "Fix the Word template or block template that failed to render this field.",
                    "payload": {},
                },
            )
        )
    return findings


def _section_key_containing(sections, excerpt):
    for section in sections:
        if excerpt and excerpt in (section.get("body") or ""):
            return section.get("key", "")
    return ""


# --- 3.2 placeholder rules ---------------------------------------------------


def _placeholder_matches(text, pattern):
    return {match.group(0) for match in pattern.finditer(text or "")}


def validate_unresolved_placeholders(draft, snapshot):
    findings = []
    json_text = snapshot["plainText"]
    docx_text = snapshot["docxText"]

    json_filing = _placeholder_matches(json_text, FILING_PLACEHOLDER_RE)
    docx_filing = _placeholder_matches(docx_text, FILING_PLACEHOLDER_RE)
    for excerpt in sorted(json_filing | docx_filing):
        view = _view_for(excerpt in json_filing, excerpt in docx_filing)
        findings.append(
            error_finding(
                draft_id=draft.id,
                rule_code="E140",
                category="template",
                target=f"placeholder:{excerpt.casefold()}",
                message=f"The {'rendered Word document' if view == 'docx' else 'draft'} still contains the visible placeholder {excerpt}.",
                location={"view": view, "excerpt": excerpt},
                action={
                    "type": "fill_template_field",
                    "label": "Fill the missing field or regenerate the block before filing.",
                    "payload": {"placeholder": excerpt},
                },
            )
        )

    json_generic = _placeholder_matches(json_text, GENERIC_PLACEHOLDER_RE) - json_filing
    docx_generic = _placeholder_matches(docx_text, GENERIC_PLACEHOLDER_RE) - docx_filing
    for excerpt in sorted(json_generic | docx_generic):
        if NUMERIC_BRACKET_RE.match(excerpt) or CITATION_RE.search(excerpt):
            continue
        view = _view_for(excerpt in json_generic, excerpt in docx_generic)
        findings.append(
            warning_finding(
                draft_id=draft.id,
                rule_code="W141",
                category="template",
                target=f"placeholder:{excerpt.casefold()}",
                message=f"Ambiguous bracketed text {excerpt} may be an unresolved placeholder.",
                location={"view": view, "excerpt": excerpt},
                action={
                    "type": "human_review",
                    "label": "Confirm this bracketed text is intentional, or fill it in before filing.",
                    "payload": {},
                },
            )
        )
    return findings


# --- 3.3 structure rules ------------------------------------------------------


def validate_structure(draft, snapshot):
    findings = []
    session, template = _session_and_template(draft)
    sections = snapshot["sections"]
    section_keys = {section.get("key") for section in sections if section.get("key")}
    docx_rendered = bool(snapshot["docxBytes"]) and not snapshot["docxRenderError"]
    docx_text = snapshot["docxText"]

    if template:
        selected_keys = set(getattr(session, "selected_block_keys", []) or [])
        for block in template.blocks.all():
            if not (block.required or block.key in selected_keys):
                continue
            if block.key not in section_keys:
                findings.append(
                    error_finding(
                        draft_id=draft.id,
                        rule_code="E210",
                        category="structure",
                        target=f"block:{block.key}",
                        message=f"Required section '{block.label}' is missing from the draft.",
                        location={"view": "json", "blockKey": block.key, "sectionLabel": block.label},
                        action={
                            "type": "regenerate_document",
                            "label": "Regenerate the draft to include the missing required section.",
                            "payload": {"blockKey": block.key},
                        },
                    )
                )

    for section in sections:
        body = (section.get("body") or "").strip()
        key = section.get("key", "")
        label = section.get("label") or key
        if not body:
            findings.append(
                error_finding(
                    draft_id=draft.id,
                    rule_code="E211",
                    category="structure",
                    target=f"block:{key}",
                    message=f"Section '{label}' has an empty body.",
                    location={"view": "json", "blockKey": key, "sectionLabel": label},
                    action={
                        "type": "regenerate_block",
                        "label": "Regenerate this section.",
                        "payload": {"blockKey": key},
                    },
                )
            )
        elif (label or "").strip().casefold() in {"section", "untitled", "block", "text"}:
            findings.append(
                warning_finding(
                    draft_id=draft.id,
                    rule_code="W220",
                    category="structure",
                    target=f"block:{key}",
                    message=f"Section label '{label}' is too generic to identify in a filed document.",
                    location={"view": "json", "blockKey": key, "sectionLabel": label},
                    action={
                        "type": "human_review",
                        "label": "Give this section a more specific label.",
                        "payload": {"blockKey": key},
                    },
                )
            )

    if docx_rendered and not docx_text.strip() and (snapshot["plainText"].strip() or sections):
        findings.append(
            error_finding(
                draft_id=draft.id,
                rule_code="E212",
                category="structure",
                target="docx:empty",
                message="The rendered Word document is empty even though the draft has content.",
                location={"view": "docx"},
                action={
                    "type": "regenerate_document",
                    "label": "Regenerate the document; the Word export produced no visible content.",
                    "payload": {},
                },
            )
        )

    if template:
        selected_keys = set(getattr(session, "selected_block_keys", []) or [])
        for block in template.blocks.all():
            if block.required or block.key in selected_keys or block.key in section_keys:
                continue
            if block.block_type in {"signature", "certificate"}:
                findings.append(
                    warning_finding(
                        draft_id=draft.id,
                        rule_code="W230",
                        category="structure",
                        target=f"block:{block.key}",
                        message=f"'{block.label}' appears optional but is commonly expected before filing.",
                        location={"view": "json", "blockKey": block.key, "sectionLabel": block.label},
                        action={
                            "type": "confirm_template",
                            "label": "Confirm whether this section should be included before filing.",
                            "payload": {"blockKey": block.key},
                        },
                    )
                )
    return findings


# --- 3.4 rendered docx consistency rules -------------------------------------


def validate_rendered_docx_consistency(draft, snapshot):
    findings = []
    if snapshot["docxRenderError"] or not snapshot["docxBytes"]:
        return findings
    docx_text = snapshot["docxText"]
    plain_text = snapshot["plainText"]
    sections = snapshot["sections"]

    if plain_text.strip() and not docx_text.strip():
        findings.append(
            error_finding(
                draft_id=draft.id,
                rule_code="E310",
                category="rendered_docx",
                target="docx:empty-vs-json",
                message="The draft has content, but the rendered Word document has no visible text.",
                location={"view": "docx"},
                action={
                    "type": "regenerate_document",
                    "label": "Regenerate the document; the Word export produced no visible content.",
                    "payload": {},
                },
            )
        )
        return findings

    for section in sections:
        body = (section.get("body") or "").strip()
        key = section.get("key", "")
        label = section.get("label") or key
        if not body:
            continue
        overlap = _text_overlap_ratio(body, docx_text)
        if overlap >= 0.5:
            continue
        block_type = _section_block_type(draft, key)
        if overlap < 0.15 and block_type in {"caption", "signature", "relief"}:
            findings.append(
                error_finding(
                    draft_id=draft.id,
                    rule_code="E320",
                    category="rendered_docx",
                    target=f"block:{key}",
                    message=f"The required '{label}' section does not appear to survive Word rendering.",
                    location={"view": "docx", "blockKey": key, "sectionLabel": label},
                    action={
                        "type": "regenerate_block",
                        "label": "Regenerate this section and re-check the Word output.",
                        "payload": {"blockKey": key},
                    },
                )
            )
        elif overlap < 0.15:
            findings.append(
                warning_finding(
                    draft_id=draft.id,
                    rule_code="W320",
                    category="rendered_docx",
                    target=f"block:{key}",
                    message=f"Section '{label}' text does not closely match the rendered Word output.",
                    location={"view": "docx", "blockKey": key, "sectionLabel": label},
                    action={
                        "type": "human_review",
                        "label": "Review this section in the exported Word document.",
                        "payload": {"blockKey": key},
                    },
                )
            )
        else:
            findings.append(
                warning_finding(
                    draft_id=draft.id,
                    rule_code="W321",
                    category="rendered_docx",
                    target=f"block:{key}",
                    message=f"Section '{label}' differs noticeably from the rendered Word output but still appears usable.",
                    location={"view": "docx", "blockKey": key, "sectionLabel": label},
                    action={
                        "type": "human_review",
                        "label": "Confirm the exported Word text still reads correctly.",
                        "payload": {"blockKey": key},
                    },
                )
            )

    for marker in ("CASE CAPTION",):
        if marker in docx_text.upper() and marker.casefold() not in plain_text.casefold():
            findings.append(
                error_finding(
                    draft_id=draft.id,
                    rule_code="E330",
                    category="rendered_docx",
                    target="docx:editorial-label",
                    message=f"The rendered Word document still shows the editorial label '{marker}', which should have been replaced.",
                    location={"view": "docx", "excerpt": marker},
                    action={
                        "type": "inspect_docx_template",
                        "label": "Fix the Word template so this editorial label is replaced during export.",
                        "payload": {},
                    },
                )
            )
    return findings


# --- 3.5 citation linting -----------------------------------------------------


def _citations_expected(draft):
    _, template = _session_and_template(draft)
    if not template:
        return False
    metadata = template.metadata or {}
    if "citationsExpected" in metadata:
        return bool(metadata["citationsExpected"])
    return template.kind in {"motion", "brief"}


def validate_citations(draft, snapshot):
    findings = []
    text = f"{snapshot['plainText']}\n{snapshot['docxText']}"
    full_citations = list(CITATION_RE.finditer(text))

    if not full_citations:
        short_matches = list(SHORT_FORM_CITATION_RE.finditer(text))
        if short_matches:
            first = short_matches[0]
            findings.append(
                error_finding(
                    draft_id=draft.id,
                    rule_code="E420",
                    category="citations",
                    target="citation:dangling-short-form",
                    message=f"Short-form citation '{first.group(0)}' appears without a preceding full citation.",
                    location={"view": "json", "excerpt": text[max(0, first.start() - 40):first.end() + 40]},
                    action={
                        "type": "review_citation",
                        "label": "Add the full citation before this short-form reference, or remove it.",
                        "payload": {"citation": first.group(0)},
                    },
                )
            )
        elif _citations_expected(draft):
            session = getattr(draft, "session", None)
            selected_sources = getattr(session, "selected_source_results", []) or []
            has_legal_authority = any(source.get("purpose") == "legal_authority" for source in selected_sources)
            if has_legal_authority:
                findings.append(
                    warning_finding(
                        draft_id=draft.id,
                        rule_code="W430",
                        category="citations",
                        target="citation:none-detected",
                        message="Selected sources include legal authority, but no citations were detected in the draft.",
                        location={"view": "json"},
                        action={
                            "type": "review_citation",
                            "label": "Confirm citations to the selected legal authority are included.",
                            "payload": {},
                        },
                    )
                )
        return findings

    first_full_position = full_citations[0].start()
    for match in SHORT_FORM_CITATION_RE.finditer(text):
        if match.start() < first_full_position:
            findings.append(
                error_finding(
                    draft_id=draft.id,
                    rule_code="E420",
                    category="citations",
                    target="citation:dangling-short-form",
                    message=f"Short-form citation '{match.group(0)}' appears before any full citation.",
                    location={"view": "json", "excerpt": text[max(0, match.start() - 40):match.end() + 40]},
                    action={
                        "type": "review_citation",
                        "label": "Move or add the full citation before this short-form reference.",
                        "payload": {"citation": match.group(0)},
                    },
                )
            )
            break

    for match in full_citations:
        findings.append(
            warning_finding(
                draft_id=draft.id,
                rule_code="W440",
                category="citations",
                target=f"citation:{match.group(0)}",
                message=f"Citation '{match.group(0)}' was detected but cannot be validated automatically.",
                location={"view": "json", "excerpt": match.group(0)},
                action={
                    "type": "review_citation",
                    "label": "Review this citation and confirm it supports the statement.",
                    "payload": {"citation": match.group(0)},
                },
            )
        )

    if _citations_expected(draft):
        for sentence in _sentences(snapshot["plainText"]):
            casefolded = sentence.casefold()
            if not any(cue in casefolded for cue in CONCLUSION_CUES):
                continue
            if CITATION_RE.search(sentence) or SHORT_FORM_CITATION_RE.search(sentence):
                continue
            findings.append(
                warning_finding(
                    draft_id=draft.id,
                    rule_code="W441",
                    category="citations",
                    target=f"citation:conclusion:{sentence[:60]}",
                    message="This legal conclusion is not tied to a nearby citation.",
                    location={"view": "json", "excerpt": sentence[:200]},
                    action={
                        "type": "review_citation",
                        "label": "Add or confirm a supporting citation near this conclusion.",
                        "payload": {},
                    },
                )
            )
    return findings


# --- 3.6 selected fact/source support rules ----------------------------------


def validate_selected_fact_support(draft, snapshot):
    findings = []
    session = getattr(draft, "session", None)
    if not session:
        return findings

    from apps.matters.models import MatterFact

    selected_facts = list(MatterFact.objects.filter(id__in=session.selected_fact_ids or []))
    draft_words = _significant_words(f"{snapshot['plainText']}\n{snapshot['docxText']}")

    for fact in selected_facts:
        fact_words = _significant_words(fact.text)
        if not fact_words:
            continue
        overlap = len(fact_words & draft_words) / len(fact_words)
        if overlap < 0.2:
            findings.append(
                warning_finding(
                    draft_id=draft.id,
                    rule_code="W520",
                    category="fact_support",
                    target=f"fact:{fact.id}",
                    message=f"Selected fact '{fact.title}' does not appear reflected anywhere in the draft.",
                    location={"view": "json", "excerpt": fact.text[:160]},
                    action={
                        "type": "review_fact_support",
                        "label": "Confirm this selected fact should be added to the draft, or remove it from selection.",
                        "payload": {"factId": fact.id},
                    },
                )
            )

    support_text = " ".join(fact.text for fact in selected_facts)
    support_text += " " + " ".join(str(source.get("snippet") or "") for source in (session.selected_source_results or []))
    support_words = _significant_words(support_text)

    for sentence in _sentences(snapshot["plainText"]):
        casefolded = sentence.casefold()
        has_signal = bool(DOLLAR_RE.search(sentence)) or bool(DATE_RE.search(sentence)) or any(
            term in casefolded for term in HIGH_RISK_KEYWORDS
        )
        if not has_signal:
            continue
        sentence_words = _significant_words(sentence)
        if not sentence_words:
            continue
        overlap = len(sentence_words & support_words) / len(sentence_words)
        if overlap >= 0.3:
            continue
        is_critical = any(term in casefolded for term in CRITICAL_KEYWORDS)
        builder = error_finding if is_critical else warning_finding
        rule_code = "E530" if is_critical else "W530"
        findings.append(
            builder(
                draft_id=draft.id,
                rule_code=rule_code,
                category="fact_support",
                target=f"assertion:{sentence[:60]}",
                message="This factual statement does not appear supported by the selected facts or source snippets.",
                location={"view": "json", "excerpt": sentence[:200]},
                action={
                    "type": "review_fact_support",
                    "label": "Confirm this factual statement is supported by selected facts or source documents.",
                    "payload": {},
                },
            )
        )
    return findings


# --- 3.7 filing/profile rules -------------------------------------------------


def _readability_finding(draft, text):
    if textstat is None:
        return None
    word_count = len((text or "").split())
    if word_count < 75:
        return None
    lexicon_count = max(textstat.lexicon_count(text), 1)
    consensus_grade = float(textstat.text_standard(text, float_output=True))
    difficult_ratio = textstat.difficult_words(text) / lexicon_count
    if consensus_grade <= 16 and difficult_ratio <= 0.3:
        return None
    return warning_finding(
        draft_id=draft.id,
        rule_code="W615",
        category="filing",
        target="filing:readability",
        message=(
            f"Readability consensus grade is approximately {consensus_grade:.1f} with a "
            f"{difficult_ratio:.0%} difficult-word ratio, which may be hard for a lay reader."
        ),
        location={"view": "json"},
        action={
            "type": "human_review",
            "label": "Consider simplifying sentence structure and vocabulary for readability.",
            "payload": {},
        },
        details={"consensusGrade": consensus_grade, "difficultWordRatio": difficult_ratio},
    )


def validate_filing_profile(draft, snapshot):
    findings = []
    session, template = _session_and_template(draft)
    if not session:
        return findings
    matter = session.matter

    word_count = len((snapshot["docxText"] or snapshot["plainText"]).split())
    max_words = ((template.metadata or {}).get("maxWordCount") if template else None) or 6000
    if word_count > max_words:
        findings.append(
            warning_finding(
                draft_id=draft.id,
                rule_code="W610",
                category="filing",
                target="filing:word-count",
                message=f"The draft is {word_count} words, which may exceed a typical page/word budget.",
                location={"view": "both" if snapshot["docxText"] else "json"},
                action={
                    "type": "human_review",
                    "label": "Confirm the draft fits any applicable page or word limits.",
                    "payload": {},
                },
            )
        )

    readability = _readability_finding(draft, snapshot["plainText"])
    if readability:
        findings.append(readability)

    effective_jurisdiction = matter.jurisdiction or (template.jurisdiction if template else "")
    has_caption_marker = bool(template) and template.blocks.filter(label__istartswith="Case caption").exists()
    if not effective_jurisdiction.strip():
        findings.append(
            warning_finding(
                draft_id=draft.id,
                rule_code="W620",
                category="filing",
                target="filing:jurisdiction",
                message="Confirm the court and jurisdiction before filing.",
                location={"view": "json", "sectionLabel": "Caption"},
                action={
                    "type": "confirm_template",
                    "label": "Confirm the jurisdiction and court before filing.",
                    "payload": {},
                },
            )
        )
    elif has_caption_marker and "court" not in effective_jurisdiction.casefold():
        findings.append(
            warning_finding(
                draft_id=draft.id,
                rule_code="W621",
                category="filing",
                target="filing:court",
                message="Select the specific court before filing this captioned document.",
                location={"view": "json", "sectionLabel": "Caption"},
                action={
                    "type": "confirm_template",
                    "label": "Select the specific court before filing.",
                    "payload": {},
                },
            )
        )

    if has_caption_marker and not str((session.template_data or {}).get("court_case_number") or "").strip():
        findings.append(
            warning_finding(
                draft_id=draft.id,
                rule_code="W622",
                category="filing",
                target="filing:case-number",
                message="The case/docket number has not been entered for this captioned document.",
                location={"view": "json", "sectionLabel": "Caption"},
                action={
                    "type": "fill_template_field",
                    "label": "Enter the case or docket number before filing.",
                    "payload": {"field": "court_case_number"},
                },
            )
        )

    if template:
        selected_keys = set(session.selected_block_keys or [])
        section_keys = {section.get("key") for section in snapshot["sections"] or []}
        for block_type, label, rule_code in (
            ("signature", "signature block", "E630"),
            ("certificate", "certificate of service", "E631"),
        ):
            required = any(
                block.block_type == block_type and (block.required or block.key in selected_keys)
                for block in template.blocks.all()
            )
            present = any(_section_block_type(draft, key) == block_type for key in section_keys)
            if required and not present:
                findings.append(
                    error_finding(
                        draft_id=draft.id,
                        rule_code=rule_code,
                        category="filing",
                        target=f"filing:{block_type}",
                        message=f"A required {label} is missing from the draft.",
                        location={"view": "json", "sectionLabel": label.title()},
                        action={
                            "type": "regenerate_document",
                            "label": f"Regenerate the draft to include the required {label}.",
                            "payload": {},
                        },
                    )
                )
    return findings


# --- pipeline entry point -----------------------------------------------------


def validate_document(draft, *, include_docx=True):
    snapshot = build_validation_snapshot(draft, include_docx=include_docx)
    findings = []

    if snapshot["docxRenderError"]:
        findings.append(
            error_finding(
                draft_id=draft.id,
                rule_code="E300",
                category="rendered_docx",
                target="docx:render",
                message=f"Rendering the Word document failed: {snapshot['docxRenderError']}",
                location={"view": "docx", "excerpt": snapshot["docxRenderError"][:300]},
                action={
                    "type": "inspect_docx_template",
                    "label": "Fix the Word template or block template that failed during rendering.",
                    "payload": {},
                },
            )
        )

    findings.extend(validate_template_data(draft, snapshot))
    findings.extend(validate_unresolved_placeholders(draft, snapshot))
    findings.extend(validate_structure(draft, snapshot))
    findings.extend(validate_rendered_docx_consistency(draft, snapshot))
    findings.extend(validate_citations(draft, snapshot))
    findings.extend(validate_selected_fact_support(draft, snapshot))
    findings.extend(validate_filing_profile(draft, snapshot))

    return sort_and_condense_findings(findings)

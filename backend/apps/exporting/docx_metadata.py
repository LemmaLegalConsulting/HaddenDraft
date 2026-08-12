"""Attach auditable drafting metadata to an OOXML Word package."""

import io
import json
import zipfile
from xml.etree import ElementTree as ET

from apps.drafting.audit import ai_audit_counts


CUSTOM_PATH = "docProps/custom.xml"
CUSTOM_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.custom-properties+xml"
CUSTOM_REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/custom-properties"
CUSTOM_NS = "http://schemas.openxmlformats.org/officeDocument/2006/custom-properties"
VT_NS = "http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CONTENT_TYPES_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
FMTID = "{D5CDD505-2E9C-101B-9397-08002B2CF9AE}"
PROPERTY_PREFIX = "Legal Drafting Tool AI "

ET.register_namespace("", CUSTOM_NS)
ET.register_namespace("vt", VT_NS)


def _custom_properties(existing, audit):
    if existing:
        root = ET.fromstring(existing)
    else:
        root = ET.Element(f"{{{CUSTOM_NS}}}Properties")
    for child in list(root):
        if str(child.get("name") or "").startswith(PROPERTY_PREFIX):
            root.remove(child)
    pids = [int(child.get("pid", "1")) for child in root if child.get("pid", "").isdigit()]
    next_pid = max(pids, default=1) + 1
    counts = ai_audit_counts(audit)
    values = [
        ("Legal Drafting Tool AI Audit Schema", "1", "lpwstr"),
        ("Legal Drafting Tool AI Interaction Count", str(counts["interactions"]), "i4"),
        ("Legal Drafting Tool AI Paragraph Count", str(counts["paragraphs"]), "i4"),
        ("Legal Drafting Tool AI Source Count", str(counts["sources"]), "i4"),
        (
            "Legal Drafting Tool AI Audit JSON",
            # ASCII escaping keeps OCR/source text containing control or
            # malformed Unicode characters from making the OOXML part invalid;
            # JSON readers restore the original characters.
            json.dumps(audit, ensure_ascii=True, separators=(",", ":"), sort_keys=True),
            "lpwstr",
        ),
    ]
    for name, value, value_type in values:
        prop = ET.SubElement(
            root,
            f"{{{CUSTOM_NS}}}property",
            {"fmtid": FMTID, "pid": str(next_pid), "name": name},
        )
        ET.SubElement(prop, f"{{{VT_NS}}}{value_type}").text = value
        next_pid += 1
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _content_types(existing):
    root = ET.fromstring(existing)
    present = any(child.get("PartName") == f"/{CUSTOM_PATH}" for child in root)
    if not present:
        ET.SubElement(
            root,
            f"{{{CONTENT_TYPES_NS}}}Override",
            {"PartName": f"/{CUSTOM_PATH}", "ContentType": CUSTOM_CONTENT_TYPE},
        )
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _root_relationships(existing):
    root = ET.fromstring(existing)
    present = any(child.get("Type") == CUSTOM_REL_TYPE for child in root)
    if not present:
        used = {child.get("Id") for child in root}
        number = 1
        while f"rIdAIAudit{number}" in used:
            number += 1
        ET.SubElement(
            root,
            f"{{{REL_NS}}}Relationship",
            {"Id": f"rIdAIAudit{number}", "Type": CUSTOM_REL_TYPE, "Target": CUSTOM_PATH},
        )
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def embed_ai_audit_metadata(docx_bytes, audit):
    """Return ``docx_bytes`` with the audit payload in custom properties."""
    source = io.BytesIO(docx_bytes)
    output = io.BytesIO()
    with zipfile.ZipFile(source, "r") as incoming, zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as outgoing:
        names = set(incoming.namelist())
        custom = _custom_properties(incoming.read(CUSTOM_PATH) if CUSTOM_PATH in names else None, audit)
        replacements = {
            CUSTOM_PATH: custom,
            "[Content_Types].xml": _content_types(incoming.read("[Content_Types].xml")),
            "_rels/.rels": _root_relationships(incoming.read("_rels/.rels")),
        }
        for info in incoming.infolist():
            if info.filename not in replacements:
                outgoing.writestr(info, incoming.read(info.filename))
        for name, content in replacements.items():
            outgoing.writestr(name, content)
    return output.getvalue()

"""Deterministic, resumable template filling; isolated from drafting AI services."""
import copy
import hashlib
import io
import json
import re
import uuid
from types import SimpleNamespace

from django.utils import timezone
from docx import Document

from apps.core.storage import get_document_storage, RAW
from apps.drafting.components import record_sections
from apps.drafting.models import DraftDocument
from apps.exporting.services import _docx_render_context
from apps.exporting.docx_preview import docx_preview
from apps.exporting.template_fill import render_fill
from apps.matters.legalserver_delivery import save_document, delivery_to_dict
from apps.templates_app.fill_mappings import mapping_index, mapped_value, seed_mappings
from apps.templates_app.fill_paths import read_path, path_parts
from apps.templates_app.fill_templates import inspect_docx, library_docx, prepare_upload, template_sources
from apps.templates_app.models import FillTemplateUpload

DOCX_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def empty_value(value):
    return value is None or value == "" or (isinstance(value, str) and (value.startswith("[") and value.endswith("]") or value == "__________"))


def prepare_session(session, payload):
    upload = None
    if payload.get("uploadId"):
        upload = FillTemplateUpload.objects.get(pk=payload["uploadId"])
        if upload.prepared_key:
            with get_document_storage().open(upload.prepared_key) as stream:
                content = stream.read()
        else:
            with get_document_storage(RAW).open(upload.raw_key) as stream:
                content, report = prepare_upload(stream.read())
            upload.prepared_key = f"template-fill/uploads/{upload.pk}/{uuid.uuid4().hex}.docx"
            get_document_storage().put_bytes(key=upload.prepared_key, content=content, content_type=DOCX_TYPE)
            upload.report = report
            upload.save(update_fields=["prepared_key", "report"])
        title, slug = upload.title, upload.slug
    else:
        content = library_docx(session.template)
        title, slug = session.template.title, session.template.slug
    fields = inspect_docx(content)
    dummy = SimpleNamespace(session=session, template=session.template, title=title, sections=[], plain_text="")
    context = _docx_render_context(dummy, {})
    # Materialize the defaults as plain data. No lazy objects or runtime lookups
    # survive into a saved session or into the uploaded template's environment.
    context["fields"] = dict(context["fields"])
    seed_mappings()
    mappings = mapping_index(slug)
    choices = {choice["name"]: choice for choice in ((session.template.metadata or {}).get("choices", []) if session.template else (upload.report.get("choices", []) if upload else []))}
    for field in fields:
        parts = path_parts(field["path"])
        optional_block = None
        if session.template and parts[0] == "fill_options" and len(parts) == 2:
            optional_block = session.template.blocks.filter(key=parts[1], required=False).first()
        mapping = mappings.get(field["key"])
        field.update(value=None, source="", state="unanswered", reason="")
        if mapping:
            field["source"] = f"LegalServer: {mapping.source_path}"
            try:
                field["value"] = mapped_value(mapping, session.matter.raw_payload or {}, collection=field["kind"] == "json")
                field["state"] = "mapped"
            except ValueError as error:
                field["reason"] = str(error)
        else:
            try:
                value = read_path(context, field["path"])
                if not empty_value(value):
                    field.update(value=value, source="Case or author profile / template default", state="default")
            except ValueError:
                pass
        choice = choices.get(field["path"])
        if choice:
            field.update(choices=choice.get("options", []), required=False, label=choice.get("label", field["label"]))
            if field["value"] is None:
                field["value"] = choice.get("default") or next(iter(choice.get("options", [])), None)
        elif field["required"] and field["kind"] == "text":
            field["kind"] = "control"
        if optional_block:
            field.update(kind="boolean", label=f"Include {optional_block.label}", value=False,
                         state="default", source="Optional section: off until selected", required=False)
    if session.template:
        source = "\n".join(template_sources(content))
        for block in session.template.blocks.all():
            # A block the document never prints is not a field: text typed into
            # it would go nowhere, and the screen would say otherwise.
            if block.ai_latitude == "generate" and block_is_used(source, block.key):
                instructions = block.ai_instructions
                if isinstance(instructions, list):
                    instructions = " ".join(str(item) for item in instructions)
                fields.append({"key": f"manual:{block.key}", "path": "", "label": block.label,
                               "kind": "multiline", "blockKey": block.key, "value": None,
                               "state": "unanswered", "source": "", "required": False,
                               "reason": instructions or "Write this section manually, or leave a prompt in Word."})
    key = f"template-fill/sessions/{session.pk}/{uuid.uuid4().hex}.docx"
    get_document_storage().put_bytes(key=key, content=content, content_type=DOCX_TYPE)
    session.fill_state = {"title": title, "slug": slug, "templateKey": key,
                          "templateChecksum": hashlib.sha256(content).hexdigest(),
                          "matterPayloadChecksum": hashlib.sha256(json.dumps(session.matter.raw_payload, sort_keys=True).encode()).hexdigest(),
                          "matterUpdatedAt": session.matter.updated_at.isoformat(),
                          "uploadId": upload.pk if upload else None,
                          "preparationReport": upload.report if upload else {"ai": "No AI used"},
                          "preparedAt": timezone.now().isoformat(), "fields": fields,
                          "context": context, "answers": {}, "revision": 0}
    session.save(update_fields=["fill_state", "updated_at"])
    return {"sessionId": session.pk}


def save_answers(session, answers, revision):
    state = copy.deepcopy(session.fill_state)
    if not state:
        raise ValueError("Template preparation has not completed.")
    if revision != state["revision"]:
        raise ValueError("This session changed in another window. Reopen it before saving.")
    validate_answers(state, answers)
    state["answers"].update(answers)
    state["revision"] += 1
    session.fill_state = state
    session.save(update_fields=["fill_state", "updated_at"])


def validate_answers(state, answers):
    if not isinstance(answers, dict):
        raise ValueError("Answers must be an object keyed by template field.")
    if len(json.dumps(answers)) > 1024 * 1024:
        raise ValueError("Field answers exceed the 1 MB limit.")
    fields = {field["key"]: field for field in state["fields"]}
    for key, value in answers.items():
        if key not in fields:
            raise ValueError(f"Unknown template field: {key}")
        kind = fields[key]["kind"]
        if fields[key].get("choices") and value not in fields[key]["choices"]:
            raise ValueError(f"Choose one of the listed options for {fields[key]['label']}.")
        if kind == "boolean" and type(value) is not bool:
            raise ValueError(f"Choose whether to include {fields[key]['label']}.")
        if kind not in {"json", "control"} and not isinstance(value, (str, int, float, bool, type(None))):
            raise ValueError(f"Enter a text value for {fields[key]['label']}.")
        if kind == "json" and value not in (None, "") and not isinstance(value, (list, dict)):
            raise ValueError(f"Enter a JSON list or object for {fields[key]['label']}.")


def preview_session(session, answers):
    """Render the saved state plus unsaved answers for reading, not saving."""
    state = copy.deepcopy(session.fill_state)
    if not state:
        raise ValueError("Template preparation has not completed.")
    validate_answers(state, answers)
    state["answers"].update(answers)
    with get_document_storage().open(state["templateKey"]) as stream:
        content, marked, assumed = render_fill(stream.read(), state, preview=True)
    return {**docx_preview(content, marked), "assumedOff": assumed}


def session_payload(session):
    state = session.fill_state
    fields = copy.deepcopy(state.get("fields", []))
    for field in fields:
        if field["key"] in state.get("answers", {}):
            field.update(value=state["answers"][field["key"]], state="manual", source="Author entry")
    return {"id": session.pk, "title": state.get("title", "Preparing template"),
            "fields": fields, "revision": state.get("revision", 0),
            "preparedAt": state.get("preparedAt"), "preparationReport": state.get("preparationReport", {}), "ai": "No AI used"}


def export_session(job):
    session = job.session
    state = job.payload["state"]
    with get_document_storage().open(state["templateKey"]) as stream:
        content = render_fill(stream.read(), state)
    key = f"template-fill/exports/{session.pk}/{job.pk}.docx"
    get_document_storage().put_bytes(key=key, content=content, content_type=DOCX_TYPE)
    text = "\n".join(paragraph.text for paragraph in Document(io.BytesIO(content)).paragraphs)
    # Each export is an immutable version; editing answers never overwrites an
    # existing document or its component provenance.
    draft = DraftDocument.objects.create(session=session, template=session.template, title=state["title"], plain_text="")
    record_sections(draft, [{"key": "filled-template", "label": state["title"], "body": text,
                             "fillDocxKey": key, "fillRevision": state["revision"],
                             "fieldProvenance": session_payload_from_state(state), "ai": "No AI used"}], origin="human")
    filename = f"{state['slug']}-filled.docx"
    delivery = save_document(session.matter, user=job.created_by, filename=filename, content=content,
                             content_type=DOCX_TYPE, title=state["title"], origin="template_fill",
                             requested=job.payload["saveToLegalServer"], scope_key=f"template-fill:{session.pk}")
    return {"fileKey": key, "filename": filename, "draftId": draft.pk, "delivery": delivery_to_dict(delivery), "ai": "No AI used"}


def session_payload_from_state(state):
    return [{"path": field["path"], "source": "Author entry" if field["key"] in state["answers"] else field["source"],
             "value": state["answers"].get(field["key"], field.get("value"))} for field in state["fields"]]


def block_is_used(source, key):
    return re.search(r"blocks\s*(?:\[\s*[\"']" + re.escape(key) + r"[\"']\s*\]|\." + re.escape(key) + r"\b)", source) is not None

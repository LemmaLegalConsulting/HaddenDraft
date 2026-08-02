import tempfile
from pathlib import Path

from django import forms
from django.contrib import admin, messages
from django.utils import timezone
from django.utils.html import format_html

from apps.templates_app.letterhead_library import letterhead_path
from apps.templates_app.letterheads import (
    LETTERHEAD_VARIABLES,
    prepare_letterhead,
)
from apps.templates_app.models import (
    AdviceLetterSection,
    DocumentTemplate,
    Letterhead,
    TemplateBlock,
)


LETTERHEAD_HELP = """
<div style="max-width:52em;line-height:1.5">
<h2>Replacing the letterhead</h2>
<p>One letterhead serves every advocate. Upload an ordinary Word letterhead &mdash;
one advocate's copy is fine &mdash; and leave <b>Parameterize on save</b> checked.
The advocate's name, phone, fax, and email lines are replaced with variables that
are filled from each author's profile when a letter is drafted. The masthead
image, margins, page setup, and the continuation header are left untouched.</p>

<h3>What the file should contain</h3>
<ul>
  <li>The organization's masthead, exactly as it should print.</li>
  <li>A contact block with the advocate's name on its own line, followed by lines
      beginning <code>Phone:</code>, optionally <code>Fax:</code>, and the email
      address on its own line. This is what gets parameterized.</li>
  <li>Optionally a continuation header such as
      <code>Letter to ______, 1/1/2025, Page 1 of 2</code>. The blank becomes the
      letter subject and the date becomes the send date.</li>
</ul>

<h3>Variables available in the letterhead</h3>
<ul>%s</ul>

<p>After saving, check <b>Preparation report</b> to confirm each contact line was
found. If it reports that no contact block was found, the layout differs from the
expected one &mdash; edit the DOCX and type the variables in by hand, then upload
it again with <b>Parameterize on save</b> unchecked.</p>

<p>Values come from each advocate's author profile. An advocate with no fax number
gets no fax line at all rather than an empty label.</p>
</div>
""" % "".join(
    f"<li><code>{{{{ {name} }}}}</code> &mdash; {description}</li>"
    for name, description in LETTERHEAD_VARIABLES.items()
)


class TemplateBlockInline(admin.StackedInline):
    model = TemplateBlock
    extra = 0


@admin.register(DocumentTemplate)
class DocumentTemplateAdmin(admin.ModelAdmin):
    list_display = ("title", "kind", "jurisdiction", "source_kind", "is_active", "has_style_template", "created_from_example")
    list_filter = ("kind", "source_kind", "is_active", "created_from_example")
    search_fields = ("title", "description", "jurisdiction")
    prepopulated_fields = {"slug": ("title",)}
    inlines = [TemplateBlockInline]

    @admin.display(boolean=True, description="Style template")
    def has_style_template(self, obj):
        return bool(obj.style_template)


ADVICE_SECTION_HELP = """
<div style="max-width:52em;line-height:1.5">
<h2>Reviewing an advice-letter section</h2>
<p>Every section is loaded, including ones that were not finished in the source
documents, so an attorney can read them here instead of opening Word. The
<b>Needs attorney review</b> flag &mdash; not the absence of a row &mdash; is what marks
text nobody has checked. Flagged sections are still offered to advocates, with
the reason shown next to them.</p>

<h3>Why a section gets flagged</h3>
<ul>
  <li><b>Tracked changes accepted here.</b> The source still had unresolved
      edits. Accepting them is faithful, not corrective: where the editor
      deleted more than they replaced, the result can be ungrammatical.</li>
  <li><b>A passage sat on a merge boundary.</b> Exactly where a half-finished
      edit shows up. Read those sentences.</li>
  <li><b>Drafted here.</b> The maintained section stopped before giving any
      advice, so the text was written to finish it. It adds no citations, but
      nobody has confirmed the law.</li>
  <li><b>Reviewer comments dropped.</b> Someone left a question in the file.</li>
</ul>

<h3>When you have read it</h3>
<p>Edit the body if it needs it, clear <b>Needs attorney review</b>, and save.
Saving here sets <b>Is locally edited</b>, which stops a later
<code>ingest_advice_letters</code> from overwriting your text or undoing your
decision. Use the <b>Mark as reviewed</b> action to clear several at once.</p>

<h3>Editing in the content library instead</h3>
<p>These sections come from <code>advice-letters/catalog.yaml</code> in the private
content repository, with selection criteria in
<code>advice-letters/selection-hints.yaml</code>. Editing there and re-running
<code>ingest_advice_letters</code> is the right path for a change the whole
organization should keep &mdash; but it will not overwrite anything already edited
here.</p>
</div>
"""


@admin.register(AdviceLetterSection)
class AdviceLetterSectionAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "topic",
        "region",
        "role",
        "status",
        "needs_attorney_review",
        "word_count",
        "reading_grade",
        "reviewed_at",
    )
    list_filter = (
        "needs_attorney_review",
        "status",
        "role",
        "topic",
        "region",
        "letter_type",
        "is_active",
        "is_locally_edited",
    )
    search_fields = ("title", "slug", "body", "topic", "review_reason")
    ordering = ("-needs_attorney_review", "topic", "title")
    actions = ("mark_reviewed", "flag_for_review")
    readonly_fields = (
        "review_help",
        "why_flagged",
        "readability_summary",
        "copyedit_summary",
        "ingest_notes",
        "slug",
        "word_count",
        "content_path",
        "source_checksum",
        "last_synced_at",
        "is_locally_edited",
    )
    fieldsets = (
        ("How review works", {"fields": ("review_help",)}),
        ("Review", {
            "fields": (
                "needs_attorney_review",
                "why_flagged",
                "review_notes",
                "reviewed_by",
                "reviewed_at",
            )
        }),
        ("Section", {"fields": ("title", "slug", "body", "status", "is_active")}),
        ("Where it applies", {
            "fields": ("role", "topic", "letter_type", "region", "cleveland_specific", "order")
        }),
        ("Selection", {"fields": ("selection_hints", "fields", "variants", "slots")}),
        ("Checks", {"fields": ("readability_summary", "copyedit_summary", "ingest_notes")}),
        ("Provenance", {
            "fields": ("content_path", "source_kind", "source_checksum", "last_synced_at",
                       "is_locally_edited", "word_count")
        }),
    )

    @admin.display(description="How review works")
    def review_help(self, obj):
        return format_html(ADVICE_SECTION_HELP)

    @admin.display(description="Reading grade", ordering="word_count")
    def reading_grade(self, obj):
        return (obj.readability or {}).get("metrics", {}).get("flesch_kincaid_grade", "-")

    @admin.display(description="Why this is flagged")
    def why_flagged(self, obj):
        if not obj or not obj.needs_attorney_review:
            return "Not flagged."
        return format_html("<b>{}</b>", obj.review_reason or obj.get_status_display())

    @admin.display(description="Readability")
    def readability_summary(self, obj):
        metrics = (obj.readability or {}).get("metrics") or {}
        if not metrics:
            return "Not scored."
        warnings = (obj.readability or {}).get("warnings") or []
        return format_html(
            "Flesch-Kincaid {} &middot; SMOG {} &middot; {} plain-language warning(s)"
            "<ul>{}</ul>",
            metrics.get("flesch_kincaid_grade", "-"),
            metrics.get("smog_index", "-"),
            len(warnings),
            format_html("".join(f"<li>{warning.get('message', '')}</li>" for warning in warnings[:8])),
        )

    @admin.display(description="Copy-edit")
    def copyedit_summary(self, obj):
        report = obj.copyedit or {}
        fixes, flags = report.get("fixes") or [], report.get("flags") or []
        if not fixes and not flags:
            return "Clean."
        return format_html(
            "<p>{} fix(es) applied at ingest.</p><p><b>Read these:</b></p><ul>{}</ul>",
            len(fixes),
            format_html(
                "".join(
                    f"<li><code>{flag.get('kind','')}</code> {flag.get('excerpt','')[:160]}</li>"
                    for flag in flags[:12]
                )
            )
            or "<li>None</li>",
        )

    @admin.display(description="Ingest notes")
    def ingest_notes(self, obj):
        notes = obj.notes or []
        if not notes:
            return "None."
        return format_html("<ul>{}</ul>", format_html("".join(f"<li>{note}</li>" for note in notes)))

    def save_model(self, request, obj, form, change):
        if change and form.changed_data:
            # Anything touched here must survive the next ingest.
            obj.is_locally_edited = True
        if "needs_attorney_review" in getattr(form, "changed_data", []) and not obj.needs_attorney_review:
            obj.reviewed_at = timezone.now()
            obj.reviewed_by = obj.reviewed_by or request.user
        super().save_model(request, obj, form, change)

    @admin.action(description="Mark as reviewed (clears the flag)")
    def mark_reviewed(self, request, queryset):
        updated = queryset.update(
            needs_attorney_review=False,
            reviewed_at=timezone.now(),
            reviewed_by=request.user,
            is_locally_edited=True,
        )
        self.message_user(request, f"Marked {updated} section(s) reviewed.", messages.SUCCESS)

    @admin.action(description="Flag for attorney review")
    def flag_for_review(self, request, queryset):
        updated = queryset.update(
            needs_attorney_review=True, reviewed_at=None, is_locally_edited=True
        )
        self.message_user(request, f"Flagged {updated} section(s).", messages.WARNING)


class LetterheadForm(forms.ModelForm):
    parameterize = forms.BooleanField(
        required=False,
        initial=True,
        label="Parameterize on save",
        help_text=(
            "Replace the advocate contact lines in the uploaded file with template "
            "variables. Uncheck only if the file already contains them."
        ),
    )

    class Meta:
        model = Letterhead
        fields = "__all__"


@admin.register(Letterhead)
class LetterheadAdmin(admin.ModelAdmin):
    form = LetterheadForm
    list_display = ("title", "organization", "source_kind", "is_default", "is_active", "is_placeholder")
    list_filter = ("source_kind", "is_default", "is_active", "is_placeholder")
    search_fields = ("title", "organization", "slug")
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = ("setup_help", "preparation_summary", "variables", "source_checksum", "last_synced_at")
    fieldsets = (
        ("How this works", {"fields": ("setup_help",)}),
        (None, {"fields": ("title", "slug", "organization", "description")}),
        ("Document", {"fields": ("docx", "parameterize", "content_path", "source_kind")}),
        ("Use", {"fields": ("is_default", "is_active", "is_placeholder")}),
        ("Result", {"fields": ("preparation_summary", "variables", "source_checksum", "last_synced_at")}),
    )

    @admin.display(description="Setup")
    def setup_help(self, obj):
        return format_html(LETTERHEAD_HELP)

    @admin.display(description="Preparation report")
    def preparation_summary(self, obj):
        report = (obj.preparation_report or {}) if obj else {}
        if not report:
            return "Not parameterized yet."
        replaced = report.get("replaced") or []
        warnings = report.get("warnings") or []
        return format_html(
            "<div><b>Replaced {} line(s):</b><ul>{}</ul>{}</div>",
            len(replaced),
            format_html("".join(f"<li>{item}</li>" for item in replaced)) or "",
            format_html(
                '<p style="color:#b00">{}</p>', " ".join(warnings)
            )
            if warnings
            else "",
        )

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if not form.cleaned_data.get("parameterize") or not obj.docx:
            return
        path = letterhead_path(obj)
        if not path or not path.is_file():
            return
        with tempfile.TemporaryDirectory() as work:
            output = Path(work) / path.name
            try:
                report = prepare_letterhead(path, output)
            except Exception as error:  # noqa: BLE001 - surfaced to the admin user
                self.message_user(
                    request, f"Could not parameterize the letterhead: {error}", messages.ERROR
                )
                return
            path.write_bytes(output.read_bytes())
        obj.variables = report.variables
        obj.preparation_report = {"replaced": report.replaced, "warnings": report.warnings}
        obj.save(update_fields=["variables", "preparation_report", "updated_at"])
        if report.warnings:
            self.message_user(request, " ".join(report.warnings), messages.WARNING)
        else:
            self.message_user(
                request,
                f"Parameterized {len(report.replaced)} contact line(s) in the letterhead.",
                messages.SUCCESS,
            )


@admin.register(TemplateBlock)
class TemplateBlockAdmin(admin.ModelAdmin):
    list_display = ("label", "template", "block_type", "order", "required", "editable", "ai_latitude", "has_docx_template")
    list_filter = ("block_type", "required", "editable", "ai_latitude", "ai_fill_mode")
    search_fields = ("label", "body")

    @admin.display(boolean=True, description="DOCX template")
    def has_docx_template(self, obj):
        return bool(obj.docx_template)

import tempfile
from pathlib import Path

from django import forms
from django.contrib import admin, messages
from django.utils.html import format_html

from apps.templates_app.letterhead_library import letterhead_path
from apps.templates_app.letterheads import (
    LETTERHEAD_VARIABLES,
    prepare_letterhead,
)
from apps.templates_app.models import DocumentTemplate, Letterhead, TemplateBlock


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

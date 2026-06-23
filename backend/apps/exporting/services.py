from django.http import HttpResponse


def export_plain_text(draft):
    response = HttpResponse(draft.plain_text, content_type="text/plain; charset=utf-8")
    filename = f"draft-{draft.id}.txt"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response

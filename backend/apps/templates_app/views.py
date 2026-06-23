from django.http import JsonResponse

from apps.core.http import api_login_required, json_body, method_not_allowed
from apps.templates_app.models import DocumentTemplate
from apps.templates_app.seed import seed_templates
from apps.templates_app.serializers import template_to_dict
from apps.templates_app.services import build_template_from_example


@api_login_required
def templates(request):
    seed_templates()
    if request.method != "GET":
        return method_not_allowed(["GET"])
    queryset = DocumentTemplate.objects.prefetch_related("blocks")
    return JsonResponse({"templates": [template_to_dict(template, include_blocks=True) for template in queryset]})


@api_login_required
def template_from_example(request):
    if request.method != "POST":
        return method_not_allowed(["POST"])
    body = json_body(request)
    template = build_template_from_example(
        title=body.get("title") or "Example-derived template",
        example_text=body.get("exampleText") or "",
        jurisdiction=body.get("jurisdiction") or "",
    )
    return JsonResponse({"template": template_to_dict(template, include_blocks=True)}, status=201)

from django.contrib import admin
from django.conf import settings
from django.urls import path

from apps.core import views as core_views
from apps.drafting import views as drafting_views
from apps.matters import views as matter_views
from apps.rules import views as rule_views
from apps.sources import views as source_views
from apps.templates_app import views as template_views


admin.site.site_url = settings.FRONTEND_SITE_URL

urlpatterns = [
    path("favicon.ico", core_views.favicon, name="favicon"),
    path("admin/", admin.site.urls),
    path("api/bootstrap/", core_views.bootstrap, name="api_bootstrap"),
    path("api/auth/me/", core_views.me, name="api_auth_me"),
    path("api/author-profile/", core_views.author_profile, name="api_author_profile"),
    path("api/auth/login/", core_views.login_view, name="api_auth_login"),
    path("api/auth/logout/", core_views.logout_view, name="api_auth_logout"),
    path("api/auth/office365/start/", core_views.office365_start, name="api_auth_office365_start"),
    path("api/auth/office365/callback/", core_views.office365_callback, name="api_auth_office365_callback"),
    path("api/modes/", core_views.modes, name="api_modes"),
    path("api/cases/", matter_views.cases, name="api_cases"),
    path("api/legalserver/account/", matter_views.legalserver_account, name="api_legalserver_account"),
    path("api/cases/<str:matter_id>/chat/", matter_views.case_chat, name="api_case_chat"),
    path("api/cases/<str:matter_id>/facts/", matter_views.case_facts, name="api_case_facts"),
    path("api/cases/<str:matter_id>/facts/recommend/", matter_views.case_fact_recommendations, name="api_case_fact_recommendations"),
    path("api/cases/<str:matter_id>/documents/", matter_views.case_documents, name="api_case_documents"),
    path("api/cases/<str:matter_id>/documents/<str:document_id>/context/", matter_views.case_document_context, name="api_case_document_context"),
    path("api/cases/<str:matter_id>/candidate-issues/", rule_views.case_candidate_issues, name="api_case_candidate_issues"),
    path("api/cases/<str:matter_id>/run-issue-selection/", rule_views.run_case_issue_selection, name="api_run_issue_selection"),
    path("api/cases/<str:matter_id>/", matter_views.case_detail, name="api_case_detail"),
    path("api/candidate-issues/<int:issue_id>/review/", rule_views.candidate_issue_review, name="api_candidate_issue_review"),
    path("api/sources/", source_views.sources, name="api_sources"),
    path("api/research/", source_views.research, name="api_research"),
    path("api/templates/", template_views.templates, name="api_templates"),
    path("api/templates/from-example/", template_views.template_from_example, name="api_template_from_example"),
    path("api/drafting-sessions/", drafting_views.sessions, name="api_sessions"),
    path("api/drafting-sessions/<int:session_id>/", drafting_views.session_detail, name="api_session_detail"),
    path("api/drafting-sessions/<int:session_id>/advance/", drafting_views.advance_session, name="api_session_advance"),
    path("api/drafting-sessions/<int:session_id>/draft/", drafting_views.generate_draft, name="api_generate_draft"),
    path("api/drafts/<int:draft_id>/", drafting_views.draft_detail, name="api_draft_detail"),
    path("api/drafts/<int:draft_id>/blocks/<slug:block_key>/regenerate/", drafting_views.regenerate_block, name="api_regenerate_block"),
    path("api/drafts/<int:draft_id>/validate/", drafting_views.validate_draft, name="api_validate_draft"),
    path("api/drafts/<int:draft_id>/export/", drafting_views.export_draft, name="api_export_draft"),
]

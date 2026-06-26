from apps.sources.connectors.base import SourceConnector, SourceResult
from apps.sources.models import UserResource


def _matches(resource, terms):
    if not terms:
        return True
    haystack = f"{resource.title}\n{resource.original_filename}\n{resource.text}".casefold()
    return all(term in haystack for term in terms)


def _snippet(text, terms, length=320):
    compact = " ".join((text or "").split())
    if not compact:
        return ""
    lowered = compact.casefold()
    first = min((lowered.find(term) for term in terms if term and lowered.find(term) >= 0), default=0)
    start = max(0, first - 80)
    end = min(len(compact), start + length)
    prefix = "... " if start else ""
    suffix = " ..." if end < len(compact) else ""
    return f"{prefix}{compact[start:end]}{suffix}"


class UserResourceConnector(SourceConnector):
    kind = "user_resources"
    label = "User resources"
    status = "Available"
    detail = "Private uploaded cases, example briefs, and user-specific reference materials"

    def search(self, query, *, matter=None, jurisdiction="", limit=5, user=None, request=None):
        if not user or not getattr(user, "is_authenticated", False):
            return []
        terms = [term for term in (query or "").casefold().split() if len(term) > 2]
        resources = UserResource.objects.filter(user=user)
        matches = [resource for resource in resources if _matches(resource, terms)]
        return [
            SourceResult(
                id=f"user-resource:{resource.id}",
                title=resource.title,
                snippet=_snippet(resource.text, terms),
                source_kind=self.kind,
                source_label="Private reference",
                citation=resource.title,
                metadata={
                    "resourceId": resource.id,
                    "resourceType": resource.resource_type,
                    "filename": resource.original_filename,
                    "private": True,
                },
            )
            for resource in matches[:limit]
        ]

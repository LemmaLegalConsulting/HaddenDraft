from dataclasses import dataclass, field


@dataclass
class SourceResult:
    id: str
    title: str
    snippet: str
    source_kind: str
    source_label: str
    citation: str = ""
    url: str = ""
    metadata: dict = field(default_factory=dict)

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "snippet": self.snippet,
            "sourceKind": self.source_kind,
            "sourceLabel": self.source_label,
            "citation": self.citation,
            "url": self.url,
            "metadata": self.metadata,
        }


class SourceConnector:
    kind = "base"
    label = "Base source"
    status = "Not configured"
    detail = ""

    def metadata(self):
        return {
            "kind": self.kind,
            "label": self.label,
            "status": self.status,
            "detail": self.detail,
        }

    def search(self, query, *, matter=None, jurisdiction="", limit=5, user=None, request=None):
        raise NotImplementedError

from apps.sources.connectors.base import SourceConnector, SourceResult


class LocalCaseIndexConnector(SourceConnector):
    kind = "local_cases"
    label = "Local archived cases"
    status = "Indexed"
    detail = "Locally archived municipal and trial court decisions"

    def search(self, query, *, matter=None, jurisdiction="", limit=5, user=None, request=None):
        return [
            SourceResult(
                id="local:cleveland-repair-ledger",
                title="Repair conditions and disputed ledger order",
                snippet="Local archived order addressing repair evidence alongside a disputed rent ledger in an eviction case.",
                source_kind=self.kind,
                source_label="Local case index",
                citation="Cleveland M.C. Housing Div. archived order",
                metadata={"court": jurisdiction or "Cleveland Municipal Court - Housing Division"},
            )
        ][:limit]

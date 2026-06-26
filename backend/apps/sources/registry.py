from apps.sources.connectors.legalserver import LegalServerConnector
from apps.sources.connectors.local_cases import LocalCaseIndexConnector
from apps.sources.connectors.rag import RagDatabaseConnector
from apps.sources.connectors.sharepoint import SharePointConnector
from apps.sources.connectors.user_resources import UserResourceConnector


class ConnectorRegistry:
    def __init__(self):
        self._connectors = {}

    def register(self, connector):
        self._connectors[connector.kind] = connector

    def all(self):
        return list(self._connectors.values())

    def get(self, kind):
        return self._connectors[kind]

    def search(self, query, *, kinds=None, source_ids=None, matter=None, jurisdiction="", limit_per_source=5, user=None, request=None):
        selected = self.all() if not kinds else [self.get(kind) for kind in kinds if kind in self._connectors]
        results = []
        for connector in selected:
            # A single connector can expose several logical libraries.  Keep the
            # picker selection intact instead of treating every RAG library alike.
            source_kwargs = {"source_ids": source_ids} if connector.kind == "rag" else {}
            results.extend(
                connector.search(
                    query,
                    matter=matter,
                    jurisdiction=jurisdiction,
                    limit=limit_per_source,
                    user=user,
                    request=request,
                    **source_kwargs,
                )
            )
        return results


connector_registry = ConnectorRegistry()
connector_registry.register(LegalServerConnector())
connector_registry.register(SharePointConnector())
connector_registry.register(RagDatabaseConnector())
connector_registry.register(LocalCaseIndexConnector())
connector_registry.register(UserResourceConnector())

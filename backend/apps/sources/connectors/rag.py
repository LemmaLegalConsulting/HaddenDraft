from apps.sources.connectors.base import SourceConnector, SourceResult


class RagDatabaseConnector(SourceConnector):
    kind = "rag"
    label = "RAG database"
    status = "Indexed"
    detail = "Specified treatise, rules, memos, and training content"

    def search(self, query, *, matter=None, jurisdiction="", limit=5, user=None, request=None):
        return [
            SourceResult(
                id="rag:habitability-elements",
                title="Habitability defense elements",
                snippet="Element outline: condition existed, landlord had notice, condition affected use and enjoyment, tenant preserved rights.",
                source_kind=self.kind,
                source_label="Structured knowledge base",
                citation="Internal treatise: Habitability",
                metadata={"query": query, "kind": "element_outline"},
            ),
            SourceResult(
                id="rag:continuance-standard",
                title="Continuance considerations",
                snippet="Continuance requests should connect specific missing evidence or pending rental assistance to the requested hearing delay.",
                source_kind=self.kind,
                source_label="Structured knowledge base",
                citation="Internal memo: Emergency Rental Assistance",
                metadata={"query": query, "kind": "legal_standard"},
            ),
        ][:limit]

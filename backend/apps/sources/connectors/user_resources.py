from apps.sources.connectors.base import SourceConnector, SourceResult


class UserResourceConnector(SourceConnector):
    kind = "user_resources"
    label = "User resources"
    status = "Available"
    detail = "Uploaded materials and user-specific saved resources"

    def search(self, query, *, matter=None, jurisdiction="", limit=5, user=None, request=None):
        return [
            SourceResult(
                id="user:uploaded-confirmation",
                title="Uploaded rental assistance confirmation",
                snippet="User-uploaded confirmation showing rental assistance application is pending.",
                source_kind=self.kind,
                source_label="User upload",
                citation="Rental assistance confirmation",
                metadata={"matter": matter.external_id if matter else ""},
            )
        ][:limit]

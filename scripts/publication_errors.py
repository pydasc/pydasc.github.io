"""Shared fail-closed publication exceptions."""


class CollectionError(ValueError):
    pass


class UnapprovedPublicationError(CollectionError):
    """A structurally valid source contract is not approved for publication."""

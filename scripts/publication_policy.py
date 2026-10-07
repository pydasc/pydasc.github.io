"""Shared publication identities, provenance records and controlled errors.

These types describe the existing manifest/inventory contract; validation stays
at the input boundary. This module performs no filesystem or Git operations.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import TypedDict

__all__ = [
    "CollectionError",
    "UnapprovedPublicationError",
    "Entry",
    "InventoryRecord",
    "EXPECTED",
    "SHA_RE",
    "SPDX_RE",
    "DOCUMENTATION_STATUSES",
    "UNSAFE_ATTRIBUTION_RE",
]

EXPECTED = {
    "pydasc": "https://github.com/pydasc/pydasc",
    "dasc": "https://github.com/pydasc/dasc",
}

SHA_RE = re.compile(r"^[0-9a-f]{40}$")

SPDX_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.+-]*$")

DOCUMENTATION_STATUSES = {
    "Draft",
    "Reviewed",
    "Reference",
    "Validated",
    "Unvalidated",
    "Superseded",
    "Released",
}

UNSAFE_ATTRIBUTION_RE = re.compile(r"(?:[\x00-\x1f<>\[\]]|--)")


class CollectionError(ValueError):
    pass


class UnapprovedPublicationError(CollectionError):
    """A structurally valid source contract is not approved for publication."""


@dataclass(frozen=True)
class Entry:
    source_name: str
    repository: str
    checkout_commit: str
    content_commit: str
    source: PurePosixPath
    destination: PurePosixPath
    status: str
    license_id: str
    attribution: str


class InventoryRecord(TypedDict):
    """Serialized provenance and checksum for one generated document.

    A type annotation only: consumers must validate untrusted decoded values.
    """

    destination: str
    sha256: str
    repository: str
    source: str
    commit: str
    status: str
    license: str
    attribution: str

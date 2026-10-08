"""Distinct syntax selections, checked approvals and serialized output records."""

from dataclasses import dataclass, asdict
from pathlib import PurePosixPath
from urllib.parse import quote
import hashlib
from publication_errors import CollectionError


@dataclass(frozen=True)
class SelectedEntry:
    source_name: str
    repository: str
    checkout_commit: str
    source: PurePosixPath
    destination: PurePosixPath


@dataclass(frozen=True)
class ApprovedEntry(SelectedEntry):
    content_commit: str
    status: str
    license_id: str
    attribution: str


@dataclass(frozen=True)
class SourceLock:
    name: str
    repository: str
    checkout_commit: str
    publication_manifest: PurePosixPath
    selections: tuple[SelectedEntry, ...]


@dataclass(frozen=True)
class ApprovedFile:
    destination: PurePosixPath
    status: str
    license_id: str
    attribution: str


@dataclass(frozen=True)
class InventoryRecord:
    destination: str
    sha256: str
    repository: str
    source: str
    commit: str
    status: str
    license: str
    attribution: str

    @classmethod
    def from_approved(cls, entry: ApprovedEntry, data: bytes):
        if not isinstance(entry, ApprovedEntry):
            raise CollectionError("output requires an approved entry")
        return cls(
            entry.destination.as_posix(),
            hashlib.sha256(data).hexdigest(),
            entry.repository,
            entry.source.as_posix(),
            entry.content_commit,
            entry.status,
            entry.license_id,
            entry.attribution,
        )

    def mapping(self) -> dict[str, str]:
        return asdict(self)


def provenance_banner(record) -> str:
    source = quote(record["source"], safe="/")
    url = f"{record['repository']}/blob/{record['commit']}/{source}"
    return (
        f"<!-- Generated; source={url}; status={record['status']}; "
        f"license={record['license']}; attribution={record['attribution']}; do not edit. -->\n"
    )

"""Website selection parsing and immutable upstream approval are separate stages."""

from pathlib import Path, PurePosixPath
from typing import Any
from publication_errors import CollectionError, UnapprovedPublicationError
from publication_policy import (
    EXPECTED,
    LEGACY_CONTRACT_REPOSITORIES,
    SHA_RE,
    ALLOWED,
    MEDIA,
    DOCUMENTATION_STATUSES,
    SPDX_RE,
    UNSAFE_ATTRIBUTION_RE,
)
from safe_files import (
    relative_path as _path,
    inside as _inside,
    read_regular_file as _read_regular_file,
)
from structured_input import (
    require_mapping as _mapping,
    read_yaml as _read_yaml,
    read_json as _read_json,
)
from git_inspection import inspect_git as _git, object_kind as _git_object_kind
from publication_models import SourceLock, SelectedEntry, ApprovedEntry, ApprovedFile


def _source_contract(
    path: Path,
    name: str,
    repository: str,
    checkout: str,
    raw_contract: bytes | None = None,
) -> tuple[str, dict[str, ApprovedFile]]:
    context = f"{name} publication manifest"
    raw = _read_json(
        raw_contract if raw_contract is not None else _read_regular_file(path, context),
        context,
    )
    root_keys = {"schema_version", "project", "repository", "source_commit", "files"}
    if name == "dasc":
        root_keys.add("publication_decision")
    root = _mapping(raw, root_keys, f"{name} publication manifest")
    accepted_repository = isinstance(root["repository"], str) and root["repository"] in {
        repository,
        LEGACY_CONTRACT_REPOSITORIES[name],
    }
    if (
        type(root["schema_version"]) is not int
        or root["schema_version"] != 1
        or root["project"] != name
        or not accepted_repository
    ):
        raise CollectionError(f"invalid {name} publication identity/schema")
    content = root["source_commit"]
    if not isinstance(content, str) or not SHA_RE.fullmatch(content):
        raise CollectionError(f"invalid {name} source_commit")
    if name == "dasc":
        decision = _mapping(
            root["publication_decision"], {"state", "reason", "evidence"}, "dasc decision"
        )
        if not isinstance(decision["state"], str) or not decision["state"].strip():
            raise CollectionError("invalid DASC publication decision state")
        if decision["state"] != "approved":
            raise UnapprovedPublicationError("DASC publication decision is not approved")
        if any(
            not isinstance(decision[field], str) or not decision[field].strip()
            for field in ("reason", "evidence")
        ):
            raise CollectionError("invalid DASC publication decision evidence")
    if _git(path.parent, "rev-parse", "HEAD").strip() != checkout:
        raise CollectionError(f"{name} checkout commit mismatch")
    approved: dict[str, ApprovedFile] = {}
    approved_sources: set[str] = set()
    approved_destinations: set[str] = set()
    if not isinstance(root["files"], list):
        raise CollectionError(f"{name} files must be a list")
    for index, item in enumerate(root["files"]):
        item = _mapping(
            item,
            {"source", "destination", "media_type", "documentation_status", "redistribution"},
            f"{name}.files[{index}]",
        )
        source = _path(item["source"], "source")
        destination = _path(item["destination"], "destination")
        if (
            destination.parts[0] != name
            or source.suffix.lower() not in ALLOWED
            or item["media_type"] != MEDIA[source.suffix.lower()]
        ):
            raise CollectionError(f"invalid approved file: {source}")
        folded_source = source.as_posix().casefold()
        folded_destination = destination.as_posix().casefold()
        if folded_source in approved_sources:
            raise CollectionError(f"duplicate approved source: {source}")
        if folded_destination in approved_destinations:
            raise CollectionError(f"duplicate approved destination: {destination}")
        approved_sources.add(folded_source)
        approved_destinations.add(folded_destination)
        status = _mapping(item["documentation_status"], {"label", "evidence"}, "status")
        if (
            not isinstance(status["label"], str)
            or status["label"] not in DOCUMENTATION_STATUSES
            or not isinstance(status["evidence"], str)
            or not status["evidence"].strip()
        ):
            raise CollectionError(f"invalid status for {source}")
        rights_keys = {"spdx_license", "license_file"} | (
            {"attribution"} if name == "dasc" else set()
        )
        rights = _mapping(item["redistribution"], rights_keys, "redistribution")
        if not isinstance(rights["spdx_license"], str) or not SPDX_RE.fullmatch(
            rights["spdx_license"]
        ):
            raise CollectionError(f"invalid SPDX license for {source}")
        if name == "dasc" and (
            not isinstance(rights["attribution"], str)
            or not rights["attribution"].strip()
            or UNSAFE_ATTRIBUTION_RE.search(rights["attribution"])
        ):
            raise CollectionError(f"invalid attribution for {source}")
        license_path = _path(rights["license_file"], "license_file")
        if _git_object_kind(path.parent, content, license_path) != "blob":
            raise CollectionError(f"missing or unsafe license at approved commit for {source}")
        license_bytes = _git(
            path.parent, "show", f"{content}:{license_path.as_posix()}", binary=True
        )
        if not license_bytes:
            raise CollectionError(f"missing license at approved commit for {source}")
        approved[source.as_posix()] = ApprovedFile(
            destination, status["label"], rights["spdx_license"], rights.get("attribution", "")
        )
    return content, approved


def read_source_locks(path: Path) -> tuple[SourceLock, ...]:
    root = _mapping(_read_yaml(path), {"schema_version", "sources"}, "website manifest")
    if (
        type(root["schema_version"]) is not int
        or root["schema_version"] != 2
        or not isinstance(root["sources"], dict)
        or set(root["sources"]) != set(EXPECTED)
    ):
        raise CollectionError("website manifest must be schema 2 with exactly pydasc and dasc")
    locks = []
    destinations = set()
    for name, repository in EXPECTED.items():
        source = _mapping(
            root["sources"][name],
            {"repository", "checkout_commit", "publication_manifest", "files"},
            f"source {name}",
        )
        commit = source["checkout_commit"]
        if (
            source["repository"] != repository
            or not isinstance(commit, str)
            or not SHA_RE.fullmatch(commit)
        ):
            raise CollectionError(f"invalid lock identity/commit for {name}")
        manifest_rel = _path(source["publication_manifest"], "publication_manifest")
        if not isinstance(source["files"], list) or not source["files"]:
            raise CollectionError(f"{name} lock files must be non-empty")
        selections = []
        for index, selected in enumerate(source["files"]):
            selected = _mapping(selected, {"source", "destination"}, f"{name}.files[{index}]")
            src = _path(selected["source"], "source")
            dest = _path(selected["destination"], "destination")
            if (
                dest.parts[0] != name
                or src.suffix.lower() not in ALLOWED
                or src.suffix.lower() != dest.suffix.lower()
            ):
                raise CollectionError(f"invalid selected file {src} -> {dest}")
            folded = dest.as_posix().casefold()
            if folded in destinations:
                raise CollectionError(f"duplicate destination: {dest}")
            destinations.add(folded)
            selections.append(SelectedEntry(name, repository, commit, src, dest))
        locks.append(SourceLock(name, repository, commit, manifest_rel, tuple(selections)))
    return tuple(locks)


def approve_entries(
    locks: tuple[SourceLock, ...], checkouts: dict[str, Path]
) -> list[ApprovedEntry]:
    if set(checkouts) != set(EXPECTED):
        raise CollectionError("approval requires exactly the configured source checkouts")
    entries = []
    for lock in locks:
        checkout = checkouts[lock.name].resolve()
        contract = checkout.joinpath(*lock.publication_manifest.parts)
        if contract.is_symlink() or not _inside(contract.resolve(), checkout):
            raise CollectionError(f"unsafe {lock.name} publication manifest")
        working = _read_regular_file(contract, f"{lock.name} publication manifest")
        if _git(checkout, "rev-parse", "HEAD").strip() != lock.checkout_commit:
            raise CollectionError(f"{lock.name} checkout commit mismatch")
        committed = _git(
            checkout,
            "show",
            f"{lock.checkout_commit}:{lock.publication_manifest.as_posix()}",
            binary=True,
        )
        if working != committed:
            raise CollectionError(f"{lock.name} publication manifest differs from locked commit")
        content, approved = _source_contract(
            contract, lock.name, lock.repository, lock.checkout_commit, committed
        )
        for selected in lock.selections:
            offer = approved.get(selected.source.as_posix())
            if offer is None or offer.destination != selected.destination:
                raise CollectionError(
                    f"missing source approval: {selected.source} -> {selected.destination}"
                )
            entries.append(
                ApprovedEntry(
                    selected.source_name,
                    selected.repository,
                    selected.checkout_commit,
                    selected.source,
                    selected.destination,
                    content,
                    offer.status,
                    offer.license_id,
                    offer.attribution,
                )
            )
    return entries


def load_manifest(path: Path, checkouts: dict[str, Path] | None = None):
    locks = read_source_locks(path)
    if checkouts is None:
        return [entry for lock in locks for entry in lock.selections]
    return approve_entries(locks, checkouts)

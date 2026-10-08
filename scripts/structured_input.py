"""Bounded JSON/YAML loading with duplicate-key rejection."""

import json
from pathlib import Path
from typing import Any
import yaml
from safe_files import read_regular_file
from publication_errors import CollectionError


class UniqueKeyLoader(yaml.SafeLoader):
    """Reject duplicate keys rather than silently changing a publication decision."""

    def construct_mapping(self, node, deep=False):
        self.flatten_mapping(node)
        result = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, str) or key in result:
                raise CollectionError("manifest keys must be unique strings")
            result[key] = self.construct_object(value_node, deep=deep)
        return result


def unique_json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise CollectionError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def read_json(data: bytes, context: str) -> Any:
    try:
        return json.loads(data, object_pairs_hook=unique_json_object)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise CollectionError(f"invalid {context}: {exc}") from exc


def read_yaml(path: Path) -> dict[str, Any]:
    try:
        # Website manifests may be explicitly addressed through a symlink;
        # source contracts and generated files must not be symlinks.
        data = read_regular_file(path.resolve(), "website manifest")
        return yaml.load(data.decode("utf-8"), Loader=UniqueKeyLoader)
    except (OSError, UnicodeError, yaml.YAMLError, RecursionError, RuntimeError) as exc:
        raise CollectionError(f"cannot read website manifest: {exc}") from exc


def require_mapping(value: object, keys: set[str], context: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        actual = set(value) if isinstance(value, dict) else set()
        raise CollectionError(
            f"{context} keys invalid (missing={sorted(keys - actual)}, unknown={sorted(map(repr, actual - keys))})"
        )
    return value

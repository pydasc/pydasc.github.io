"""Recoverable same-filesystem publication, with a fail-closed writer lock.

Successful generations replace only named outputs. A directory lock serializes
writers; an interrupted process leaves its backup/journal for operator recovery.
Do not delete a retained lock until the previous generation has been restored.
"""
from pathlib import Path
from typing import Callable
import json
import os
import shutil


class PublicationTransactionError(ValueError):
    pass


def publish(output: Path, stage: Path, names: tuple[str, ...],
            write_inventory: Callable[[], None], preflight: Callable[[], None]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    lock = output.parent / f".{output.name}.collection-lock"
    try:
        lock.mkdir(mode=0o700)
    except FileExistsError as exc:
        raise PublicationTransactionError(
            f"collection is active or needs recovery; inspect {lock} before retrying"
        ) from exc
    backup = lock / "previous"
    prepared = lock / "next"
    backup.mkdir()
    prepared.mkdir()
    destinations = (*names, "generated-inventory.json")
    originals = {name: (output / name).exists() for name in destinations}
    moved: list[str] = []
    installed: list[str] = []
    safe_to_remove = False

    def journal(phase: str) -> None:
        # Write intent before mutation. Only fixed destination names are used.
        record = {"schema_version": 1, "pid": os.getpid(), "output": str(output),
                  "phase": phase, "destinations": destinations,
                  "originals": originals, "moved": moved, "installed": installed}
        temporary = lock / "journal.tmp"
        with temporary.open("w") as stream:
            json.dump(record, stream, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, lock / "journal.json")

    try:
        journal("preparing")
        for name in names:
            shutil.copytree(stage / name, prepared / name)
        preflight()
        output.mkdir(parents=True, exist_ok=True)
        journal("replacing")
        for name in destinations:
            target = output / name
            if target.exists():
                os.replace(target, backup / name)
                moved.append(name)
                journal("replacing")
        for name in names:
            os.replace(prepared / name, output / name)
            installed.append(name)
            journal("replacing")
        # Register intent first: atomic inventory writing may fail after replace.
        installed.append("generated-inventory.json")
        journal("writing-inventory")
        write_inventory()
        journal("committed")
        safe_to_remove = True
    except BaseException:
        try:
            for name in reversed(installed):
                target = output / name
                if target.is_symlink():
                    raise PublicationTransactionError("output changed to symlink during rollback")
                if target.is_dir():
                    shutil.rmtree(target)
                else:
                    target.unlink(missing_ok=True)
            for name in reversed(moved):
                os.replace(backup / name, output / name)
            safe_to_remove = True
        except BaseException as rollback_error:
            raise PublicationTransactionError(
                f"rollback incomplete; preserve recovery data in {lock}"
            ) from rollback_error
        raise
    finally:
        if safe_to_remove:
            shutil.rmtree(lock)

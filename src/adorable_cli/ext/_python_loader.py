from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path
from typing import Any, Iterable


def iter_python_files(directory: Path) -> Iterable[Path]:
    if not directory.exists():
        return []
    files = [
        path
        for path in directory.rglob("*.py")
        if path.is_file() and not path.name.startswith("_")
    ]
    return sorted(files)


def load_module_from_path(path: Path) -> Any | None:
    module_key = hashlib.sha1(str(path).encode("utf-8")).hexdigest()
    module_name = f"adorable_cli.ext.user_{module_key}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(module_name, None)
        return None
    return module


def normalize_items(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [item for item in value if item is not None]
    return [value]


def load_objects_from_directory(directory: Path) -> list[Any]:
    objects: list[Any] = []
    for path in iter_python_files(directory):
        module = load_module_from_path(path)
        if module is None:
            continue

        objects.extend(normalize_items(getattr(module, "TOOLS", None)))
        objects.extend(normalize_items(getattr(module, "tools", None)))
        objects.extend(normalize_items(getattr(module, "TOOL", None)))
        objects.extend(normalize_items(getattr(module, "tool", None)))

        for fn_name in ("get_tools", "build_tools"):
            fn = getattr(module, fn_name, None)
            if callable(fn):
                objects.extend(normalize_items(fn()))

    return objects

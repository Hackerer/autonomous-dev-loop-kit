from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / ".agent-loop" / "scripts"


def load_common():
    if "common" in sys.modules:
        return sys.modules["common"]
    spec = importlib.util.spec_from_file_location("common", SCRIPTS_DIR / "common.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load common.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["common"] = module
    spec.loader.exec_module(module)
    return module


def load_module(name: str, filename: str):
    load_common()
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / filename)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {filename}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

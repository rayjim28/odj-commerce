"""The three application layers must keep their public entry points stable."""
from pathlib import Path
import importlib
import main

ROOT = Path(__file__).resolve().parents[1]


def test_layer_paths_and_asgi_compatibility():
    assert main.ROOT == ROOT
    assert main.STATIC_DIR == ROOT / "frontend" / "static"
    assert main.TEMPLATE_DIR == ROOT / "frontend" / "templates"
    assert (main.STATIC_DIR / "js/store.js").exists()
    assert (main.TEMPLATE_DIR / "admin.html").exists()
    assert main.app is importlib.import_module("backend.app").app


def test_legacy_imports_resolve_to_same_modules():
    names = {
        "database": "backend.database",
        "security": "backend.security",
        "staging_security": "backend.staging_security",
        "staging_setup": "backend.staging_setup",
        "payment": "middleware.payment",
        "notifications": "middleware.notifications",
        "launch_readiness": "middleware.launch_readiness",
    }
    for old, canonical in names.items():
        assert importlib.import_module(old) is importlib.import_module(canonical)

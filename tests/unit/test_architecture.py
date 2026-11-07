"""Enforces CLAUDE.md §4: domain is pure, services don't know HTTP, repositories don't know HTTP."""

import ast
from pathlib import Path

PKG = Path(__file__).resolve().parents[2] / "feature_signal"


def imports_of(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def files(sub: str) -> list[Path]:
    return [p for p in (PKG / sub).rglob("*.py")]


def test_domain_imports_no_io_layers():
    banned = (
        "feature_signal.integrations",
        "feature_signal.repositories",
        "feature_signal.api",
        "fastapi",
        "sqlalchemy",
        "httpx",
        "openai",
    )
    for f in files("domain"):
        bad = [i for i in imports_of(f) if i.startswith(banned)]
        assert not bad, f"{f.name} imports {bad}"


def test_services_do_not_import_fastapi():
    for f in files("services"):
        assert not [i for i in imports_of(f) if i.startswith("fastapi")], f.name


def test_repositories_do_not_import_http():
    for f in files("repositories"):
        assert not [i for i in imports_of(f) if i.startswith(("fastapi", "httpx"))], f.name

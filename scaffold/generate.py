# /// script
# requires-python = ">=3.10"
# dependencies = ["jinja2>=3.1", "pyyaml>=6.0"]
# ///
"""Generate a full-stack FastAPI + React project from scaffold.yaml.

Usage (from project root):
    uv run scaffold/generate.py

Modes:
    mode: operation  — single POST endpoint, no DB (ML inference, scoring, calculators)
    mode: resource   — full CRUD REST API with SQLite/SQLAlchemy (swappable to Postgres)
"""

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import jinja2
import yaml

ROOT = Path(__file__).parent.parent
TEMPLATES = Path(__file__).parent / "templates"


# ── Config ────────────────────────────────────────────────────────────────────

def load_config() -> dict[str, Any]:
    path = ROOT / "scaffold.yaml"
    if not path.exists():
        sys.exit("scaffold.yaml not found. Copy scaffold.yaml.example and fill it in.")
    with open(path) as f:
        cfg = yaml.safe_load(f)
    mode = cfg.get("mode", "operation")
    if mode == "operation":
        _validate_operation(cfg)
    elif mode == "resource":
        _validate_resource(cfg)
    else:
        sys.exit(f"Invalid mode '{mode}'. Must be 'operation' or 'resource'.")
    return cfg


def _validate_operation(cfg: dict[str, Any]) -> None:
    required = [
        ("project", "name"), ("project", "package"), ("project", "description"),
        ("domain", "input_model"), ("domain", "output_model"),
        ("domain", "endpoint_path"), ("domain", "handler_name"),
        ("domain", "business_logic_fn"),
        ("frontend", "form_component"), ("frontend", "result_component"),
    ]
    _check_required(cfg, required)


def _validate_resource(cfg: dict[str, Any]) -> None:
    required = [
        ("project", "name"), ("project", "package"), ("project", "description"),
        ("resource", "name"),
        ("frontend", "list_component"), ("frontend", "form_component"),
        ("frontend", "detail_component"),
    ]
    _check_required(cfg, required)


def _check_required(cfg: dict[str, Any], required: list[tuple[str, str]]) -> None:
    for section, key in required:
        if not cfg.get(section, {}).get(key):
            sys.exit(f"scaffold.yaml missing required field: {section}.{key}")


# ── Type mappings ─────────────────────────────────────────────────────────────

def py_to_ts(py_type: str) -> str:
    simple = {"int": "number", "float": "number", "str": "string", "bool": "boolean"}
    if py_type in simple:
        return simple[py_type]
    m = re.match(r'Literal\[(.+)\]', py_type)
    if m:
        values = [v.strip().replace('"', "'") for v in m.group(1).split(",")]
        return " | ".join(values)
    return py_type


def py_to_sa(py_type: str) -> str:
    """Map Python annotation to SQLAlchemy Column type string."""
    simple = {"int": "Integer", "float": "Float", "str": "String", "bool": "Boolean"}
    if py_type in simple:
        return simple[py_type]
    if "Literal" in py_type:
        return "String"
    return "String"


# ── Context building ──────────────────────────────────────────────────────────

def _enrich_fields(fields: list[dict[str, Any]], include_sa: bool = False) -> None:
    for f in fields:
        f["ts_type"] = py_to_ts(f.get("type", "unknown"))
        if include_sa:
            f["sa_type"] = py_to_sa(f.get("type", "unknown"))
        if "default" in f:
            raw = f["default"]
            f["py_default"] = "True" if raw is True else "False" if raw is False else repr(raw)
            f["ts_optional"] = True
        else:
            f["ts_optional"] = False


def build_context_operation(cfg: dict[str, Any]) -> dict[str, Any]:
    input_fields = cfg.get("input_fields", [])
    output_fields = cfg.get("output_fields", [])
    _enrich_fields(input_fields)
    _enrich_fields(output_fields)
    needs_literal = any("Literal" in f.get("type", "") for f in input_fields + output_fields)
    return {
        "mode": "operation",
        "project": cfg["project"],
        "domain": {**cfg["domain"], "endpoint_path": cfg["domain"]["endpoint_path"].lstrip("/")},
        "input_fields": input_fields,
        "output_fields": output_fields,
        "frontend": cfg["frontend"],
        "needs_literal": needs_literal,
        "input_field_names": ", ".join(f["name"] for f in input_fields),
        "output_field_names": ", ".join(f["name"] for f in output_fields),
        "lt": "<",
    }


def build_context_resource(cfg: dict[str, Any]) -> dict[str, Any]:
    resource_fields = cfg.get("resource", {}).get("fields", [])
    _enrich_fields(resource_fields, include_sa=True)
    rname = cfg["resource"]["name"]
    rlower = rname.lower()
    rplural = cfg["resource"].get("plural", rlower + "s")
    sa_types = sorted({f["sa_type"] for f in resource_fields})
    needs_literal = any("Literal" in f.get("type", "") for f in resource_fields)
    db_cfg = cfg.get("database", {"dev": "sqlite"})
    return {
        "mode": "resource",
        "project": cfg["project"],
        "resource": {
            **cfg["resource"],
            "name_lower": rlower,
            "name_plural": rplural,
        },
        "resource_fields": resource_fields,
        "resource_field_names": ", ".join(f["name"] for f in resource_fields),
        "sa_types": sa_types,
        "needs_literal": needs_literal,
        "database": db_cfg,
        "use_sqlite": db_cfg.get("dev", "sqlite") == "sqlite",
        "frontend": cfg["frontend"],
        "lt": "<",
    }


# ── Template selection ────────────────────────────────────────────────────────

def templates_operation(pkg: str, cfg: dict[str, Any]) -> dict[str, list[tuple[str, str]]]:
    form = cfg["frontend"]["form_component"]
    result = cfg["frontend"]["result_component"]
    return {
        "backend": [
            (f"backend/src/{pkg}/__init__.py",     "backend/src/app/__init__.py.j2"),
            (f"backend/src/{pkg}/config.py",        "backend/src/app/config.py.j2"),
            (f"backend/src/{pkg}/main.py",          "backend/src/app/main.py.j2"),
            (f"backend/src/{pkg}/api/__init__.py",  "backend/src/app/api/__init__.py.j2"),
            (f"backend/src/{pkg}/api/schemas.py",   "backend/src/app/api/schemas_operation.py.j2"),
            (f"backend/src/{pkg}/api/routes.py",    "backend/src/app/api/routes_operation.py.j2"),
            (f"backend/src/{pkg}/core/__init__.py", "backend/src/app/core/__init__.py.j2"),
            (f"backend/src/{pkg}/core/model.py",    "backend/src/app/core/model.py.j2"),
            ("backend/scripts/generate_openapi.py", "backend/scripts/generate_openapi.py.j2"),
            ("backend/tests/__init__.py",           "backend/tests/__init__.py.j2"),
            ("backend/tests/conftest.py",           "backend/tests/conftest_operation.py.j2"),
            ("backend/tests/test_api.py",           "backend/tests/test_api_operation.py.j2"),
            ("backend/tests/test_model.py",         "backend/tests/test_model_operation.py.j2"),
            ("backend/tests/test_contract_sync.py", "backend/tests/test_contract_sync.py.j2"),
        ],
        "frontend": [
            ("frontend/vite.config.ts",                     "frontend/vite.config.ts.j2"),
            ("frontend/src/index.css",                      "frontend/src/index.css.j2"),
            ("frontend/src/App.tsx",                        "frontend/src/App_operation.tsx.j2"),
            ("frontend/src/api/client.ts",                  "frontend/src/api/client_operation.ts.j2"),
            (f"frontend/src/components/{form}.tsx",         "frontend/src/components/Form.tsx.j2"),
            (f"frontend/src/components/{result}.tsx",       "frontend/src/components/Chart.tsx.j2"),
            ("frontend/src/test/setup.ts",                  "frontend/src/test/setup.ts.j2"),
            ("frontend/src/__tests__/App.test.tsx",         "frontend/src/__tests__/App.test.tsx.j2"),
        ],
    }


def templates_resource(pkg: str, cfg: dict[str, Any]) -> dict[str, list[tuple[str, str]]]:
    list_c  = cfg["frontend"]["list_component"]
    form_c  = cfg["frontend"]["form_component"]
    detail_c = cfg["frontend"]["detail_component"]
    return {
        "backend": [
            (f"backend/src/{pkg}/__init__.py",     "backend/src/app/__init__.py.j2"),
            (f"backend/src/{pkg}/config.py",        "backend/src/app/config.py.j2"),
            (f"backend/src/{pkg}/main.py",          "backend/src/app/main.py.j2"),
            (f"backend/src/{pkg}/api/__init__.py",  "backend/src/app/api/__init__.py.j2"),
            (f"backend/src/{pkg}/api/schemas.py",   "backend/src/app/api/schemas_resource.py.j2"),
            (f"backend/src/{pkg}/api/routes.py",    "backend/src/app/api/routes_resource.py.j2"),
            (f"backend/src/{pkg}/core/__init__.py", "backend/src/app/core/__init__.py.j2"),
            (f"backend/src/{pkg}/core/crud.py",     "backend/src/app/core/crud.py.j2"),
            (f"backend/src/{pkg}/database.py",      "backend/src/app/database.py.j2"),
            (f"backend/src/{pkg}/models.py",        "backend/src/app/models.py.j2"),
            ("backend/scripts/generate_openapi.py", "backend/scripts/generate_openapi.py.j2"),
            ("backend/tests/__init__.py",           "backend/tests/__init__.py.j2"),
            ("backend/tests/conftest.py",           "backend/tests/conftest_resource.py.j2"),
            ("backend/tests/test_api.py",           "backend/tests/test_api_resource.py.j2"),
            ("backend/tests/test_crud.py",          "backend/tests/test_crud_resource.py.j2"),
            ("backend/tests/test_contract_sync.py", "backend/tests/test_contract_sync.py.j2"),
        ],
        "frontend": [
            ("frontend/vite.config.ts",                      "frontend/vite.config.ts.j2"),
            ("frontend/src/index.css",                       "frontend/src/index.css.j2"),
            ("frontend/src/App.tsx",                         "frontend/src/App_resource.tsx.j2"),
            ("frontend/src/api/client.ts",                   "frontend/src/api/client_resource.ts.j2"),
            (f"frontend/src/components/{list_c}.tsx",        "frontend/src/components/Table.tsx.j2"),
            (f"frontend/src/components/{form_c}.tsx",        "frontend/src/components/Form.tsx.j2"),
            (f"frontend/src/components/{detail_c}.tsx",      "frontend/src/components/Detail.tsx.j2"),
            ("frontend/src/test/setup.ts",                   "frontend/src/test/setup.ts.j2"),
            ("frontend/src/__tests__/App.test.tsx",          "frontend/src/__tests__/App.test.tsx.j2"),
            (f"frontend/src/components/__tests__/{form_c}.test.tsx",
             "frontend/src/components/__tests__/Form.test.tsx.j2"),
        ],
    }


# ── Jinja2 ────────────────────────────────────────────────────────────────────

def make_env() -> jinja2.Environment:
    """Custom delimiters avoid conflicts with Python {} and TypeScript <>."""
    return jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(TEMPLATES)),
        variable_start_string="<<",
        variable_end_string=">>",
        block_start_string="<%",
        block_end_string="%>",
        comment_start_string="<#",
        comment_end_string="#>",
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )


def render(env: jinja2.Environment, tmpl: str, ctx: dict[str, Any]) -> str:
    return env.get_template(tmpl).render(**ctx)


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    print(f"  wrote {path.relative_to(ROOT)}")


def run(cmd: str, cwd: Path | None = None) -> None:
    print(f"  $ {cmd}")
    subprocess.run(cmd, shell=True, cwd=cwd or ROOT, check=True)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    cfg = load_config()
    mode = cfg.get("mode", "operation")
    pkg = cfg["project"]["package"]

    if mode == "operation":
        ctx = build_context_operation(cfg)
        tmpl_map = templates_operation(pkg, cfg)
    else:
        ctx = build_context_resource(cfg)
        tmpl_map = templates_resource(pkg, cfg)

    env = make_env()

    print(f"\n=== Backend ({mode} mode) ===")
    for out, tmpl in tmpl_map["backend"]:
        write(ROOT / out, render(env, tmpl, ctx))

    print("\n=== Root files ===")
    for out, tmpl in [("pyproject.toml", "pyproject.toml.j2"), ("Makefile", "Makefile.j2")]:
        write(ROOT / out, render(env, tmpl, ctx))

    print("\n=== Frontend ===")
    frontend_dir = ROOT / "frontend"
    if not (frontend_dir / "package.json").exists():
        # Pin to vite@7: compatible with @tailwindcss/vite@4, no auto-start prompt
        run("npm create vite@7 frontend -- --template react-ts --yes")
    else:
        print("  frontend/ already exists — skipping npm create vite")
    run(
        "npm install --legacy-peer-deps "
        "tailwindcss @tailwindcss/vite recharts react-is openapi-typescript",
        cwd=ROOT / "frontend",
    )
    run(
        "npm install -D --legacy-peer-deps vitest @vitest/ui jsdom "
        "@testing-library/react @testing-library/user-event @testing-library/jest-dom",
        cwd=ROOT / "frontend",
    )

    for out, tmpl in tmpl_map["frontend"]:
        write(ROOT / out, render(env, tmpl, ctx))

    _patch_package_json(ROOT / "frontend/package.json")

    print("\n=== Install + verify ===")
    run("uv sync --extra dev")
    run("uv run python backend/scripts/generate_openapi.py")
    run("npm --prefix frontend run generate:types")
    run("uv run ruff check backend/src backend/tests")
    run("uv run mypy backend/src")
    run("uv run pytest -v")

    print(f"""
✓  Scaffold complete ({mode} mode).

Next:
  1. /scaffold  → generates CLAUDE.md + plan.md
  2. make backend   → :8000  (/docs shows your schema)
  3. make frontend  → :5173
""")


def _patch_package_json(path: Path) -> None:
    data = json.loads(path.read_text())
    data["scripts"].update({
        "generate:types": "openapi-typescript ../openapi.json -o src/api/types.gen.ts",
        "test":           "vitest run",
        "test:watch":     "vitest",
        "test:ui":        "vitest --ui",
    })
    path.write_text(json.dumps(data, indent=2) + "\n")
    print(f"  patched {path.relative_to(path.parent.parent)}")


if __name__ == "__main__":
    main()

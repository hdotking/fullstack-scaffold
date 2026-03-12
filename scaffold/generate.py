# /// script
# requires-python = ">=3.10"
# dependencies = ["jinja2>=3.1", "pyyaml>=6.0"]
# ///
"""Generate a full-stack FastAPI + React project from scaffold.yaml.

Usage (from project root):
    uv run scaffold/generate.py
"""

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
    _validate(cfg)
    return cfg


def _validate(cfg: dict[str, Any]) -> None:
    required = [
        ("project", "name"),
        ("project", "package"),
        ("project", "description"),
        ("domain", "input_model"),
        ("domain", "output_model"),
        ("domain", "endpoint_path"),
        ("domain", "handler_name"),
        ("domain", "business_logic_fn"),
        ("frontend", "form_component"),
        ("frontend", "result_component"),
    ]
    for section, key in required:
        if not cfg.get(section, {}).get(key):
            sys.exit(f"scaffold.yaml missing required field: {section}.{key}")


# ── Type mapping ──────────────────────────────────────────────────────────────

def py_to_ts(py_type: str) -> str:
    """Map Python type annotation string to TypeScript equivalent."""
    simple = {"int": "number", "float": "number", "str": "string", "bool": "boolean"}
    if py_type in simple:
        return simple[py_type]
    m = re.match(r'Literal\[(.+)\]', py_type)
    if m:
        values = [v.strip().replace('"', "'") for v in m.group(1).split(",")]
        return " | ".join(values)
    return py_type  # passthrough for complex types


# ── Context building ──────────────────────────────────────────────────────────

def build_context(cfg: dict[str, Any]) -> dict[str, Any]:
    input_fields = cfg.get("input_fields", [])
    output_fields = cfg.get("output_fields", [])

    # Enrich fields with computed properties
    for field in input_fields:
        field["ts_type"] = py_to_ts(field.get("type", "unknown"))
        if "default" in field:
            raw = field["default"]
            field["py_default"] = "True" if raw is True else "False" if raw is False else repr(raw)
            field["ts_optional"] = True
        else:
            field["ts_optional"] = False

    for field in output_fields:
        field["ts_type"] = py_to_ts(field.get("type", "unknown"))

    needs_literal = any(
        "Literal" in f.get("type", "")
        for f in input_fields + output_fields
    )

    # Endpoint path without leading slash (router prefix supplies /api/v1)
    endpoint_path = cfg["domain"]["endpoint_path"].lstrip("/")

    return {
        "project": cfg["project"],
        "domain": {**cfg["domain"], "endpoint_path": endpoint_path},
        "input_fields": input_fields,
        "output_fields": output_fields,
        "frontend": cfg["frontend"],
        "needs_literal": needs_literal,
        "input_field_names": ", ".join(f["name"] for f in input_fields),
        "output_field_names": ", ".join(f["name"] for f in output_fields),
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


def render(env: jinja2.Environment, template_path: str, ctx: dict[str, Any]) -> str:
    return env.get_template(template_path).render(**ctx)


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
    ctx = build_context(cfg)
    env = make_env()
    pkg = cfg["project"]["package"]
    form = cfg["frontend"]["form_component"]
    result = cfg["frontend"]["result_component"]

    print("\n=== Backend ===")
    backend_files = [
        (f"backend/src/{pkg}/__init__.py",     "backend/src/app/__init__.py.j2"),
        (f"backend/src/{pkg}/config.py",        "backend/src/app/config.py.j2"),
        (f"backend/src/{pkg}/main.py",          "backend/src/app/main.py.j2"),
        (f"backend/src/{pkg}/api/__init__.py",  "backend/src/app/api/__init__.py.j2"),
        (f"backend/src/{pkg}/api/schemas.py",   "backend/src/app/api/schemas.py.j2"),
        (f"backend/src/{pkg}/api/routes.py",    "backend/src/app/api/routes.py.j2"),
        (f"backend/src/{pkg}/core/__init__.py", "backend/src/app/core/__init__.py.j2"),
        (f"backend/src/{pkg}/core/model.py",    "backend/src/app/core/model.py.j2"),
        ("backend/scripts/generate_openapi.py", "backend/scripts/generate_openapi.py.j2"),
        ("backend/tests/__init__.py",           "backend/tests/__init__.py.j2"),
        ("backend/tests/conftest.py",           "backend/tests/conftest.py.j2"),
        ("backend/tests/test_api.py",           "backend/tests/test_api.py.j2"),
        ("backend/tests/test_model.py",         "backend/tests/test_model.py.j2"),
        ("backend/tests/test_contract_sync.py", "backend/tests/test_contract_sync.py.j2"),
    ]
    for out, tmpl in backend_files:
        write(ROOT / out, render(env, tmpl, ctx))

    print("\n=== Root files ===")
    for out, tmpl in [
        ("pyproject.toml", "pyproject.toml.j2"),
        ("Makefile",       "Makefile.j2"),
    ]:
        write(ROOT / out, render(env, tmpl, ctx))

    print("\n=== Frontend ===")
    run("npm create vite@latest frontend -- --template react-ts --yes")
    run("npm install tailwindcss recharts openapi-typescript", cwd=ROOT / "frontend")
    run("npm install @tailwindcss/vite --legacy-peer-deps", cwd=ROOT / "frontend")

    frontend_files = [
        ("frontend/vite.config.ts",                    "frontend/vite.config.ts.j2"),
        ("frontend/src/index.css",                     "frontend/src/index.css.j2"),
        ("frontend/src/App.tsx",                       "frontend/src/App.tsx.j2"),
        ("frontend/src/api/client.ts",                 "frontend/src/api/client.ts.j2"),
        (f"frontend/src/components/{form}.tsx",        "frontend/src/components/Form.tsx.j2"),
        (f"frontend/src/components/{result}.tsx",      "frontend/src/components/Chart.tsx.j2"),
    ]
    for out, tmpl in frontend_files:
        write(ROOT / out, render(env, tmpl, ctx))

    # Update package.json with generate:types script
    _patch_package_json(ROOT / "frontend/package.json")

    print("\n=== Install + verify ===")
    run("uv sync --extra dev")
    run("uv run python backend/scripts/generate_openapi.py")
    run("npm --prefix frontend run generate:types")
    run("uv run ruff check backend/src backend/tests")
    run("uv run mypy backend/src")
    run("uv run pytest -v")

    print(f"""
✓  Scaffold complete.

Next steps:
  1. Run /scaffold in Claude Code → generates CLAUDE.md + plan.md
  2. make backend   → starts :8000  (/docs shows your schema)
  3. make frontend  → starts :5173
  4. Implement backend/src/{pkg}/core/model.py
     then backend/src/{pkg}/api/routes.py
""")


def _patch_package_json(path: Path) -> None:
    import json
    data = json.loads(path.read_text())
    data["scripts"]["generate:types"] = "openapi-typescript ../openapi.json -o src/api/types.gen.ts"
    path.write_text(json.dumps(data, indent=2) + "\n")
    print(f"  patched {path.relative_to(path.parent.parent)}")


if __name__ == "__main__":
    main()

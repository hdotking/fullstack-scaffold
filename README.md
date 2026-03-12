# fullstack-scaffold

GitHub template repo → FastAPI + React + Tailwind + fully-wired contract pipeline in one command.

## Stack

- **Backend**: FastAPI, Pydantic v2, uvicorn, mypy, ruff, pytest
- **Frontend**: React + TypeScript, Vite, Tailwind v4, recharts
- **Contract**: openapi.json (committed) → openapi-typescript → types.gen.ts
- **Hooks**: ruff+mypy on every Python edit, auto-regen on schemas.py edit, pytest on stop

## Usage

### 1. Create a new project from this template

```bash
gh repo create my-app --template yourusername/fullstack-scaffold --clone
cd my-app
```

### 2. Configure

```bash
cp scaffold.yaml.example scaffold.yaml
# Edit scaffold.yaml — fill in project, domain, fields, frontend component names
```

### 3. Generate

```bash
uv run scaffold/generate.py
```

This creates all structural files, installs deps, and verifies the scaffold passes
ruff + mypy + pytest.

### 4. Add context (run in Claude Code)

```
/scaffold
```

Reads scaffold.yaml and writes CLAUDE.md + plan.md with domain-specific context
and interview talking points.

### 5. Implement

```bash
make backend    # :8000 — /docs shows your schema
make frontend   # :5173
```

Edit `backend/src/{package}/core/model.py` → implement business logic.
Edit `backend/src/{package}/api/routes.py` → wire up the call.
Edit `frontend/src/components/` → build the UI.

## What generate.py does

1. Renders all backend files from `scaffold/templates/` using your config
2. Runs `npm create vite@latest frontend` + installs Tailwind/recharts/openapi-typescript
3. Renders frontend files (overwrites Vite defaults)
4. Writes `pyproject.toml` and `Makefile` for your package name
5. Runs `uv sync`, `make types`, ruff, mypy, pytest — all must pass before handing off

## Injection Points (scaffold.yaml only)

| Field | Controls |
|-------|---------|
| `project.name/package` | Package name, pyproject.toml, all imports |
| `project.description` | Docs title, config, CLAUDE.md header |
| `domain.*` | Model names, endpoint path, function names |
| `input_fields` | Pydantic model fields + TS interface + form TODO comment |
| `output_fields` | Pydantic model fields + TS interface + result TODO comment |
| `frontend.*` | React component names |

## Architecture

```
scaffold.yaml
    │
    └── uv run scaffold/generate.py
              │  deterministic (Jinja2 templates)
              ├── backend/src/{package}/   ← all Python files
              ├── frontend/src/            ← all TS/TSX files
              ├── pyproject.toml
              └── Makefile

    └── /scaffold  (Claude Code skill)
              │  intelligent (reads config, writes prose)
              ├── CLAUDE.md   ← tooling notes + project context + talking points
              └── plan.md     ← checklist + domain notes
```

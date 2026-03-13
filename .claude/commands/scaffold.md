Read `scaffold.yaml` from the project root directory.

Using the values from scaffold.yaml, write two files completely:

---

**1. Write `CLAUDE.md`** with exactly these sections:

# {project.name} — {project.description}

## Tooling Notes (read before writing code)

- **Tailwind v4** — no `tailwindcss init`. Use `@tailwindcss/vite` plugin in
  `vite.config.ts` and `@import "tailwindcss"` at top of CSS.
  Install: `npm install @tailwindcss/vite --legacy-peer-deps`
- **Pydantic v2** — use `from pydantic import ValidationInfo` for field
  validators. Never use `pydantic_core.core_schema.FieldValidationInfo` (deprecated).
- **recharts v3** — `Cell` is deprecated; add `fill` to each data object
  instead of wrapping `<Bar>` children in `<Cell>`. `Tooltip formatter`
  receives `ValueType | undefined` — guard with `Number(v ?? 0)`, not a bare
  `number` cast.
- **Inline comments** — keep ≤ 80 chars to stay under ruff's 88-char line limit.
- **Working directory** — all `uv run` and `make` commands run from project root.
- **Read before Write** — Edit/Write tools require the file to have been Read first.

## Architecture

```
backend/src/{package}/api/schemas.py  ← SOURCE OF TRUTH
    │  generate_openapi.py
    ▼
openapi.json  ← COMMITTED CONTRACT ARTIFACT
    │  npm run generate:types
    ▼
frontend/src/api/types.gen.ts  ← AUTO-GENERATED, never hand-edit
    │
    ▼
client.ts → App.tsx → {form_component}.tsx / {result_component}.tsx
```

## Commands

```bash
make backend     # FastAPI dev server :8000
make frontend    # Vite dev server :5173
make types       # regenerate openapi.json + types.gen.ts
make test        # pytest
make lint        # ruff check + format
make typecheck   # mypy + tsc --noEmit
```

## Key Files

| File | Role |
|------|------|
| `backend/src/{package}/api/schemas.py` | Pydantic models — contract source of truth |
| `backend/src/{package}/api/routes.py` | FastAPI routes — stub raises 501 |
| `backend/src/{package}/core/model.py` | Business logic — raises NotImplementedError |
| `openapi.json` | Committed contract artifact |
| `frontend/src/api/types.gen.ts` | Auto-generated TS types — never edit |
| `frontend/src/api/client.ts` | Typed fetch wrapper with error handling |

## Contract Enforcement

1. `.claude/hooks/regen-types.sh` — fires on `schemas.py` edit → auto-regenerates
2. `test_contract_sync.py` — fails if `openapi.json` is stale
3. `tsc --noEmit` — fails on type mismatch with generated contract

## Project Context

Write 2-3 sentences describing the domain from scaffold.yaml's project.description
and the input/output models. What does this app do? What does the model compute?

---

**2. Write `plan.md`** with exactly these sections:

# {project.name} — Implementation Plan

## Checklist

### Backend
- [ ] `core/model.py` — implement {domain.business_logic_fn}()
- [ ] `api/routes.py` — replace HTTPException(501) with model call
- [ ] `api/schemas.py` — add any fields the model needs

### Frontend
- [ ] `{form_component}.tsx` — wire up all {input_model} fields
- [ ] `{result_component}.tsx` — render {output_model} fields
- [ ] `App.tsx` — form → API call → result display

### Contract
- [ ] `make types` after any schema change

### Verification
- [ ] `make test` — all 13 tests pass
- [ ] `make typecheck` — mypy + tsc clean
- [ ] `make backend` — /docs shows correct schema, /{endpoint_path} returns data

## Scaffold Commands

```bash
# From project root (always)
uv sync --extra dev
npm --prefix frontend install
uv run python backend/scripts/generate_openapi.py
npm --prefix frontend run generate:types

uv run ruff check backend/src backend/tests
uv run mypy backend/src
uv run pytest -v
cd frontend && npx tsc --noEmit
```

## Key Import Reminders

```python
# Pydantic v2 field validator — public API only
from pydantic import ValidationInfo, field_validator

# Raise HTTPException not NotImplementedError
def {handler_name}(payload: {input_model}) -> {output_model}:
    raise HTTPException(status_code=501, detail="Not implemented yet")
```

## Domain Notes

Write a paragraph describing the business logic to implement for
{domain.business_logic_fn}(). What inputs matter most? What does the output
represent? Are there any fields accepted for forward-compatibility that aren't
used in the current formula?

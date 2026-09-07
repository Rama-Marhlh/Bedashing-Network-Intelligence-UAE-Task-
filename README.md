# Bedashing Geospatial Decision Support

A decision-support dashboard for reviewing Bedashing's UAE branch network, branch health,
competitors, drive-time coverage, overlap, reviews, services, financial scenarios, and potential
growth areas. It combines a Next.js/MapLibre interface with FastAPI and a Pydantic AI analyst.

This system supports human review. It does **not** automate branch closure, leasing, or investment.

## Quick start for time-constrained reviewers

### Prerequisites

- Python 3.11+
- Node.js 20+ and npm
- A valid OpenAI API key
- Free local ports `8000` and `3001`

### 1. Install

From the repository root in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]" -e apps/api
npm install
npm run sync:data
```

`sync:data` copies the validated `app_data/` snapshot to `apps/web/public/app_data/`; it does not
recollect external data.

### 2. Configure

Create/update the root `.env`:

```dotenv
ANALYST_MODE=llm
OPENAI_API_KEY=your_openai_api_key
AI_MODEL=openai:gpt-5-mini
ANALYST_TIMEOUT_SECONDS=90
```

Keep the key server-side and never use a `NEXT_PUBLIC_` prefix. The root `.env` overrides stale
terminal values. Restart FastAPI after changing it.

### 3. Run the API

Terminal 1:

```powershell
.\.venv\Scripts\python.exe -m uvicorn bedashing_api.main:app --app-dir apps/api/src --reload --host 127.0.0.1 --port 8000
```

Verify it:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Expected: `status=ok` and `mode=llm`. If it says `static`, stop the old API process, verify `.env`,
and restart it.

### 4. Run the dashboard

Terminal 2:

```powershell
npm run dev:web -- --port 3001
```

Open <http://localhost:3001/>. The analyst header should show that the AI model is connected.

### 5. Smoke test

```powershell
$body = @{ question = "Tell me about the total branches and their analysis" } | ConvertTo-Json
Invoke-RestMethod `
  -Uri http://127.0.0.1:8000/api/analyst/query `
  -Method Post -ContentType "application/json" -Body $body
```

Model answers can take several seconds because the LLM selects grounded tools and the result must
pass response validation.

## Publish this project to GitHub

The repository ignores `.env`, virtual environments, dependencies, build output, caches, and the
generated browser copy of `app_data`. Before publishing, confirm that `.env` remains ignored so the
OpenAI and data-provider keys are never uploaded.

### Option A: GitHub CLI (fastest)

Install and authenticate the GitHub CLI if it is not already available:

```powershell
gh auth login
```

Then run these commands from the project root. Replace `bedashing-geospatial-decision-support` if
you want a different repository name:

```powershell
git init
git branch -M main
git check-ignore .env
git add .
git status
git commit -m "Initial Bedashing geospatial decision-support release"
gh repo create bedashing-geospatial-decision-support --private --source=. --remote=origin --push
```

`git check-ignore .env` should print `.env`. Review `git status` before committing and confirm that
`.env`, `.venv`, `node_modules`, and `.next` are absent. Change `--private` to `--public` only if the
data and code have been approved for public release.

### Option B: Create the GitHub repository in the browser

Create an empty repository on GitHub without adding a README, `.gitignore`, or license. Copy its
HTTPS URL, then run:

```powershell
git init
git branch -M main
git check-ignore .env
git add .
git status
git commit -m "Initial Bedashing geospatial decision-support release"
git remote add origin https://github.com/YOUR-USERNAME/YOUR-REPOSITORY.git
git push -u origin main
```

For later updates:

```powershell
git status
git add README.md
git commit -m "Improve technical documentation"
git push
```

Use `git add .` instead of `git add README.md` when a later commit intentionally includes all
reviewed project changes. Never use `git add -f .env`.

## What to evaluate

- Network KPIs and PROTECT/HOLD/SHRINK recommendation filters
- Interactive branch, catchment, competitor, whitespace, cluster, and shortlist map layers
- Branch comparison and component-level health analysis
- Branch details, reviews, competitors, services, and financial scenarios
- Filtered/paginated reviews with English and Arabic preserved
- H3 growth cells, contiguous clusters, and reviewed Top 10 search areas
- Grounded AI answers and explicit dashboard actions

Example questions:

- `How many SHRINK branches do we have?`
- `Explain the total portfolio and recommendation distribution.`
- `Why are the SHRINK branches classified that way?`
- `Compare branches by health score.`
- `Which competitors are inside a branch's 10-minute catchment?`
- `What are the strongest reviewed expansion areas?`
- `Show only PROTECT branches on the map.`

## Current committed snapshot

These are snapshot values, not live market data:

| Measure                                           |                      Value |
| ------------------------------------------------- | -------------------------: |
| Branches                                          |                         24 |
| PROTECT / HOLD / SHRINK                           |                 7 / 12 / 5 |
| Average health score                              |                      52.08 |
| Average Google rating                             |                       4.62 |
| Google review count represented in branch metrics |                     20,960 |
| Observed unique competitors                       |                      2,367 |
| Catchments                                        | 72 (5, 10, and 15 minutes) |
| Whitespace cells                                  |                      5,548 |
| GROW / WATCH / SKIP cells                         |      1,727 / 1,222 / 2,599 |
| Growth clusters / reviewed shortlist              |                   171 / 10 |

Competitors are observed Google Places candidates, not an exhaustive census.

## Architecture

```text
Validated app_data files
  +--> Next.js 15 + React 19 + MapLibre dashboard
  +--> FastAPI repository and deterministic services
         +--> Pydantic AI + OpenAI
         +--> validated response + bounded UI actions
```

The model interprets intent and selects tools. Deterministic repository functions supply factual
counts, rankings, branch records, catchment relationships, reviews, and methodology. Pydantic
validates the final answer and action plan.

| Path                                | Purpose                                                |
| ----------------------------------- | ------------------------------------------------------ |
| `app_data/`                         | Canonical API runtime snapshot                         |
| `apps/api/`                         | FastAPI, agent, tools, repository, services, and tests |
| `apps/web/`                         | Next.js dashboard and UI tests                         |
| `apps/web/public/app_data/`         | Browser data copied by `sync:data`                     |
| `packages/data-contract/`           | Shared Zod contracts and parity fixtures               |
| `data/raw/`, `data/clean/`          | Source responses and cleaned intermediates             |
| `data/analysis/`, `data/decisions/` | Metrics, decisions, clusters, and methodologies        |
| `data/external/`                    | Supplied reviews, services, and population inputs      |
| `scripts/`                          | Publish, sync, and validation utilities                |
| `docs/`                             | Audit, validation, and demo documentation              |

## Configuration

| Variable                      | Default                 | Meaning                                   |
| ----------------------------- | ----------------------- | ----------------------------------------- |
| `ANALYST_MODE`                | `static` in code        | `llm`, `auto`, or `static`                |
| `OPENAI_API_KEY`              | none                    | Server-side credential required for AI    |
| `AI_MODEL`                    | `openai:gpt-5-mini`     | Pydantic AI provider/model string         |
| `ANALYST_TIMEOUT_SECONDS`     | `90`                    | Request timeout, clamped to 5–120 seconds |
| `NEXT_PUBLIC_ANALYST_API_URL` | `http://127.0.0.1:8000` | Browser-visible API base URL              |
| `NEXT_PUBLIC_MAP_STYLE_URL`   | inline style            | Optional public MapLibre style URL        |
| `AGENT_URL`                   | project-specific        | Optional CopilotKit proxy upstream        |

Modes:

- `llm`: requires a constructible model provider at startup.
- `auto`: attempts model construction and permits startup in static fallback.
- `static`: disables the external model; the dashboard and deterministic endpoints still work.

The panel directly uses `NEXT_PUBLIC_ANALYST_API_URL`. An AG-UI-compatible SSE adapter is also
available at `/api/agui`.

## API

OpenAPI documentation: <http://127.0.0.1:8000/docs>

| Method | Endpoint                                         | Purpose                             |
| ------ | ------------------------------------------------ | ----------------------------------- |
| GET    | `/health`                                        | API status and analyst mode         |
| GET    | `/api/data-health`                               | Snapshot/relationship validation    |
| GET    | `/api/portfolio-health`                          | Portfolio and branch health records |
| GET    | `/api/branches/{branch_id}/intelligence`         | Branch intelligence bundle          |
| GET    | `/api/branches/{branch_id}/reviews`              | Filtered, paginated reviews         |
| GET    | `/api/services`                                  | Service catalogue and summaries     |
| GET    | `/api/competitors/{competitor_id}`               | Competitor details                  |
| GET    | `/api/competitors/{competitor_id}/relationships` | Branch relationships                |
| GET    | `/api/whitespace/{h3_cell}`                      | Validated cell analysis             |
| POST   | `/api/analyst/query`                             | Structured analyst query            |
| POST   | `/api/agui`                                      | AG-UI SSE response                  |

Analyst responses include the answer, key findings, evidence, referenced entities, data sources,
limitations, and a bounded action plan.

## Methodology

### Branch health

```text
health = 35% customer signal + 25% competitive position
       + 30% network value + 10% catchment reach
```

- PROTECT: health at least 62
- SHRINK: health below 40 plus the documented network-value/overlap guardrail
- HOLD: all other cases

Scores are relative external-market signals on a 0–100 scale. SHRINK means priority for internal
commercial review, not automatic closure. Financial scenarios are excluded from recommendations.

### Whitespace

H3 scores combine population (40%), 10-minute coverage gap (30%), market activity (15%), and
competition headroom (15%). GROW requires human validation; WATCH is inconclusive; SKIP is
unattractive under current public signals. Contiguous GROW cells form clusters. Shortlist points are
search anchors, not approved sites.

### Reviews

A valid `data/external/bedashing_google_reviews.csv` is reported as `FULL_EXTERNAL_DATASET`;
otherwise the published sample is used. “Full” means every row in the supplied export, not every
Google review. Filters run before pagination. Sentiment is rating-based: 4–5 positive, 3 neutral,
1–2 negative. Bilingual keyword topics can miss context, variants, and sarcasm.

### Financial scenarios

```text
hours/day × operating days × productive staff × utilization
× list productivity/hour × realization
```

Hours and prices are sourced; productivity is derived from prices; days, staff, utilization, and
realization are assumed. Outputs are **ESTIMATED — SCENARIO, NOT ACTUAL REVENUE** and do not
represent profit, bookings, cash flow, or business value.

### Provenance

| Label            | Meaning                                                             |
| ---------------- | ------------------------------------------------------------------- |
| OBSERVED         | Public branch, review, or competitor fact                           |
| SOURCED          | WorldPop, official catalogue, or public opening-hours value         |
| DERIVED          | Computed coverage, overlap, density, sentiment, or component metric |
| DECISION-DERIVED | Health/opportunity score or recommendation                          |
| RULE-DERIVED     | Deterministic competitor tier or rating sentiment                   |
| ASSUMED          | Unobserved scenario input                                           |

## Data sources and pipeline

Sources are the official Bedashing locator/catalogue, supplied Google Places exports,
OpenRouteService/OpenStreetMap catchments, and WorldPop Global2 R2025A population. Normal evaluation
uses published files and calls no collection API.

The numbered root scripts document collection, resolution, competitor classification, 5/10/15-minute
catchments, overlap/coverage, H3 whitespace, branch decisions, clusters, shortlist review, services,
financial scenarios, reviews, and publication. Re-running collection can require paid credentials
and can change results; it is unnecessary for evaluating the committed snapshot.

## Tests and build

Fast reviewer checks:

```powershell
npm run validate:data
.\.venv\Scripts\python.exe -m pytest apps/api/tests -q
npm run test --workspace @bedashing/web
npm run typecheck
```

Full check (data validation, lint, formatting, tests, and types):

```powershell
npm run check
```

Production web build:

```powershell
npm run build
npm run start --workspace @bedashing/web -- -p 3001
```

FastAPI must remain running for AI chat and dynamic intelligence endpoints.

## Troubleshooting

### Header says “Static fallback — no AI model”

Check `/health`, verify `ANALYST_MODE=llm` and the API key, restart FastAPI, then hard-refresh the
browser. Greetings and simple counts may be deterministic, so they do not prove the model is active;
`/health` must report `mode=llm`.

### Analyst times out

The configured model uses low reasoning effort for responsive grounded tool calls. If the provider
is slow, increase `ANALYST_TIMEOUT_SECONDS` up to 120, restart FastAPI, and inspect its terminal for
timeout, authentication, HTTP, or output-validation warnings.

### Dashboard cannot reach FastAPI

Confirm port 8000 is listening. For another host/port, set `NEXT_PUBLIC_ANALYST_API_URL` before
starting Next.js. Backend CORS currently permits localhost ports 3000–3003 and
`127.0.0.1:3003`.

### Data appears stale

Run `npm run sync:data`, refresh Next.js, and use `npm run validate:data` to verify counts, hashes,
and relationships.

## Known limitations and responsible use

- Snapshot data is not live; competitors are not an exhaustive census.
- Catchments are modeled isochrones, not live traffic or customer origins.
- WorldPop population is not income, spend, demand, or site footfall.
- Reviews have selection bias; sentiment and topics can miss language context.
- No internal sales, profit, rent, payroll, bookings, utilization, retention, origins, footfall,
  income, or property-availability data is included.
- Service data is network-level; branch-level availability is unknown.
- Growth points and SHRINK labels are review priorities, not approved actions.

Material decisions require finance, operations, real-estate, leadership, and local-market review.
Keep secrets only in ignored `.env` files, rotate exposed keys, and never place secrets in
`NEXT_PUBLIC_*` variables.

## Additional documentation

- [Demo walkthrough](docs/demo-walkthrough.md)
- [Requirements audit](docs/requirements-audit.md)
- [Phase 1 validation](docs/phase-1-validation.md)

Screenshots in `artifacts/` are illustrative. The running product, committed data, API responses,
and in-application methodology are authoritative.

# Bedashing Geospatial Decision Support

A decision-support dashboard for reviewing Bedashing's UAE branch network, branch health,
competitors, drive-time coverage, overlap, reviews, services, financial scenarios, and potential
growth areas. It combines a Next.js/MapLibre interface with FastAPI and a Pydantic AI analyst.

This system supports human review. It does **not** automate branch closure, leasing, or investment.

## Technical stack

| Layer          | Technology                       | Responsibility                                                      |
| -------------- | -------------------------------- | ------------------------------------------------------------------- |
| Web            | Next.js 15, React 19, TypeScript | Dashboard pages, state, analyst panel, and API integration          |
| Mapping        | MapLibre GL                      | Branch, catchment, competitor, whitespace, and growth visualization |
| API            | FastAPI, Python 3.11+, Pydantic  | Validated HTTP endpoints and response contracts                     |
| AI             | Pydantic AI, OpenAI `gpt-5-mini` | Intent interpretation and grounded tool selection                   |
| Data contracts | Pydantic and Zod                 | Runtime validation across Python and TypeScript                     |
| Tests          | pytest and Vitest                | API, analytical, contract, state, and component verification        |

## Clone and run locally

These instructions are designed for a clean computer and are the recommended evaluation path.

### Prerequisites

- Python 3.11+
- Node.js 20+ and npm
- Git
- A valid OpenAI API key for AI analyst evaluation
- Free local ports `8000` and `3001`

Confirm the required tools:

```powershell
git --version
python --version
node --version
npm --version
```

### 1. Clone the GitHub repository

Repository: [Bedashing Network Intelligence UAE Task](https://github.com/Rama-Marhlh/Bedashing-Network-Intelligence-UAE-Task-)

```powershell
git clone https://github.com/Rama-Marhlh/Bedashing-Network-Intelligence-UAE-Task-.git bedashing-network-intelligence
cd bedashing-network-intelligence
```

The final argument gives the local folder a clean name even though the GitHub repository name ends
with a hyphen.

### 2. Install Python and JavaScript dependencies

From the repository root in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]" -e apps/api
npm install
npm run sync:data
```

`sync:data` copies the validated `app_data/` snapshot to `apps/web/public/app_data/`; it does not
recollect external data.

### 3. Configure environment variables

Create a local environment file from the committed template:

```powershell
Copy-Item .env.example .env
code .env
```

Set these values in the root `.env`:

```dotenv
ANALYST_MODE=llm
OPENAI_API_KEY=your_openai_api_key
AI_MODEL=openai:gpt-5-mini
ANALYST_TIMEOUT_SECONDS=90
```

Keep the key server-side and never use a `NEXT_PUBLIC_` prefix. The root `.env` overrides stale
terminal values. `.env` is ignored by Git; restart FastAPI after changing it.

### 4. Start and verify FastAPI

Terminal 1:

```powershell
.\.venv\Scripts\python.exe -m uvicorn bedashing_api.main:app --app-dir apps/api/src --reload --host 127.0.0.1 --port 8000
```

In a third terminal, verify the backend:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Expected: `status=ok` and `mode=llm`. If it says `static`, stop the old API process, verify `.env`,
and restart it.

You can also open the interactive API documentation at <http://127.0.0.1:8000/docs>.

### 5. Start the dashboard

Terminal 2:

```powershell
npm run dev:web -- --port 3001
```

Open <http://localhost:3001/>. The analyst header should show that the AI model is connected.

### 6. Smoke-test the model-backed analyst

```powershell
$body = @{ question = "Tell me about the total branches and their analysis" } | ConvertTo-Json
Invoke-RestMethod `
  -Uri http://127.0.0.1:8000/api/analyst/query `
  -Method Post -ContentType "application/json" -Body $body
```

Model answers can take several seconds because the LLM selects grounded tools and the result must
pass response validation.

## GitHub development workflow

The upstream repository is
<https://github.com/Rama-Marhlh/Bedashing-Network-Intelligence-UAE-Task->. After cloning it, confirm
the configured remote with:

```powershell
git remote -v
```

### Configure Git identity once

Use the name and email connected to your GitHub account:

```powershell
git config --global user.name "YOUR-GITHUB-USERNAME"
git config --global user.email "YOUR-GITHUB-EMAIL"
```

Remove `--global` if the identity should apply only to this repository.

### Download upstream changes

Before beginning new work:

```powershell
git switch main
git pull --ff-only origin main
```

### Create a branch and publish changes

```powershell
git switch -c docs/improve-technical-readme
git status
git add README.md
git diff --cached
git commit -m "docs: improve technical setup instructions"
git push -u origin docs/improve-technical-readme
```

Open a pull request on GitHub from `docs/improve-technical-readme` into `main`. If working directly
on `main` is required, use `git push origin main` after committing.

### Secret and staging checks

Before every commit:

```powershell
git check-ignore .env
git status --short
git diff --cached
```

`git check-ignore .env` must print `.env`. Confirm that `.env`, `.venv`, `node_modules`, `.next`,
temporary browser profiles, and editor/agent caches are absent from the staged changes. Never use
`git add -f .env`. Prefer adding named files over `git add .` when only a few files changed.

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

## Agentic chatbot UI with CopilotKit

The **AI Portfolio Analyst** is an agentic user interface: it can answer questions and, when the
user explicitly requests it, translate the answer into safe dashboard operations. CopilotKit
connects the React interface to this agent workflow and makes current application state and typed
frontend capabilities available at the UI boundary.

### CopilotKit integration

The application is wrapped in the CopilotKit provider from `@copilotkit/react-core/v2`. The provider
uses the local Next.js route `/api/copilotkit`, which proxies AG-UI requests to FastAPI's
`/api/agui` SSE endpoint. The custom analyst panel also calls `/api/analyst/query` directly so it can
render the project's structured `AnalystResponse` and execute its validated action plan.

The panel uses two core CopilotKit patterns:

- `useAgentContext` publishes bounded, JSON-serializable dashboard context, including the active
  page, selected branch or growth area, compared branches, recommendation filters, catchment
  duration, visible layers, and competitor filters.
- `useFrontendTool` registers typed browser capabilities such as filtering recommendations,
  selecting branches or whitespace cells, changing catchment duration, toggling map layers,
  navigating between dashboard sections, fitting the map, and resetting filters.

### Request and action lifecycle

```text
User asks a question in the analyst panel
  -> React sends the question and bounded dashboard context to FastAPI
  -> Pydantic AI asks gpt-5-mini to select the smallest relevant data tools
  -> deterministic tools read and calculate from validated app_data
  -> Pydantic validates the factual response and proposed action plan
  -> React validates every action again with a Zod discriminated union
  -> approved actions update shared dashboard state
  -> the map, filters, selections, panels, or navigation react to that state
  -> the chat reports the answer and which actions actually completed
```

This creates a shared interaction model: a branch selected on the map becomes context for the next
question, while an explicit chat request such as “show only PROTECT branches” can update the same
filter state used by the visual controls.

### Grounding and safety boundaries

- The LLM interprets intent; deterministic backend tools provide the factual values.
- The model cannot execute arbitrary browser code. It can only propose actions from the supported
  action schema.
- Informational questions produce no dashboard mutations. Actions are allowed only for explicit
  requests such as show, select, filter, open, navigate, zoom, or reset.
- Branch-specific workflows resolve the branch before querying branch data.
- Competitor catchment workflows must use the same resolved branch, duration, and competitor tier
  in both the data query and UI action.
- The backend validates the output with Pydantic, and the browser independently validates action
  names and parameters with Zod before dispatching them.
- The UI reports completed or rejected actions instead of implying that an operation succeeded.
- Recent conversation context is bounded, and full review datasets are never sent to the model.

### Example agentic interactions

| User request                                                   | Grounded behavior                                                 | Possible UI result                                       |
| -------------------------------------------------------------- | ----------------------------------------------------------------- | -------------------------------------------------------- |
| “How many SHRINK branches are there?”                          | Query recommendation data and return the current count            | No UI change                                             |
| “Show only SHRINK branches”                                    | Validate the group and create a filter action plan                | Open overview and filter branch markers                  |
| “Show direct competitors in this branch's 10-minute catchment” | Resolve the selected branch and query its catchment relationships | Select branch, set 10 minutes, filter DIRECT, show layer |
| “Compare these branches”                                       | Retrieve validated comparison metrics                             | Populate comparison state and open Performance           |
| “Show the reviewed growth candidates”                          | Query the reviewed shortlist                                      | Show the shortlist layer and fit the map                 |

The header checks FastAPI's `/health` endpoint and displays whether the AI agent is online, in
static fallback mode, or unavailable. Greetings and a small number of unambiguous aggregate answers
can be deterministic; model-backed analysis requires `mode=llm`.

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

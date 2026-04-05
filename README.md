# TaskForge - Multi-Agent Crisis Logistics Coordination System

**Google APAC Hackathon 2026 Submission**

TaskForge is a production-grade multi-agent system that coordinates supply chain crisis response using Google Gemini. Given a crisis scenario (flood, cyclone, earthquake), it runs a 4-agent pipeline to assess resources, generate a dispatch plan, execute logistics tasks, and adaptively replan when routes are disrupted.

Built with FastAPI, PostgreSQL, and Gemini 2.0 Flash. Deployed on Google Cloud Run.

**Live**: https://taskforge-888893197774.asia-south1.run.app

[![CI — Lint & Test](https://github.com/mangod12/google_apac_2026/actions/workflows/ci.yml/badge.svg)](https://github.com/mangod12/google_apac_2026/actions/workflows/ci.yml)
[![CD — Deploy to Cloud Run](https://github.com/mangod12/google_apac_2026/actions/workflows/deploy.yml/badge.svg)](https://github.com/mangod12/google_apac_2026/actions/workflows/deploy.yml)

---

## Live Demo

**Dashboard**: https://taskforge-888893197774.asia-south1.run.app

6 preset scenarios available on the dashboard — click any chip to run instantly.

```bash
curl -X POST https://taskforge-888893197774.asia-south1.run.app/execute \
  -H "Content-Type: application/json" \
  -d '{"query": "Flood in Odisha causing food shortage across 3 districts"}'
```

---

## Architecture

```
                    +-----------------------+
                    |   FastAPI REST API     |
                    |   /execute  /api/v1/*  |
                    +-----------+-----------+
                                |
                                v
                    +-----------+-----------+
                    |   OrchestratorAgent    |
                    |   (Central Coordinator)|
                    +-----------+-----------+
                                |
            +-------------------+-------------------+
            |                   |                   |
            v                   v                   v
    +-------+------+   +-------+------+   +--------+-----+
    | ResourceAgent |   | PlanningAgent|   | ExecutionAgent|
    | (Inventory +  |   | (Route +     |   | (Dispatch +   |
    |  Risk Audit)  |   |  Strategy)   |   |  Scheduling)  |
    +-------+------+   +-------+------+   +--------+-----+
            |                   |                   |
            +-------------------+-------------------+
                                |
                     (if crisis keyword detected)
                                |
                                v
                    +-----------+-----------+
                    |   ReplanningAgent     |
                    |   (Reroute + Adapt)   |
                    +-----------------------+
```

All agents use **Gemini 2.5 Flash** via function calling. Tools are exposed via **MCP (Model Context Protocol)** over SSE transport. Each agent has deterministic fallback logic that produces realistic operational output when the LLM is unavailable.

---

## What It Does

1. **ResourceAgent** audits warehouse inventory and computes shortage severity (Critical/Moderate/Low based on unit thresholds)
2. **PlanningAgent** selects the optimal source depot, compares cost and ETA across warehouses, generates a multi-step dispatch plan
3. **ExecutionAgent** creates subtasks, schedules deliveries, assigns truck counts and routes
4. **ReplanningAgent** fires when crisis keywords (flood, cyclone, earthquake, etc.) are detected - reroutes convoys, adds emergency airlifts, updates ETAs

The system returns **16 structured fields** per execution:

| Field | Description |
|-------|-------------|
| `summary` | One-line operational summary with route and reroute info |
| `crisis_context` | Extracted location, crisis type, resource, shortage, severity |
| `plan` | Strategy text with warehouse-to-destination routing |
| `tasks` | Prioritized task breakdown (critical/high/medium) |
| `schedule` | Day-by-day timeline with timestamps (Day 1 06:00, etc.) |
| `agent_flow` | Step-by-step trace of what each agent decided |
| `confidence_score` | 0.0-1.0 pipeline confidence (drops with replanning) |
| `insights` | Operational insights (cost comparisons, route risks) |
| `risk_notes` | Active risks (flooding, fuel uncertainty, cascade delays) |
| `decision_comparison` | Side-by-side warehouse cost/ETA comparison |
| `system_state` | Live telemetry: agents, decisions made, replans, confidence trend |
| `impact_analysis` | What happens *without* TaskForge (delay, unmet demand) |
| `replanning` | Reroute changes + emergency measures (when triggered) |
| `system_reliability` | Test coverage, pipeline validation status |
| `outcome_summary` | Final judge line: "300-unit shortage covered in ~4 days..." |
| `execution_time` | Wall-clock time for the full pipeline |

---

## MCP Integration (Model Context Protocol)

All 7 tools are exposed via an **MCP server** embedded in the FastAPI app using SSE transport:

| MCP Tool | Category | Description |
|----------|----------|-------------|
| `create_subtask` | Task Manager | Create subtasks under a parent task |
| `update_task_status` | Task Manager | Update task lifecycle status |
| `estimate_effort` | Task Manager | Estimate hours/days for a task |
| `knowledge_lookup` | Notes/Memory | Search stored knowledge entries |
| `schedule_delivery` | Calendar | Schedule logistics deliveries |
| `live_weather` | Data Source | Real-time weather from Open-Meteo API |
| `disaster_check` | Data Source | Flood warnings from Open-Meteo Flood API |

**MCP endpoints:**
- `GET /mcp/sse` — SSE connection for MCP clients
- `POST /mcp/messages` — MCP message handler

**How agents use MCP:** Each agent's tool calls route through an MCP client (`app/mcp_client.py`) that connects to the embedded MCP server via SSE. This proves full MCP compliance — tools are discovered, invoked, and results returned through the MCP protocol layer. Falls back to direct registry if MCP is unavailable.

```python
# Connect to TaskForge MCP server from any MCP client
from mcp.client.sse import sse_client
from mcp import ClientSession

async with sse_client("https://taskforge-888893197774.asia-south1.run.app/mcp/sse") as (r, w):
    async with ClientSession(r, w) as session:
        await session.initialize()
        tools = await session.list_tools()        # 7 tools
        result = await session.call_tool("live_weather", {"location_name": "mumbai"})
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| API | **FastAPI** + Uvicorn (async, production-grade) |
| LLM | **Google Gemini 2.5 Flash** via `google-genai` SDK |
| MCP | **Model Context Protocol** (SSE transport, 7 tools) |
| Database | **PostgreSQL 16** + SQLAlchemy 2.0 (fully async with asyncpg) |
| Migrations | Alembic |
| Frontend | Built-in HTML/CSS/JS dashboard (served by FastAPI, no separate build) |
| Testing | pytest + pytest-asyncio + httpx (34 E2E tests, 100% pass) |
| Deployment | Docker + **Google Cloud Run** |
| Language | Python 3.12 |

---

## Project Structure

```
app/
  agents/
    orchestrator.py    # Central coordinator - runs 4-agent pipeline
    resource.py        # Inventory audit + shortage computation
    planner.py         # Route selection + dispatch strategy
    execution.py       # Task creation + delivery scheduling
    replanning.py      # Emergency rerouting + plan adjustment
    base.py            # Abstract agent with function-calling loop
  api/
    routes_tasks.py    # REST endpoints (CRUD + /execute)
    routes_health.py   # Health check with DB connectivity
  db/
    models.py          # Task, AgentLog, MemoryEntry (PostgreSQL + JSONB)
    repositories.py    # Async CRUD (Repository pattern)
    database.py        # AsyncEngine + session factory
  llm/
    gemini_client.py   # Gemini SDK wrapper (Vertex AI + API key modes)
  tools/
    registry.py        # Tool registry for function calling
    task_tools.py      # create_subtask, update_status, estimate_effort
    knowledge_tool.py  # knowledge_lookup (memory search)
    calendar_tool.py   # schedule_delivery
  schemas/
    task_schemas.py    # Pydantic request/response models (16 fields)
  memory/
    context.py         # ContextManager for agent memory persistence
  static/
    index.html         # Interactive dashboard (dark theme, responsive)
  mcp_server.py        # MCP server — 7 tools via SSE transport
  mcp_client.py        # MCP client — routes agent tool calls through MCP
  config.py            # pydantic-settings (env vars + .env)
  main.py              # App entry point, startup, CORS, MCP mount, routing
tests/
  conftest.py          # Async fixtures, real PostgreSQL, session-scoped
  test_health.py       # Health + DB connectivity
  test_task_crud.py    # Create, list, get, delete tasks
  test_execute.py      # Full pipeline E2E (flood, cyclone, earthquake)
  test_agent_logs.py   # Agent log persistence
  test_validation.py   # Input validation, error handling, OpenAPI
```

---

## Local Setup

### 1. Start PostgreSQL

```bash
docker compose up db -d
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
# Set GEMINI_API_KEY or VERTEX_AI_PROJECT
```

### 4. Run

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open http://localhost:8000 for the dashboard.

### 5. Run tests

```bash
pip install pytest pytest-asyncio httpx
python -m pytest tests/ -v
```

```
34 passed in ~150s
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/execute` | Synchronous demo - runs full pipeline, returns 16-field response |
| `POST` | `/api/v1/tasks` | Async task submission (202 Accepted, background pipeline) |
| `GET` | `/api/v1/tasks` | List tasks (paginated, limit/offset) |
| `GET` | `/api/v1/tasks/{id}` | Get task with structured results |
| `GET` | `/api/v1/tasks/{id}/logs` | Agent execution logs (chronological) |
| `DELETE` | `/api/v1/tasks/{id}` | Delete task + cascade subtasks/logs |
| `GET` | `/health` | Service health + DB connectivity |
| `GET` | `/docs` | Swagger UI (auto-generated) |

---

## Deploy to Google Cloud Run

```bash
export PROJECT_ID=your-gcp-project
export REGION=asia-south1

# Build
gcloud builds submit --tag gcr.io/$PROJECT_ID/taskforge

# Deploy
gcloud run deploy taskforge \
  --image gcr.io/$PROJECT_ID/taskforge \
  --region $REGION \
  --platform managed \
  --allow-unauthenticated \
  --set-env-vars="DATABASE_URL=postgresql+asyncpg://USER:PASS@HOST:5432/taskforge" \
  --set-env-vars="VERTEX_AI_PROJECT=$PROJECT_ID" \
  --set-env-vars="VERTEX_AI_LOCATION=$REGION" \
  --set-env-vars="GEMINI_MODEL=gemini-2.0-flash" \
  --memory=1Gi --timeout=300 --min-instances=0 --max-instances=3
```

---

## CI/CD Pipeline

Two GitHub Actions workflows run automatically:

**CI — Lint & Test** (on every push and PR to `main`):
- Spins up PostgreSQL 16 service container
- Installs dependencies
- Runs all 34 E2E tests against real PostgreSQL

**CD — Deploy to Cloud Run** (on push to `main`):
- Authenticates with GCP via service account
- Builds Docker image via Cloud Build
- Deploys to Cloud Run with Cloud SQL connection
- Runs a health check to verify the deployment

```
.github/workflows/
  ci.yml      # Test pipeline — PostgreSQL + pytest
  deploy.yml  # Build + deploy to Cloud Run
```

To enable CD, add a `GCP_SA_KEY` secret in GitHub repo settings containing the service account JSON key with Cloud Run Admin, Cloud Build Editor, Cloud SQL Client, and Artifact Registry Writer roles.

---

## Key Design Decisions

**Deterministic fallbacks**: Every agent has hardcoded fallback data that produces ops-engineer quality output. The system is fully functional even without LLM access - validated by running the full pipeline with billing disabled.

**Forced replanning**: `_should_force_replan()` checks for crisis keywords (flood, cyclone, war, etc.) in the query. This guarantees replanning fires for demo scenarios regardless of LLM risk assessment.

**Rule-based crisis extraction**: Location, crisis type, resource, and severity are extracted via lookup tables + regex, not LLM. This makes crisis context deterministic and instant.

**Real decision counts**: `system_state.decisions_made` is derived from actual pipeline output (plan actions + route selections + execution tasks + replan changes), not hardcoded.

**No separate frontend build**: The dashboard is a single `index.html` served by FastAPI's `StaticFiles`. No npm, no webpack, no build step. Works in any browser.

---

## Testing

34 E2E tests against real PostgreSQL (no mocks):

- **Health**: DB connectivity verification
- **CRUD**: Create (202), list with pagination, get by ID, delete with cascade
- **Pipeline**: Full agent execution for flood/cyclone/earthquake scenarios, all 16 response fields validated
- **Replanning**: Verified crisis keywords trigger rerouting, non-crisis queries skip it
- **Validation**: Schema enforcement, UUID format, pagination bounds, empty input rejection
- **Persistence**: Tasks written to DB during pipeline, retrievable via GET

```
tests/test_health.py       2 passed
tests/test_task_crud.py    9 passed
tests/test_execute.py     11 passed
tests/test_agent_logs.py   2 passed
tests/test_validation.py  10 passed
========================= 34 passed
```

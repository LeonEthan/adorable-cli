# Milestones & Issue List (Agno-First)

This document breaks `ROADMAP.md` into actionable milestones and GitHub-style issues.

Conventions:
- **P0/P1/P2**: priority
- **DoD**: Definition of Done
- **Deps**: dependencies

---

## Milestone 0 — Roadmap Foundations (Prep)
### Issue: Define configuration spec & file layout (P0)
- **Goal**: Agree on config formats and where new modules live.
- **Scope**:
  - Decide: core config JSON, teams/workflows YAML
  - Define directories:
    - `src/adorable_cli/os/`
    - `src/adorable_cli/teams/`
    - `src/adorable_cli/workflows/`
    - `src/adorable_cli/knowledge/`
    - `~/.adorable/{teams,workflows,skills,tools,commands}/`
- **Decisions**:
  - Core config file (canonical): `~/.adorable/config.json`
  - Legacy config file (compat): `~/.adorable/config` (`KEY=VALUE`)
  - Precedence: CLI flags > env vars > `config.json` > `config`
  - Team config: `~/.adorable/teams/*.yaml`
  - Workflow config: `~/.adorable/workflows/*.yaml`
- **DoD**:
  - `docs/` or `ROADMAP.md` updated with final structure
  - Sample config snippets included
  - Skeleton modules exist for Phase 1–4 (`os/`, `teams/`, `workflows/`, `knowledge/`)

Sample `~/.adorable/config.json`:

```json
{
  "openai": {
    "api_key": "sk-...",
    "base_url": "https://api.openai.com/v1"
  },
  "models": {
    "default": "gpt-4o",
    "fast": "gpt-4o-mini",
    "vlm": "gpt-4o"
  },
  "confirm_mode": "ask",
  "server": {
    "host": "0.0.0.0",
    "port": 7777
  }
}
```

Sample `~/.adorable/teams/coding.yaml` (schema placeholder; will be finalized in Milestone 4):

```yaml
name: coding
agents:
  - planner
  - coder
  - tester
```

Sample `~/.adorable/workflows/research.yaml` (schema placeholder; will be finalized in Milestone 6):

```yaml
name: research
steps:
  - search
  - analyze
  - write
```

---

## Milestone 1 — AgentOS Server Mode (Phase 1) (P0)
### Issue: Add AgentOS wrapper module (P0)
- **Goal**: Wrap existing `build_agent()` into an AgentOS app.
- **Tasks**:
  - Create `src/adorable_cli/os/server.py`
  - Create `create_agent_os()` that builds the agent and returns `AgentOS`
  - Expose `app = agent_os.get_app()`
- **DoD**:
  - Importing module exposes a valid FastAPI app
- **Deps**:
  - Confirm Agno version compatibility in `pyproject.toml`

### Issue: Add `ador serve` Typer command (P0)
- **Goal**: Start local AgentOS server from CLI.
- **Flags**:
  - `--host`, `--port`, `--reload`
  - Optional: `--daemon` (can be deferred)
- **DoD**:
  - `ador serve` starts server successfully
  - Browser can open `http://localhost:<port>`
- **Deps**:
  - AgentOS wrapper module

### Issue: Add server config plumbing (P0)
- **Goal**: Allow configuration of server behavior.
- **Tasks**:
  - Extend config layer to store server settings
  - Choose defaults: port 7777, host 0.0.0.0
- **DoD**:
  - Running `ador serve` respects config

### Issue: Add minimal health check & smoke tests (P1)
- **Goal**: Basic confidence that server boots.
- **Tasks**:
  - Add a simple unit/integration test (if test infra supports)
  - Or add `ador serve --check` mode that pings `/config`
- **DoD**:
  - CI/local run can validate server starts

---

## Milestone 2 — Hybrid CLI/Server Runtime (Phase 1) (P0)
### Issue: Implement `ador attach <url>` (P1)
- **Goal**: Connect CLI to a running AgentOS server.
- **Tasks**:
  - Define client transport (HTTP + SSE)
  - Decide minimal set of operations: send message, stream tokens, list sessions
- **DoD**:
  - CLI can drive remote AgentOS instance
- **Deps**:
  - AgentOS server mode working

### Issue: Shared session semantics between CLI and AgentOS (P1)
- **Goal**: Ensure local CLI sessions map to AgentOS sessions.
- **Tasks**:
  - Align session id format and persistence
  - Decide DB handling (shared SQLite vs server-owned DB)
- **DoD**:
  - Sessions created from CLI are visible in AgentOS UI (or clearly documented)

---

## Milestone 3 — Team System MVP (Phase 2) (P0)
### Issue: Create team builder module (P0)
- **Goal**: Provide built-in teams based on Agno `Team`.
- **Teams**:
  - `coding`: planner + coder + tester
  - `research`: searcher + analyst + writer
  - `planning`: plan-only/read-only behaviors
- **DoD**:
  - Teams can be instantiated and run
- **Deps**:
  - Agent builder refactor may be needed to create specialized agents

### Issue: Add `--team` option to CLI entry (P0)
- **Goal**: Select team at runtime.
- **Tasks**:
  - Add `--team` global option
  - Route interactive run loop to team runner
- **DoD**:
  - `ador --team research` works

### Issue: Add `ador teams list` command (P1)
- **Goal**: Discoverability.
- **DoD**:
  - Lists built-in and configured teams

---

## Milestone 4 — Team Configuration (Phase 2) (P1)
### Issue: Load teams from `~/.adorable/teams/*.yaml` (P1)
- **Goal**: User-defined team composition.
- **Tasks**:
  - YAML schema for team files
  - Validate and surface errors nicely
- **DoD**:
  - A custom team YAML can be loaded and used

### Issue: Permissions policy per agent/team (P1)
- **Goal**: Enforce read-only or confirmation-based modes.
- **Tasks**:
  - Map tool permissions (e.g., `ShellTools` restricted)
  - Align with current `requires_confirmation` shell behavior
- **DoD**:
  - Plan/read-only modes cannot write files unless allowed

---

## Milestone 5 — Workflow MVP (Phase 3) (P1)
### Issue: Create workflow registry (P1)
- **Goal**: Central place to register workflows.
- **Tasks**:
  - `src/adorable_cli/workflows/registry.py`
  - Register built-in workflows
- **DoD**:
  - `list_workflows()` returns built-ins

### Issue: Built-in workflow: `research` (P1)
- **Goal**: Demonstrate workflow value quickly.
- **Steps**:
  - search -> analyze -> write
- **DoD**:
  - Running workflow produces structured output

### Issue: Built-in workflow: `code-review` (P1)
- **Goal**: Automated review pipeline.
- **Steps**:
  - diff parse -> run tests -> summarize findings
- **DoD**:
  - Produces markdown report

### Issue: CLI commands for workflows (P1)
- **Commands**:
  - `ador workflows list`
  - `ador workflow run <name> --input ...`
- **DoD**:
  - Users can run workflows from CLI

---

## Milestone 6 — Workflow Configuration (Phase 3) (P2)
### Issue: Load workflows from `~/.adorable/workflows/*.yaml` (P2)
- **Goal**: User-defined workflows.
- **Tasks**:
  - YAML schema for steps
  - Map steps to agents/teams
- **DoD**:
  - Custom workflow can be executed

---

## Milestone 7 — Knowledge Base MVP (Phase 4) (P1)
### Issue: Knowledge manager module (P1)
- **Goal**: Create/search/update KB.
- **Tasks**:
  - `src/adorable_cli/knowledge/manager.py`
  - Support local SQLite-based KB first
- **DoD**:
  - KB can be created and searched

### Issue: CLI KB commands (P1)
- **Commands**:
  - `ador kb create <name> <path>`
  - `ador kb update <name>`
  - `ador kb search <name> <query>`
- **DoD**:
  - Basic KB lifecycle works

### Issue: pgvector backend support (P2)
- **Goal**: Production-ready KB.
- **DoD**:
  - Can switch backend via config

---

## Milestone 8 — Extensibility (Phase 5) (P2)
### Issue: Skills loader (P2)
- **Goal**: Load skills from `~/.adorable/skills/`, optionally `.claude/skills/`.
- **DoD**:
  - Skills appear in agent context and are callable

### Issue: Custom tools loader (P2)
- **Goal**: Load `Toolkit` subclasses from `~/.adorable/tools/`.
- **DoD**:
  - Tools are registered and callable

### Issue: Custom commands loader (P2)
- **Goal**: Markdown frontmatter + prompt text commands.
- **DoD**:
  - Users can run `/my-command` in interactive mode

---

## Milestone 9 — Production Features (Phase 6) (P2)
### Issue: Evals CLI (P2)
- **Goal**: Run agent evaluations.
- **Commands**:
  - `ador eval run`
  - `ador eval report`
- **DoD**:
  - Can execute at least one eval suite

### Issue: Observability & metrics documentation (P2)
- **Goal**: Make AgentOS UI observability usable.
- **DoD**:
  - Document how to view metrics and traces

### Issue: Database migrations and upgrade path (P2)
- **Goal**: Safe schema evolution.
- **DoD**:
  - Migration mechanism defined and tested

---

## Optional / Deferred
### Issue: LSP integration (P3)
- **Status**: intentionally deferred
- **Rationale**: maximize Agno-native differentiation first

### Issue: Desktop app wrapper (P3)
- **Status**: optional
- **Rationale**: AgentOS UI covers most UI needs

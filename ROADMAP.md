# Adorable CLI Roadmap (Agno-First)

## Overview
Adorable CLI should leverage Agno’s native strengths (AgentOS, Teams, Workflows, Knowledge Base, Evals) instead of duplicating OpenCode’s architecture. The product becomes a **terminal-first AgentOS**: interactive CLI + production-ready server/UI.

---

## Guiding Principles
- **Agno-native first**: Maximize AgentOS/Team/Workflow features before building custom infrastructure.
- **Dual-mode**: CLI and AgentOS server should share the same agent core.
- **Production-ready**: FastAPI runtime, SSE streaming, monitoring, and database flexibility.
- **Extensible**: Skills, tools, workflows, and teams should be configurable.

---

## Phase 1 — AgentOS Integration (P0)
### Goals
- Make Adorable CLI run as an AgentOS server.
- Enable web UI (AgentOS UI), REST API, SSE streaming.
- Keep CLI experience intact.

### Deliverables
- `ador serve` command
- AgentOS app builder wrapper
- Hybrid CLI/Server runtime
- Server config in `~/.adorable/config.json`

### Implementation Plan
1. **AgentOS wrapper**
   - Create `src/adorable_cli/os/server.py`
   - Wrap existing `build_agent()` into `AgentOS(agents=[agent])`
   - Expose `app = agent_os.get_app()`

2. **CLI command**
   - Add `ador serve` (Typer command)
   - Flags: `--port`, `--host`, `--reload`, `--daemon`

3. **Config integration**
   - Add server config section
   - Default port 7777

4. **Smoke test**
   - `ador serve` → open http://localhost:7777

---

## Phase 2 — Team System (P0)
### Goals
- Use Agno’s Team abstraction for multi-agent collaboration.
- Provide built-in teams for common workflows.

### Deliverables
- Team builder module
- Built-in teams: `coding`, `research`, `planning`
- CLI support: `ador --team` and `/team`

### Implementation Plan
1. **Team builder**
   - `src/adorable_cli/teams/builder.py`
   - Define `create_coding_team()`, `create_research_team()`

2. **Team config**
   - Allow YAML config in `~/.adorable/teams/`

3. **CLI integration**
   - Add `--team` option and `ador teams list`

---

## Phase 3 — Workflow Orchestration (P1)
### Goals
- Enable reusable workflows for complex tasks.
- Leverage Agno workflows (steps, conditions, parallelism).

### Deliverables
- Workflow registry
- Built-in workflows: `code-review`, `research`, `deploy`
- CLI: `ador workflow run <name>`

### Implementation Plan
1. **Workflow module**
   - `src/adorable_cli/workflows/registry.py`
   - Register built-in workflows

2. **Workflow CLI**
   - Commands: `ador workflows list`, `ador workflow run`

3. **YAML workflow config**
   - Load from `~/.adorable/workflows/`

---

## Phase 4 — Knowledge Base (P1)
### Goals
- Add RAG capability with Agno Knowledge.
- Support multiple vector DB backends.

### Deliverables
- Knowledge manager
- CLI: `ador kb create/search/update`
- Auto indexing for docs

### Implementation Plan
1. **Knowledge manager**
   - `src/adorable_cli/knowledge/manager.py`
   - Use `agno.knowledge.KnowledgeBase`

2. **Vector DB support**
   - SQLite for local
   - PostgreSQL/pgvector for production

3. **CLI interface**
   - `ador kb create <name> <path>`
   - `ador kb search <name> <query>`

---

## Phase 5 — Extensibility (P2)
### Goals
- User-defined skills, tools, commands.

### Deliverables
- Skills loader (`~/.adorable/skills/`)
- Tool loader (`~/.adorable/tools/`)
- Command loader (`~/.adorable/commands/`)

### Implementation Plan
1. **Skills**
   - Use `agno.skills.Skills`
   - Support `.claude/skills` compatibility

2. **Tools**
   - Auto-import Toolkit subclasses

3. **Commands**
   - Markdown frontmatter + prompt text

---

## Phase 6 — Production Features (P2)
### Goals
- Monitoring, evaluation, and reliability.

### Deliverables
- Evals CLI
- Metrics view in AgentOS UI
- Database migrations

### Implementation Plan
1. **Evals**
   - Provide `ador eval run` and `ador eval report`

2. **Observability**
   - Use AgentOS built-in metrics

---

## Priority Matrix
### Immediate (Q1 2026)
- AgentOS integration
- Team system

### Short Term (Q2 2026)
- Workflows
- Knowledge base

### Mid Term (Q3 2026)
- Extensibility (skills/tools/commands)

### Long Term (Q4 2026+)
- Evals + Monitoring
- Multi-interface support (Slack/WhatsApp)

---

## Key Decisions
- **LSP is low priority**: focus on Agno-native strengths.
- **Desktop app not required**: AgentOS UI covers visual needs.
- **JSON config for core; YAML for teams/workflows**.
- **Config migration**: `~/.adorable/config.json` is canonical; `~/.adorable/config` remains for compatibility.

---

## Next Steps
1. Implement `ador serve` with AgentOS wrapper.
2. Add team builder and basic team CLI support.
3. Publish v1.0.0 (AgentOS-native CLI).

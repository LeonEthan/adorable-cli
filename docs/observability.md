# Observability and Metrics

Adorable CLI leverages AgentOS UI for observability. This guide explains how to view metrics and traces.

## Viewing Metrics

1. Start the AgentOS server:
   ```bash
   ador serve
   ```

2. Open the AgentOS UI (default: http://localhost:7777, or as configured).

3. Navigate to the **Metrics** dashboard.
   - **Request Rate**: Number of requests per minute.
   - **Latency**: Average response time.
   - **Error Rate**: Percentage of failed requests.
   - **Token Usage**: Tokens consumed by LLM calls.

## Tracing

AgentOS automatically traces agent execution steps.

1. In the AgentOS UI, go to **Sessions**.
2. Click on a specific session ID.
3. View the **Trace** tab to see the sequence of tool calls, thoughts, and responses.

## Configuration

Metrics are enabled by default in `ador serve` mode.

To customize logging levels:
```bash
export AGNO_LOG_LEVEL=DEBUG
ador serve
```

## Database

The observability data is stored in the underlying database (SQLite by default).
See `docs/database.md` (if available) or check `~/.adorable/memory.db`.
You can override the path with `ADORABLE_DB_PATH` (or `db.path` in `config.json`) to share
sessions between CLI and `ador serve`.

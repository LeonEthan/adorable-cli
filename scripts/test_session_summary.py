import os
from pathlib import Path

from adorable_cli.main import CONFIG_FILE, build_agent

# Load config
cfg_path = CONFIG_FILE
if Path(cfg_path).exists():
    for line in Path(cfg_path).read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())
# Ensure FAST_MODEL_ID
os.environ.setdefault("FAST_MODEL_ID", os.environ.get("ADORABLE_FAST_MODEL_ID", "gpt-5-mini"))
agent = build_agent()

# two turns (keep simple to avoid tool calls/errors)
agent.run("请用一句中文概括本项目目标。", stream=False)
agent.run("再用一句中文概括：上下文窗口守卫的作用。", stream=False)

# Create session summary via the manager
summary_obj = agent.session_summary_manager.create_session_summary(agent)

def _extract_summary_text(s):
    # Handle both string and object return types robustly
    if s is None:
        return ""
    if isinstance(s, str):
        return s
    # Try common attributes
    for attr in ("text", "content", "summary", "value"):
        v = getattr(s, attr, None)
        if isinstance(v, str) and v.strip():
            return v
    # Fallback to repr
    return str(s)

summary_text = _extract_summary_text(summary_obj)
print("\n--- SUMMARY ---\n")
print(summary_text.strip())

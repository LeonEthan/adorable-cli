from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from adorable_cli import config as cfg
from adorable_cli.settings import settings


class KnowledgeManager:
    """Minimal knowledge base manager used by CLI commands."""

    def __init__(self, name: str = "default") -> None:
        self.name = name
        self.backend = settings.kb_backend
        self.kb_path = cfg.CONFIG_PATH / "knowledge" / name
        self.pgvector_dsn = settings.kb_pgvector_dsn
        self.pgvector_table = settings.kb_pgvector_table or "adorable_kb"

        if self.backend == "pgvector" and not self.pgvector_dsn:
            raise ValueError("pgvector backend requires a DSN (use --pgvector-dsn)")

    def load_directory(self, path: Path) -> int:
        """Index a directory by storing file contents in a local index."""
        docs: list[dict[str, Any]] = []
        for file_path in path.rglob("*"):
            if not file_path.is_file():
                continue
            try:
                content = file_path.read_text(encoding="utf-8")
            except Exception:
                continue
            docs.append({"name": str(file_path), "content": content})

        self.kb_path.mkdir(parents=True, exist_ok=True)
        index_path = self.kb_path / "index.json"
        index_path.write_text(json.dumps(docs, ensure_ascii=False, indent=2), encoding="utf-8")
        return len(docs)

    def search(self, query: str, num_results: int = 5) -> list[dict[str, Any]]:
        """Search the local index with a simple substring match."""
        index_path = self.kb_path / "index.json"
        if not index_path.exists():
            return []

        try:
            data = json.loads(index_path.read_text(encoding="utf-8"))
        except Exception:
            return []

        needle = query.lower()
        results: list[dict[str, Any]] = []
        for doc in data:
            content = str(doc.get("content", ""))
            hay = content.lower()
            if needle in hay:
                score = float(hay.count(needle))
                results.append({"name": doc.get("name", "unknown"), "content": content, "score": score})

        results.sort(key=lambda item: item.get("score", 0.0), reverse=True)
        return results[:num_results]

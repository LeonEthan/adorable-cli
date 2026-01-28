from pathlib import Path
from typing import Any, Dict, List, Optional

from agno.knowledge.knowledge import Knowledge
from agno.knowledge.embedder.openai import OpenAIEmbedder
from agno.vectordb.lancedb import LanceDb, SearchType

from adorable_cli.config import CONFIG_PATH
from adorable_cli.settings import settings

class KnowledgeManager:
    def __init__(self, name: str, base_dir: Optional[Path] = None):
        self.name = name
        self.base_dir = base_dir or CONFIG_PATH / "knowledge"
        self.kb_path = self.base_dir / name
        self.db_path = self.kb_path / "lancedb"
        self.kb_path.mkdir(parents=True, exist_ok=True)
        
        self.vector_db = self._build_vector_db(name)
        
        self.knowledge = Knowledge(
            vector_db=self.vector_db,
        )

    def _build_vector_db(self, table_name: str):
        backend = (settings.kb_backend or "lancedb").strip().lower()
        embedder = OpenAIEmbedder()

        if backend in {"pgvector", "pg", "postgres", "postgresql"}:
            dsn = (settings.kb_pgvector_dsn or "").strip()
            if not dsn:
                raise ValueError(
                    "pgvector backend requires a DSN. Set KB_PGVECTOR_DSN or "
                    "ADORABLE_KB_PGVECTOR_DSN (or knowledge.pgvector.dsn in config.json)."
                )
            table = (settings.kb_pgvector_table or table_name).strip() or table_name
            return self._build_pgvector_db(table=table, dsn=dsn, embedder=embedder)

        return LanceDb(
            table_name=table_name,
            uri=str(self.db_path),
            embedder=embedder,
            search_type=SearchType.vector,
        )

    def _build_pgvector_db(self, *, table: str, dsn: str, embedder: OpenAIEmbedder):
        try:
            from agno.vectordb.pgvector import PgVectorDb
        except Exception as e:
            raise RuntimeError(
                "pgvector backend is not available. Install the pgvector extra for agno and "
                "ensure database drivers are installed."
            ) from e

        candidates = [
            {"table_name": table, "connection_string": dsn},
            {"table_name": table, "dsn": dsn},
            {"table_name": table, "uri": dsn},
            {"table_name": table, "conn_str": dsn},
            {"table": table, "dsn": dsn},
        ]

        last_error: Exception | None = None
        for kwargs in candidates:
            try:
                return PgVectorDb(
                    **kwargs,
                    embedder=embedder,
                    search_type=SearchType.vector,
                )
            except TypeError as e:
                last_error = e
                continue

        raise RuntimeError(
            "Unable to initialize PgVectorDb with the provided DSN. "
            "Check your agno version and pgvector configuration."
        ) from last_error

    def load_directory(self, path: Path, extensions: List[str] = None) -> int:
        """
        Recursively load files from a directory into the knowledge base.
        Returns the number of files indexed.
        """
        path = Path(path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"Path not found: {path}")
            
        if extensions is None:
            extensions = [".md", ".txt", ".pdf", ".json", ".py"]

        count = 0
        if path.is_file():
            if path.suffix.lower() in extensions:
                self.knowledge.add_content(path=path, upsert=True)
                count = 1
        else:
            for file_path in path.rglob("*"):
                if file_path.is_file() and file_path.suffix.lower() in extensions:
                    try:
                        # Skip hidden files
                        if file_path.name.startswith("."):
                            continue
                        
                        self.knowledge.add_content(path=file_path, upsert=True)
                        count += 1
                    except Exception as e:
                        # Log error but continue
                        print(f"Failed to index {file_path}: {e}")
        return count

    def search(self, query: str, num_results: int = 5) -> List[Dict[str, Any]]:
        """
        Search the knowledge base.
        """
        results = self.knowledge.search(query=query, max_results=num_results)
        output = []
        for r in results:
            # Helper to extract relevant fields from Document object
            content = getattr(r, "content", str(r))
            meta_data = getattr(r, "meta_data", {})
            score = getattr(r, "score", 0.0)
            name = getattr(r, "name", "unknown")
            
            output.append({
                "name": name,
                "content": content,
                "meta_data": meta_data,
                "score": score
            })
        return output
        
    def delete(self):
        """Delete the knowledge base (files)."""
        import shutil
        if self.kb_path.exists():
            shutil.rmtree(self.kb_path)

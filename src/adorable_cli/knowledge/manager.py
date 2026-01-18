import os
from pathlib import Path
from typing import List, Optional, Dict, Any

from agno.knowledge.knowledge import Knowledge
from agno.vectordb.lancedb import LanceDb, SearchType
from agno.knowledge.embedder.openai import OpenAIEmbedder
from adorable_cli.config import CONFIG_PATH

class KnowledgeManager:
    def __init__(self, name: str, base_dir: Optional[Path] = None):
        self.name = name
        self.base_dir = base_dir or CONFIG_PATH / "knowledge"
        self.kb_path = self.base_dir / name
        self.db_path = self.kb_path / "lancedb"
        self.kb_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize Vector DB
        # Note: We rely on standard OpenAI embeddings for now.
        # Future work: make embedder configurable via config.json
        self.vector_db = LanceDb(
            table_name=name,
            uri=str(self.db_path),
            embedder=OpenAIEmbedder(),
            search_type=SearchType.vector,
        )
        
        self.knowledge = Knowledge(
            vector_db=self.vector_db,
        )

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

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Settings:
    """Central configuration management."""

    # API Configuration
    api_key: Optional[str] = field(default=None)
    base_url: Optional[str] = field(default=None)
    model_id: str = field(default="gpt-4o")
    
    # Advanced Model Configuration
    fast_model_id: Optional[str] = field(default=None)
    vlm_model_id: Optional[str] = field(default=None)

    # Debugging
    debug_mode: bool = field(default=False)
    debug_level: Optional[int] = field(default=None)

    # Paths
    config_path: Path = field(default=Path.home() / ".adorable")
    
    @property
    def mem_db_path(self) -> Path:
        return self.config_path / "memory.db"

    @classmethod
    def from_env(cls) -> "Settings":
        """Load settings from environment variables."""
        return cls(
            api_key=os.environ.get("OPENAI_API_KEY") or os.environ.get("API_KEY"),
            base_url=os.environ.get("OPENAI_BASE_URL") or os.environ.get("BASE_URL"),
            model_id=os.environ.get("DEEPAGENTS_MODEL_ID") or os.environ.get("MODEL_ID", "gpt-4o"),
            fast_model_id=os.environ.get("DEEPAGENTS_FAST_MODEL_ID") or os.environ.get("FAST_MODEL_ID"),
            vlm_model_id=os.environ.get("DEEPAGENTS_VLM_MODEL_ID") or os.environ.get("VLM_MODEL_ID"),
            debug_mode=os.environ.get("AGNO_DEBUG", "").lower() in ("1", "true", "yes", "on"),
            debug_level=int(os.environ.get("AGNO_DEBUG_LEVEL")) if os.environ.get("AGNO_DEBUG_LEVEL") else None,
        )

    def reload_from_env(self) -> None:
        """Reload settings from environment variables in-place.
        
        This updates the existing Settings instance rather than creating a new one,
        ensuring all modules that imported the settings object see the updated values.
        """
        self.api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("API_KEY")
        self.base_url = os.environ.get("OPENAI_BASE_URL") or os.environ.get("BASE_URL")
        self.model_id = os.environ.get("DEEPAGENTS_MODEL_ID") or os.environ.get("MODEL_ID", "gpt-4o")
        self.fast_model_id = os.environ.get("DEEPAGENTS_FAST_MODEL_ID") or os.environ.get("FAST_MODEL_ID")
        self.vlm_model_id = os.environ.get("DEEPAGENTS_VLM_MODEL_ID") or os.environ.get("VLM_MODEL_ID")
        self.debug_mode = os.environ.get("AGNO_DEBUG", "").lower() in ("1", "true", "yes", "on")
        self.debug_level = int(os.environ.get("AGNO_DEBUG_LEVEL")) if os.environ.get("AGNO_DEBUG_LEVEL") else None


# Global settings instance
settings = Settings.from_env()

def reload_settings():
    """Reload settings from environment variables.
    
    Updates the existing global settings instance in-place so all modules
    that have imported settings will see the updated values.
    """
    settings.reload_from_env()

"""Application settings loaded from environment / .env."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    app_name: str = "DevOps Copilot"
    debug: bool = True
    mock_mode: bool = True
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    database_url: str = f"sqlite+aiosqlite:///{DATA_DIR / 'devops_copilot.db'}"

    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    prefer_ollama: bool = False

    chroma_persist_dir: str = str(DATA_DIR / "chroma")
    chroma_collection: str = "failure_knowledge"
    auto_seed_knowledge: bool = True

    github_webhook_secret: str = ""
    github_token: str = ""
    github_repo_owner: str = ""
    github_repo_name: str = ""

    slack_bot_token: str = ""
    slack_channel_id: str = ""

    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    # auto | hash | sentence-transformers — use "hash" on Render free Docker
    embedding_backend: str = "auto"

    @property
    def cors_origin_list(self) -> list[str]:
        raw = [o.strip() for o in self.cors_origins.split(",") if o.strip()]
        if "*" in raw:
            return ["*"]
        return raw

    @property
    def use_groq(self) -> bool:
        return bool(self.groq_api_key) and not self.mock_mode

    @property
    def use_llm(self) -> bool:
        """True when Groq is configured, or caller will try Ollama when not in mock."""
        if self.mock_mode:
            return False
        return self.use_groq or self.prefer_ollama

    @property
    def llm_backend(self) -> str:
        if self.mock_mode:
            return "mock"
        if self.prefer_ollama and not self.use_groq:
            return "ollama"
        if self.use_groq:
            return "groq"
        if self.prefer_ollama:
            return "ollama"
        return "mock"


@lru_cache
def get_settings() -> Settings:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return Settings()

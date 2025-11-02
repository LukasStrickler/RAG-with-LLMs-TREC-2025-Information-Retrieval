"""
Configuration management for the evaluation CLI.
"""

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

RetrievalMode = Literal["lexical", "vector", "hybrid"]


class APIConfig(BaseModel):
    """API configuration."""

    base_url: str = Field(default="http://localhost:8000", description="API base URL")
    api_key: SecretStr | None = Field(
        default=None, description="API key for authentication"
    )
    timeout: int = 30
    max_retries: int = 3
    concurrency: int = 5


class CLIRetrievalConfig(BaseModel):
    """CLI retrieval configuration (different from shared RetrievalConfig)."""

    top_k: int = Field(default=100, alias="top_k")
    mode: RetrievalMode = "hybrid"


class PathsConfig(BaseModel):
    """Path configuration."""

    project_root: str | None = None
    data_dir: str = ".data/trec_rag_assets"
    output_dir: str = "backend/eval/artifacts"
    topics: dict[str, str] = Field(default_factory=dict)
    qrels: dict[str, str | None] = Field(default_factory=dict)
    baselines: dict[str, str] = Field(default_factory=dict)


class PerformanceLevel(BaseModel):
    """Performance level configuration."""

    ndcg_10: float
    map_100: float
    mrr_10: float


class ScoreGeneration(BaseModel):
    """Score generation parameters."""

    seed: int = 42
    score_range: tuple[float, float] = (0.0, 1.0)
    relevance_bias: float = 0.3
    position_decay: float = 0.1


class MockConfig(BaseModel):
    """Mock system configuration."""

    performance_levels: dict[str, PerformanceLevel] = Field(default_factory=dict)
    score_generation: ScoreGeneration = Field(default_factory=ScoreGeneration)


class MetricsConfig(BaseModel):
    """Metrics configuration."""

    primary: str = "ndcg_cut_10"
    cutoffs: list[int] = [10, 25, 50, 100]
    targets: dict[str, float] = Field(default_factory=dict)
    custom: list[str] = Field(default_factory=list)


class TrecEvalConfig(BaseModel):
    """trec_eval configuration."""

    binary_path: str = "trec_eval"
    flags: list[str] = ["-c"]
    metrics: list[str] = Field(default_factory=list)


class LoggingConfig(BaseModel):
    """Logging configuration."""

    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


class Config(BaseSettings):
    """Main configuration class."""

    model_config = SettingsConfigDict(
        env_prefix="",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore extra fields from .env
    )

    # Load API key directly from .env
    api_key: SecretStr | None = Field(default=None, description="API key from .env")

    api: APIConfig = Field(default_factory=APIConfig)
    retrieval: CLIRetrievalConfig = Field(default_factory=CLIRetrievalConfig)
    paths: PathsConfig = Field(default_factory=PathsConfig)
    mock: MockConfig = Field(default_factory=MockConfig)
    metrics: MetricsConfig = Field(default_factory=MetricsConfig)
    trec_eval: TrecEvalConfig = Field(default_factory=TrecEvalConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    @classmethod
    def load(cls, config_path: Path | None = None) -> "Config":
        """Load configuration from YAML file and environment variables."""
        if config_path is None:
            # First check environment variable
            import os

            env_config_path = os.getenv("EVAL_CONFIG_PATH")
            if env_config_path:
                config_path = Path(env_config_path)
            else:
                # Fallback: Find config.yaml relative to the eval directory (parent of eval_cli)
                # This is a development convenience - in production, EVAL_CONFIG_PATH should be set
                current_dir = Path(__file__).parent.parent
                config_path = current_dir / "config.yaml"
                # Warn if using heuristic in non-dev environment
                import logging

                dev_mode = os.getenv("DEV", "").lower() in ("1", "true", "yes")
                if not dev_mode:
                    logger = logging.getLogger(__name__)
                    logger.warning(
                        f"Using heuristic config path: {config_path}. "
                        "Set EVAL_CONFIG_PATH environment variable for explicit configuration."
                    )

        if not config_path.exists():
            raise FileNotFoundError(
                f"Configuration file not found: {config_path}\n"
                "Please set EVAL_CONFIG_PATH environment variable or provide explicit config_path."
            )

        with open(config_path, encoding="utf-8") as f:
            config_data = yaml.safe_load(f)

        # Auto-detect project root if not set
        if not config_data.get("paths", {}).get("project_root"):
            import os

            # First check environment variable
            env_project_root = os.getenv("PROJECT_ROOT")
            if env_project_root:
                project_root = Path(env_project_root)
                # Validate the path exists and contains expected directories
                if not project_root.exists():
                    raise RuntimeError(
                        f"PROJECT_ROOT environment variable points to non-existent path: {project_root}"
                    )
                if (
                    not (project_root / "shared").exists()
                    or not (project_root / "backend").exists()
                ):
                    raise RuntimeError(
                        f"PROJECT_ROOT path {project_root} does not contain expected 'shared' and 'backend' directories"
                    )
            else:
                # Auto-detect only in development mode
                dev_mode = os.getenv("DEV", "").lower() in ("1", "true", "yes")
                if not dev_mode:
                    raise RuntimeError(
                        "PROJECT_ROOT environment variable must be set in production. "
                        "Set DEV=1 to enable auto-detection for development."
                    )
                # Auto-detect with validation
                project_root = cls._find_project_root()
                # Warn when using auto-detection
                import logging

                logger = logging.getLogger(__name__)
                logger.warning(
                    f"Auto-detected project root: {project_root}. "
                    "Set PROJECT_ROOT environment variable for explicit configuration."
                )
            if "paths" not in config_data:
                config_data["paths"] = {}
            config_data["paths"]["project_root"] = str(project_root)

        # Create config instance
        config_instance = cls(**config_data)

        # Inject API key from .env into nested api config
        if config_instance.api_key:
            config_instance.api.api_key = (
                config_instance.api_key
            )  # SecretStr is copied directly

        # Override API base URL from environment variable if set
        import os

        if api_base_url := os.getenv("API_BASE_URL"):
            config_instance.api.base_url = api_base_url

        return config_instance

    @staticmethod
    def _find_project_root() -> Path:
        """Find project root by looking for 'shared' and 'backend' directories."""
        current = Path(__file__).parent

        # Walk up directories looking for project root
        while current != current.parent:
            # Check if this is the main project root (has shared/ directory)
            if (current / "shared").exists() and (current / "backend").exists():
                return current
            current = current.parent

        # No valid project root found - raise explicit error
        error_msg = (
            f"Could not auto-detect project root. "
            f"Tried paths from: {Path(__file__).parent}\n"
            "Please set PROJECT_ROOT environment variable explicitly."
        )
        raise RuntimeError(error_msg)

    def get_project_root(self) -> Path:
        """Get project root path."""
        if self.paths.project_root:
            return Path(self.paths.project_root)
        return self._find_project_root()

    def get_data_path(self, relative_path: str) -> Path:
        """Get absolute path to data file."""
        project_root = self.get_project_root()
        return project_root / self.paths.data_dir / relative_path

    def get_output_path(self, relative_path: str) -> Path:
        """Get absolute path to output file."""
        project_root = self.get_project_root()
        return project_root / self.paths.output_dir / relative_path

    def model_dump(self, include_sensitive: bool = False) -> dict[str, Any]:
        """
        Dump configuration as dictionary.

        By default, the root-level api_key field is excluded from the output
        for security reasons. This prevents accidental exposure of sensitive
        credentials in logs, metadata snapshots, or serialized configurations.

        Args:
            include_sensitive: If True, includes the root-level api_key field.
                Must be used with caution and only in access-controlled contexts
                (e.g., secure debugging or testing environments). Defaults to False.

        Returns:
            Dictionary containing configuration sections (api, retrieval, paths, etc.).
            The root-level api_key field is excluded unless include_sensitive=True.
        """
        # Use Pydantic's built-in dump, which handles SecretStr redaction
        exclude_set = set() if include_sensitive else {"api_key"}
        return super().model_dump(exclude=exclude_set)

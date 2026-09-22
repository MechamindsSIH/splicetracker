"""Application configuration using Pydantic Settings."""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """SpliceTracker application settings loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Camera settings
    CAMERA_INDEX: int = 0
    CAMERA_WIDTH: int = 1280
    CAMERA_HEIGHT: int = 720
    CAMERA_FPS: int = 30

    # Sensor enable flags
    THERMAL_ENABLED: bool = True
    CONDUCTIVE_ENABLED: bool = True
    MECHANICAL_ENABLED: bool = True

    # Database
    DATABASE_URL: str = "sqlite:///./data/splicetracker.db"

    # Belt parameters
    BELT_SPEED: float = 2.0  # m/s
    BELT_LENGTH: float = 100.0  # meters

    # Simulation
    SIMULATION_MODE: bool = True

    # Logging
    LOG_LEVEL: str = "INFO"

    # WebSocket
    WS_HEARTBEAT: int = 5  # seconds

    # Frame buffer
    FRAME_BUFFER_SIZE: int = 100

    # Event processing window
    EVENT_WINDOW_MS: int = 500

    @property
    def async_database_url(self) -> str:
        """Convert the database URL to an async-compatible URL for aiosqlite."""
        url = self.DATABASE_URL
        if url.startswith("sqlite:///"):
            return url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
        return url

    @property
    def data_dir(self) -> Path:
        """Path to the data directory."""
        path = Path("data")
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def logs_dir(self) -> Path:
        """Path to the logs directory."""
        path = Path("logs")
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def frames_dir(self) -> Path:
        """Path to the frames directory for captured images."""
        path = self.data_dir / "frames"
        path.mkdir(parents=True, exist_ok=True)
        return path


def get_settings() -> Settings:
    """Get the application settings singleton."""
    return Settings()

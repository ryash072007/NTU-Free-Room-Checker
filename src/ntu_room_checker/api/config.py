"""Environment-backed API configuration."""

from dataclasses import dataclass
import os
from pathlib import Path
from zoneinfo import ZoneInfo

SINGAPORE_TIMEZONE = ZoneInfo("Asia/Singapore")


@dataclass(frozen=True, slots=True)
class ApiSettings:
    database_path: Path
    cors_origins: tuple[str, ...] = ()

    @classmethod
    def from_environment(cls) -> "ApiSettings":
        database = Path(os.getenv("NTU_ROOM_CHECKER_DB", "data/ntu_schedule.db"))
        origins = tuple(
            item.strip()
            for item in os.getenv("NTU_ROOM_CHECKER_CORS_ORIGINS", "").split(",")
            if item.strip()
        )
        return cls(database, origins)


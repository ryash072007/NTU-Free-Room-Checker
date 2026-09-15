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
    static_dir: Path | None = None

    @classmethod
    def from_environment(cls) -> "ApiSettings":
        database = Path(os.getenv("NTU_ROOM_CHECKER_DB", "data/ntu_schedule.db"))
        origins = tuple(
            item.strip()
            for item in os.getenv("NTU_ROOM_CHECKER_CORS_ORIGINS", "").split(",")
            if item.strip()
        )
        static_env = os.getenv("NTU_ROOM_CHECKER_STATIC_DIR")
        if static_env is not None:
            static_env_clean = static_env.strip()
            static_path: Path | None = (
                Path(static_env_clean)
                if static_env_clean and static_env_clean.lower() != "none"
                else None
            )
        else:
            # Auto-detect built frontend in standard repo location or cwd
            repo_static = Path(__file__).resolve().parents[3] / "web" / "dist"
            cwd_static = Path("web/dist").resolve()
            if repo_static.is_dir() and (repo_static / "index.html").is_file():
                static_path = repo_static
            elif cwd_static.is_dir() and (cwd_static / "index.html").is_file():
                static_path = cwd_static
            else:
                static_path = None
        return cls(database, origins, static_path)


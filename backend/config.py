from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    openai_temperature_json: float = 0.7
    openai_temperature_text: float = 0.85
    auto_interval_seconds: int = 45
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    REDIS_URL: str
    MEMEOS_CLIENT_TOKEN: str | None = None
    MEMEOS_HMAC_SECRET: str | None = None
    REPLICATE_API_TOKEN: str
    """HMAC secret for POST /generate-meme body signing (must match frontend)."""

    # Imgflip (template memes)
    IMGFLIP_USERNAME: str | None = None
    IMGFLIP_PASSWORD: str | None = None

    generate_max_per_ip_per_day: int = 5

    max_daily_generations_global: int = 500
    """Hard cap on successful generations per server calendar day (all clients)."""

    burst_interval_seconds: float = 3.0

    generate_timeout_seconds: float = 25.0
    """API wait for worker result (seconds), enforced with asyncio.wait_for."""

    trust_proxy_for_ip: bool = False

    rate_limit_exempt_ips: str = ""

    require_sec_fetch_site_browser: bool = False

    block_empty_user_agent: bool = True
    min_user_agent_length: int = 8

    block_cli_user_agents: bool = True

    require_json_content_type: bool = True

    require_origin_or_referer: bool = True

    meme_output_width: int = 560
    meme_output_height: int = 360
    """All rendered memes are resized to these dimensions (no user override)."""

    image_cache_dir: str = ""

    # Backward-compatible aliases used throughout the codebase.
    @property
    def redis_url(self) -> str:
        return self.REDIS_URL

    @property
    def memeos_client_token(self) -> str:
        return self.MEMEOS_CLIENT_TOKEN

    @property
    def memeos_hmac_secret(self) -> str:
        return self.MEMEOS_HMAC_SECRET

    @property
    def replicate_api_token(self) -> str:
        return self.REPLICATE_API_TOKEN

    @property
    def imgflip_username(self) -> str | None:
        return self.IMGFLIP_USERNAME

    @property
    def imgflip_password(self) -> str | None:
        return self.IMGFLIP_PASSWORD

    meme_jobs_max_queued: int = 100
    """Reject new jobs with 503 when meme_jobs queue length exceeds this."""

    @property
    def backend_dir(self) -> Path:
        return Path(__file__).resolve().parent

    @property
    def templates_dir(self) -> Path:
        return self.backend_dir / "templates"

    @property
    def image_cache_path(self) -> Path:
        if self.image_cache_dir.strip():
            return Path(self.image_cache_dir)
        return self.backend_dir / "data" / "image_cache"

    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def exempt_ip_set(self) -> set[str]:
        return {x.strip() for x in self.rate_limit_exempt_ips.split(",") if x.strip()}


settings = Settings()

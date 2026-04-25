"""VesperaFlow API entrypoint."""

from .settings import get_settings


def main() -> None:
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "vesperaflow_api.app:create_app",
        factory=True,
        host=settings.host,
        port=settings.port,
    )

"""VesperaFlow API entrypoint."""

from .app import create_app


def main() -> None:
    import uvicorn

    uvicorn.run(
        "vesperaflow_api.app:create_app", factory=True, host="0.0.0.0", port=8000
    )


__all__ = ["create_app"]

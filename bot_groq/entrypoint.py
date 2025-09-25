"""Unified entrypoint to run bot (polling) and optional health HTTP server.

If PORT env var is set (Koyeb/Heroku style), we start a FastAPI health server
on that port and launch the Telegram polling loop in a background task.
Otherwise we just run the bot normally (worker mode).
"""
import asyncio
import logging
import os
import sys
from contextlib import suppress

from bot_groq.main import main as run_bot

# FastAPI / Uvicorn are optional for worker-only mode
try:
    from fastapi import FastAPI
    import uvicorn
except Exception:  # pragma: no cover - if fastapi not installed
    FastAPI = None  # type: ignore
    uvicorn = None  # type: ignore

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s %(name)s: %(message)s')
logger = logging.getLogger("entrypoint")

print("[entrypoint] process starting Python", sys.version)
print("[entrypoint] CWD=", os.getcwd())
print("[entrypoint] LS root=", os.listdir('.'))
print("[entrypoint] Key env vars snapshot:")
for k in ["PORT", "BOT_TOKEN", "GROQ_API_KEY", "DB_NAME", "ENVIRONMENT", "PYTHONPATH"]:
    v = os.getenv(k)
    if v:
        masked = v if len(v) < 12 or k in {"PORT", "ENVIRONMENT", "DB_NAME"} else v[:6] + "..." + v[-4:]
    else:
        masked = None
    print(f"  - {k}={masked}")


async def _bot_wrapper():
    """Run the bot; if it crashes, log and attempt a single restart."""
    attempt = 0
    while attempt < 2:  # one retry
        try:
            await run_bot()
            return
        except Exception as e:  # noqa
            attempt += 1
            logger.error(f"Bot crashed (attempt {attempt}): {e}")
            await asyncio.sleep(3)
    logger.error("Bot terminated after retries")


def run_worker_only():
    logger.info("Starting in worker-only mode (no HTTP server)...")
    asyncio.run(run_bot())


def run_with_http(skip_poll: bool = False):
    if FastAPI is None or uvicorn is None:
        logger.warning("FastAPI/uvicorn not available; falling back to worker-only mode")
        run_worker_only()
        return

    app = FastAPI(title="ToxicBot Health", version="1.0.0")

    @app.get("/health")
    async def health():  # noqa
        return {"status": "ok"}

    bot_task: asyncio.Task | None = None

    if not skip_poll:
        @app.on_event("startup")
        async def _startup():  # noqa
            nonlocal bot_task
            logger.info("HTTP server startup: launching bot polling task")
            bot_task = asyncio.create_task(_bot_wrapper())
    else:
        logger.info("HTTP server startup: SKIP_POLLING=1 => bot polling disabled")

    @app.on_event("shutdown")
    async def _shutdown():  # noqa
        if bot_task and not bot_task.done():
            bot_task.cancel()
            with suppress(Exception):
                await bot_task
        logger.info("HTTP server shutdown completed")

    port = int(os.getenv("PORT", "8000"))
    logger.info(f"Starting HTTP health server on 0.0.0.0:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")


if __name__ == "__main__":
    if os.getenv("PORT"):
        run_with_http(skip_poll=bool(os.getenv("SKIP_POLLING")))
    else:
        run_worker_only()

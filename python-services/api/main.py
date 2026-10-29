from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.routers import health, tests, runs, approvals, instructions
from stores.db import get_pool, close_pool
from utils.logger import log_info, log_success


@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    log_info("Starting API...")
    await get_pool()
    log_success("API ready.")
    yield
    # shutdown
    log_info("Shutting down API...")
    await close_pool()
    log_info("Shutdown complete.")


app = FastAPI(
    title="QA Agent",
    description="Playwright automation and accessibility audit API.",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(tests.router)
app.include_router(runs.router)
app.include_router(approvals.router)
app.include_router(instructions.router)
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.gzip import GZipMiddleware

from app.config import BASE_DIR, CHARTS_DIR, STATIC_DIR
from app.db import init_db
from app.logger import get_logger, setup_logging
from app.routers import api, pages

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("Application startup initiated")
    os.makedirs(os.path.join(BASE_DIR, "instance"), exist_ok=True)
    os.makedirs(CHARTS_DIR, exist_ok=True)
    init_db()
    logger.info("Application startup completed")
    yield
    logger.info("Application shutdown completed")


app = FastAPI(title="Smart Expense API", lifespan=lifespan)
app.add_middleware(GZipMiddleware, minimum_size=500)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

app.include_router(pages.router)
app.include_router(api.router, prefix="/api")

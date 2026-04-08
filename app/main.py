# app/main.py
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.routes.cases import router as cases_router
from app.routes.courts import router as courts_router
from app.routes.documents import router as documents_router
from app.routes.exports import router as exports_router
from app.routes.inquiries import router as inquiries_router
from app.routes.inquiry_batches import router as inquiry_batches_router
from app.routes.requests import router as requests_router
from app.routes.ui import router as ui_router

app = FastAPI(title="Court Tracker")

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

app.include_router(courts_router)
app.include_router(cases_router)
app.include_router(exports_router)
app.include_router(requests_router)
app.include_router(documents_router)
app.include_router(inquiry_batches_router)
app.include_router(inquiries_router)
app.include_router(ui_router)


@app.get("/")
def read_root():
    return {"message": "Court Tracker API is running"}
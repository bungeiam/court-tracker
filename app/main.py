from fastapi import FastAPI

from app.routes.courts import router as courts_router
from app.routes.cases import router as cases_router
from app.routes.exports import router as exports_router
from app.routes.requests import router as requests_router
from app.routes.documents import router as documents_router
from app.routes.inquiry_batches import router as inquiry_batches_router
from app.routes.inquiries import router as inquiries_router

app = FastAPI(title="Court Tracker")

app.include_router(courts_router)
app.include_router(cases_router)
app.include_router(exports_router)
app.include_router(requests_router)
app.include_router(documents_router)
app.include_router(inquiry_batches_router)
app.include_router(inquiries_router)


@app.get("/")
def read_root():
    return {"message": "Court Tracker API is running"}
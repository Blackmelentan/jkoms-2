from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.routers import auth, locations, clients, bookings, shipments, containers, uploads, rates, invoices, payments, documents, notifications, staff

app = FastAPI(title="JKOMS Freight OS API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")

app.include_router(auth.router)
app.include_router(locations.router)
app.include_router(clients.router)
app.include_router(bookings.router)
app.include_router(shipments.router)
app.include_router(containers.router)
app.include_router(uploads.router)
app.include_router(rates.router)
app.include_router(invoices.router)
app.include_router(payments.router)
app.include_router(documents.router)
app.include_router(notifications.router)
app.include_router(staff.router)


@app.get("/health")
async def health():
    return {"status": "ok"}

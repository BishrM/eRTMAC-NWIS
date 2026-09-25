from fastapi import FastAPI

from app.routes import health, historical_events, wells

app = FastAPI(
    title="eRTMAC-NWIS API",
    description="Nearby Wells Intelligence System — decision support for drilling engineers.",
    version="0.1.0",
)

app.include_router(health.router)
app.include_router(wells.router)
app.include_router(historical_events.router)

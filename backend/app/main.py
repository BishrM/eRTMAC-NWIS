from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import health, historical_events, wells

app = FastAPI(
    title="eRTMAC-NWIS API",
    description="Nearby Wells Intelligence System — decision support for drilling engineers.",
    version="0.1.0",
)

# Local-dev-only: lets the Vite dev server (frontend/, a separate origin)
# call this API from the browser. No cookies/credentials are used, so a
# permissive origin list is not a meaningful security relaxation here.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(wells.router)
app.include_router(historical_events.router)

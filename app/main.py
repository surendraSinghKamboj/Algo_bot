from fastapi import FastAPI
from app.api.dashboard import router as dashboard_router
from app.api.routes import router

app = FastAPI(title="Algo Bot", version="0.1.0", description="PAPER-first Indian market research and execution system.")
app.include_router(router)
app.include_router(dashboard_router)

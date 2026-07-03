from fastapi import FastAPI

from app.routes import router

app = FastAPI(
    title="Pulse-Check API (Watchdog Sentinel)",
    description="A Dead Man's Switch API for monitoring remote devices via heartbeats.",
    version="1.0.0",
)

app.include_router(router)


@app.get("/")
def health_check():
    return {"service": "pulse-check-api", "status": "ok"}

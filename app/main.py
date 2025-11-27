from fastapi import FastAPI

app = FastAPI(title="YumYummy API")

@app.get("/health")
async def health_check():
    return {"status": "ok", "app": "YumYummy"}

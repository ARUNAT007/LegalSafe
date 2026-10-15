from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pipeline.pipeline import run_full_pipeline
import uvicorn

app = FastAPI(title="LegalSafe-G Prototype")

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")

@app.get("/")
async def ui():
    return FileResponse("frontend/index.html")

@app.post("/simplify")
async def simplify(file: UploadFile = File(...), retries: int = 2):
    contents = await file.read()
    try:
        result = run_full_pipeline(contents, filename=file.filename, retry_limit=retries)
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)

from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pipeline.pipeline import run_full_pipeline
import uvicorn
import uuid
import os
import tempfile
import io

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

app = FastAPI(title="LegalSafe-G Prototype")

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")

# Simple in-memory job store. For production replace with Redis or database.
JOBS = {}

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

@app.post("/analyze")
async def analyze(file: UploadFile = File(...), background_tasks: BackgroundTasks = None):
    """Accepts a file, creates a job, and processes it asynchronously.
    Returns: { job_id }
    """
    contents = await file.read()
    job_id = str(uuid.uuid4())
    temp_dir = tempfile.mkdtemp()
    file_path = os.path.join(temp_dir, file.filename)
    with open(file_path, "wb") as f:
        f.write(contents)

    # initialize job record
    JOBS[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "stage": "upload",
        "progress": 0,
        "result": None,
        "error": None
    }

    def progress_callback(update: dict):
        # update JOBS entry with stage/progress
        JOBS[job_id]["stage"] = update.get("stage", JOBS[job_id].get("stage"))
        JOBS[job_id]["progress"] = update.get("progress", JOBS[job_id].get("progress", 0))

    def _run():
        try:
            JOBS[job_id]["status"] = "processing"
            JOBS[job_id]["stage"] = "extraction"
            JOBS[job_id]["progress"] = 5

            # read file bytes and run pipeline with progress callback
            with open(file_path, "rb") as fh:
                data = fh.read()
            result = run_full_pipeline(data, filename=file.filename, retry_limit=2, progress_callback=progress_callback)

            JOBS[job_id]["result"] = result
            JOBS[job_id]["status"] = "completed"
            JOBS[job_id]["stage"] = "completed"
            JOBS[job_id]["progress"] = 100
        except Exception as e:
            JOBS[job_id]["status"] = "failed"
            JOBS[job_id]["error"] = str(e)

    # schedule background task
    if background_tasks is not None:
        background_tasks.add_task(_run)
    else:
        # fallback: run synchronously (not recommended)
        _run()

    return JSONResponse(content={"job_id": job_id})

@app.get("/status/{job_id}")
async def status(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JSONResponse(content=job)

@app.get("/export/{job_id}")
async def export_pdf(job_id: str):
    """Generate a simple PDF report from the job result and stream it to the client."""
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.get("status") != "completed":
        raise HTTPException(status_code=400, detail="Job not completed yet")
    result = job.get("result") or {}

    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    margin = 50
    y = height - margin

    def write_line(text, size=12, bold=False):
        nonlocal y
        if y < margin + 50:
            p.showPage()
            y = height - margin
        p.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        p.drawString(margin, y, text)
        y -= size + 6

    write_line("LEGALSAFE_G — Analysis Report", 16, True)
    write_line(f"Job ID: {job_id}", 10)
    write_line(" ")

    # Summary
    verification = result.get("verification") if result else None
    write_line("Verification:", 12, True)
    write_line(str(verification))
    write_line(" ")

    # Original text (truncated)
    orig = result.get("original_text", "(none)")
    write_line("Original Text (truncated):", 12, True)
    for line in orig.splitlines()[:50]:
        write_line(line, 10)
    write_line("...", 10)

    p.showPage()
    y = height - margin

    # Simplified text (truncated)
    simp = result.get("simplified_text", "(none)")
    write_line("Simplified Text (truncated):", 12, True)
    for line in simp.splitlines()[:60]:
        write_line(line, 10)

    p.showPage()
    p.save()
    buffer.seek(0)

    return StreamingResponse(buffer, media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename=legalsafe_report_{job_id}.pdf"})

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)

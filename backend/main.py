import base64
import os
from fastapi import FastAPI, UploadFile, File, Query, HTTPException
from fastapi.responses import FileResponse

from formatter import format_document, get_paragraph_labels, summarize_document

UPLOAD_DIR = "uploads"
OUTPUT_DIR = "outputs"

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

app = FastAPI(swagger_ui_parameters={"tryItOutEnabled": True})


@app.post("/format")
async def format_file(
    file: UploadFile = File(...),
    use_llm: bool = Query(False, description="Use Gemini to classify title/heading/body/caption (requires GEMINI_API_KEY)"),
):
    input_path = os.path.join(UPLOAD_DIR, file.filename)
    output_path = os.path.join(OUTPUT_DIR, f"formatted_{file.filename}")

    with open(input_path, "wb") as f:
        f.write(await file.read())

    format_document(input_path, output_path, use_llm=use_llm)

    return FileResponse(
        output_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=f"formatted_{file.filename}",
    )


@app.post("/format-with-ai")
async def format_with_ai(file: UploadFile = File(...)):
    """Same as /format but always uses Gemini for paragraph classification. Requires GEMINI_API_KEY."""
    input_path = os.path.join(UPLOAD_DIR, file.filename)
    output_path = os.path.join(OUTPUT_DIR, f"formatted_{file.filename}")
    with open(input_path, "wb") as f:
        f.write(await file.read())
    format_document(input_path, output_path, use_llm=True)
    return FileResponse(
        output_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=f"formatted_{file.filename}",
    )


@app.post("/classify")
async def classify_file(file: UploadFile = File(...)):
    """
    LLM-only: upload a .docx and get back paragraph labels (title/heading/body/caption) from Gemini.
    Returns JSON: { "paragraphs": [ {"index", "text_preview", "label"}, ... ], "summary": { "title": 1, "heading": 5, ... } }.
    Requires GEMINI_API_KEY.
    """
    input_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(input_path, "wb") as f:
        f.write(await file.read())
    result = get_paragraph_labels(input_path)
    if result is None:
        raise HTTPException(status_code=503, detail="Gemini unavailable or missing GEMINI_API_KEY")
    return result


@app.post("/summarize")
async def summarize_file(file: UploadFile = File(...)):
    """LLM-only: upload a .docx and get a 1–2 sentence summary from Gemini. Returns JSON: { "summary": "..." }. Requires GEMINI_API_KEY."""
    input_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(input_path, "wb") as f:
        f.write(await file.read())
    summary = summarize_document(input_path)
    if summary is None:
        raise HTTPException(status_code=503, detail="Gemini unavailable or missing GEMINI_API_KEY")
    return {"summary": summary}


@app.post("/process")
async def process_file(file: UploadFile = File(...)):
    """
    All-in-one: classify (Gemini) + format with AI + summarize. One upload → one JSON with:
    formatted_file_base64, filename, summary, classification.
    Requires GEMINI_API_KEY. Use this for a single automated pipeline.
    """
    input_path = os.path.join(UPLOAD_DIR, file.filename)
    output_path = os.path.join(OUTPUT_DIR, f"formatted_{file.filename}")
    with open(input_path, "wb") as f:
        f.write(await file.read())

    labels_result = get_paragraph_labels(input_path)
    if labels_result is None:
        raise HTTPException(status_code=503, detail="Gemini unavailable or missing GEMINI_API_KEY")

    label_list = [p["label"] for p in labels_result["paragraphs"]]
    format_document(input_path, output_path, use_llm=False, llm_labels=label_list)

    summary_text = summarize_document(input_path)
    if summary_text is None:
        summary_text = "(Summary unavailable)"

    with open(output_path, "rb") as f:
        file_b64 = base64.b64encode(f.read()).decode("utf-8")

    return {
        "formatted_file_base64": file_b64,
        "filename": f"formatted_{file.filename}",
        "summary": summary_text,
        "classification": labels_result["summary"],
    }


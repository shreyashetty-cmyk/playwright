import base64
import os
from fastapi import FastAPI, UploadFile, File, Query, HTTPException, Request, Form
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from formatter import format_document, get_paragraph_labels, summarize_document

UPLOAD_DIR = "uploads"
OUTPUT_DIR = "outputs"

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

app = FastAPI(swagger_ui_parameters={"tryItOutEnabled": True})

# Setup templates for unified canvas
TEMPLATES_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"
os.makedirs(TEMPLATES_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


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


@app.post("/api/format")
async def api_format(
    file: UploadFile = File(...),
    use_llm: bool = Form(False)
):
    """API endpoint for document formatting (for canvas UI)."""
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


# Unified Canvas Routes
@app.get("/canvas", response_class=HTMLResponse)
async def canvas_home(request: Request):
    """Unified Canvas Workspace - Main interface."""
    try:
        return templates.TemplateResponse("canvas.html", {"request": request})
    except Exception:
        # Fallback if template not found
        return HTMLResponse("""
        <html><body>
        <h1>Unified Canvas Workspace</h1>
        <p>Canvas UI is being set up. Please ensure templates/canvas.html exists.</p>
        <p><a href="/docs">Go to API Docs</a></p>
        </body></html>
        """)


@app.post("/api/research")
async def api_research(
    topic: str = Form(...),
    num_articles: int = Form(3),
    search_engine: str = Form("bing"),
    enhance_content: bool = Form(False),
    rewrite_style: str = Form("academic")
):
    """API endpoint for research."""
    try:
        import sys
        agent_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "agent")
        sys.path.insert(0, agent_dir)
        from research_agent import research_topic
        
        # Set environment variables for enhancement
        if enhance_content:
            os.environ["ENHANCE_CONTENT"] = "true"
            os.environ["REWRITE_STYLE"] = rewrite_style
        
        result = research_topic(
            topic=topic,
            num_articles=num_articles,
            search_engine=search_engine,
            headless=True,
            demo_mode=False
        )
        
        if result:
            return {"success": True, "output_path": result, "message": f"Research completed. Document saved to {result}"}
        else:
            return {"success": False, "message": "Research failed"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/enhance")
async def api_enhance(
    text: str = Form(...),
    rewrite: bool = Form(False),
    rewrite_style: str = Form("academic"),
    correct_tone: bool = Form(False),
    target_tone: str = Form("neutral"),
    check_grammar: bool = Form(True)
):
    """Enhance content."""
    try:
        import sys
        agent_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "agent")
        sys.path.insert(0, agent_dir)
        from content_enhancer import enhance_content
        
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        result = enhance_content(
            text,
            api_key=api_key,
            rewrite=rewrite,
            rewrite_style=rewrite_style,
            correct_tone_flag=correct_tone,
            target_tone=target_tone,
            check_grammar_flag=check_grammar
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/memory/search")
async def api_memory_search(query: str = Query(...), topic: str = Query(None)):
    """Search semantic memory."""
    try:
        import sys
        agent_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "agent")
        sys.path.insert(0, agent_dir)
        from semantic_memory import get_memory
        
        memory = get_memory()
        if not memory.available:
            return {"results": [], "available": False}
        
        results = memory.search_similar(query, topic=topic, n_results=5)
        return {"results": results, "available": True}
    except Exception as e:
        return {"results": [], "available": False, "error": str(e)}


@app.get("/api/memory/history")
async def api_memory_history(topic: str = Query(...)):
    """Get research history for a topic."""
    try:
        import sys
        agent_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "agent")
        sys.path.insert(0, agent_dir)
        from semantic_memory import get_memory
        
        memory = get_memory()
        if not memory.available:
            return {"history": [], "available": False}
        
        history = memory.get_topic_history(topic)
        return {"history": history, "available": True}
    except Exception as e:
        return {"history": [], "available": False, "error": str(e)}


"""
Unified Canvas Workspace: Web-based UI for research, writing, editing, and document management.
Provides a single interface for the entire research-to-document pipeline.
"""
from fastapi import FastAPI, Request, Form, File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os
import sys
import json
import asyncio
from pathlib import Path

# Add agent directory to path
AGENT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "agent")
sys.path.insert(0, AGENT_DIR)

# Import research agent and formatter
try:
    from research_agent import research_topic
    from formatter import format_document
    RESEARCH_AVAILABLE = True
except ImportError:
    RESEARCH_AVAILABLE = False

# Setup templates and static files
BASE_DIR = Path(__file__).parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

os.makedirs(TEMPLATES_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Create canvas router
canvas_app = FastAPI(title="Unified Canvas Workspace")

# Mount static files
if STATIC_DIR.exists():
    canvas_app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@canvas_app.get("/", response_class=HTMLResponse)
async def canvas_home(request: Request):
    """Main canvas interface."""
    return templates.TemplateResponse("canvas.html", {"request": request})


@canvas_app.post("/api/research")
async def api_research(
    topic: str = Form(...),
    num_articles: int = Form(3),
    search_engine: str = Form("bing"),
    enhance_content: bool = Form(False),
    rewrite_style: str = Form("academic")
):
    """API endpoint for research."""
    if not RESEARCH_AVAILABLE:
        raise HTTPException(status_code=503, detail="Research agent not available")
    
    try:
        # Set environment variables for enhancement
        if enhance_content:
            os.environ["ENHANCE_CONTENT"] = "true"
            os.environ["REWRITE_STYLE"] = rewrite_style
        
        # Run research (in background)
        result = research_topic(
            topic=topic,
            num_articles=num_articles,
            search_engine=search_engine,
            headless=True,
            demo_mode=False
        )
        
        if result:
            return JSONResponse({
                "success": True,
                "output_path": result,
                "message": f"Research completed. Document saved to {result}"
            })
        else:
            return JSONResponse({
                "success": False,
                "message": "Research failed"
            }, status_code=500)
    except Exception as e:
        return JSONResponse({
            "success": False,
            "message": str(e)
        }, status_code=500)


@canvas_app.post("/api/format")
async def api_format(file: UploadFile = File(...), use_llm: bool = Form(False)):
    """API endpoint for document formatting."""
    try:
        # Save uploaded file
        upload_dir = BASE_DIR / "uploads"
        os.makedirs(upload_dir, exist_ok=True)
        
        input_path = upload_dir / file.filename
        with open(input_path, "wb") as f:
            f.write(await file.read())
        
        # Format document
        output_dir = BASE_DIR / "outputs"
        os.makedirs(output_dir, exist_ok=True)
        output_path = output_dir / f"formatted_{file.filename}"
        
        format_document(str(input_path), str(output_path), use_llm=use_llm)
        
        # Return formatted file
        return FileResponse(
            path=str(output_path),
            filename=f"formatted_{file.filename}",
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@canvas_app.get("/api/memory/search")
async def api_memory_search(query: str, topic: str = None):
    """Search semantic memory."""
    try:
        from semantic_memory import get_memory
        memory = get_memory()
        
        if not memory.available:
            return JSONResponse({"results": [], "available": False})
        
        results = memory.search_similar(query, topic=topic, n_results=5)
        return JSONResponse({"results": results, "available": True})
    except Exception as e:
        return JSONResponse({"results": [], "available": False, "error": str(e)})


@canvas_app.get("/api/memory/history")
async def api_memory_history(topic: str):
    """Get research history for a topic."""
    try:
        from semantic_memory import get_memory
        memory = get_memory()
        
        if not memory.available:
            return JSONResponse({"history": [], "available": False})
        
        history = memory.get_topic_history(topic)
        return JSONResponse({"history": history, "available": True})
    except Exception as e:
        return JSONResponse({"history": [], "available": False, "error": str(e)})


@canvas_app.post("/api/enhance")
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
        
        return JSONResponse(result)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

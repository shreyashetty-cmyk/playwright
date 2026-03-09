#!/usr/bin/env python3
"""
Helper script to format a document, ensuring backend is running.
Usage: python format_document.py path/to/document.docx
"""
import os
import sys
import time
import subprocess
import requests
from pathlib import Path

BACKEND_URL = "http://127.0.0.1:8000"
FORMAT_ENDPOINT = f"{BACKEND_URL}/format"
BACKEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend")
AGENT_DIR = os.path.dirname(os.path.abspath(__file__))


def check_backend_running() -> bool:
    """Check if backend is running."""
    try:
        response = requests.get(f"{BACKEND_URL}/docs", timeout=2)
        return response.status_code == 200
    except:
        return False


def start_backend():
    """Start the backend server."""
    print("Starting backend server...")
    env = os.environ.copy()
    env.setdefault("PYTHONPATH", "")
    if BACKEND_DIR not in env["PYTHONPATH"].split(os.pathsep):
        env["PYTHONPATH"] = BACKEND_DIR + os.pathsep + env["PYTHONPATH"]
    
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000"],
        cwd=BACKEND_DIR,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    
    # Wait for backend to be ready
    print("Waiting for backend to start...", end=" ", flush=True)
    for _ in range(30):  # Wait up to 30 seconds
        if check_backend_running():
            print("ready!")
            return proc
        time.sleep(1)
        print(".", end="", flush=True)
    
    print("\nTimeout waiting for backend to start.")
    proc.terminate()
    return None


def format_document(file_path: str, use_llm: bool = False) -> str | None:
    """Format a document via backend API."""
    file_path = os.path.abspath(file_path)
    
    if not os.path.exists(file_path):
        print(f"Error: File not found: {file_path}")
        return None
    
    print(f"Formatting: {os.path.basename(file_path)}")
    
    # Ensure backend is running
    backend_proc = None
    if not check_backend_running():
        backend_proc = start_backend()
        if not backend_proc:
            print("Failed to start backend.")
            return None
    
    try:
        # Upload and format
        with open(file_path, "rb") as f:
            files = {
                "file": (
                    os.path.basename(file_path),
                    f,
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )
            }
            params = {"use_llm": "true"} if use_llm else {}
            print("Sending to backend (this may take a minute for large documents)...")
            
            response = requests.post(
                FORMAT_ENDPOINT,
                files=files,
                params=params,
                timeout=300  # 5 minutes
            )
        
        if response.status_code == 200:
            # Save formatted document
            output_dir = os.path.join(AGENT_DIR, "formatted_outputs")
            os.makedirs(output_dir, exist_ok=True)
            
            base_name = Path(file_path).stem
            output_path = os.path.join(output_dir, f"formatted_{base_name}.docx")
            
            with open(output_path, "wb") as f:
                f.write(response.content)
            
            print(f"✓ Formatted document saved: {output_path}")
            return output_path
        else:
            print(f"Error: Backend returned status {response.status_code}")
            print(f"Response: {response.text[:200]}")
            return None
            
    except requests.exceptions.Timeout:
        print("Error: Request timed out. Document may be too large.")
        print("Try formatting manually via Swagger UI at http://127.0.0.1:8000/docs")
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None
    finally:
        if backend_proc:
            print("\nStopping backend...")
            backend_proc.terminate()
            backend_proc.wait(timeout=5)


def main():
    if len(sys.argv) < 2:
        print("Usage: python format_document.py <document.docx> [--llm]")
        print("\nExample:")
        print("  python format_document.py research_temp.docx")
        print("  python format_document.py research_temp.docx --llm")
        sys.exit(1)
    
    file_path = sys.argv[1]
    use_llm = "--llm" in sys.argv
    
    result = format_document(file_path, use_llm=use_llm)
    sys.exit(0 if result else 1)


if __name__ == "__main__":
    main()

"""
One-command run: start the FastAPI backend in the background, wait until it's ready,
then run the Playwright agent (single file or batch). No need to open two terminals.

Usage:
  python run_all.py                    # format sample.docx (backend starts automatically)
  python run_all.py --llm              # same with use_llm=true
  python run_all.py path/to/folder     # format all .docx in folder
  python run_all.py file1.docx file2.docx
"""
import os
import subprocess
import sys
import time

# Project root (parent of agent/)
AGENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(AGENT_DIR)
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")

DOCS_URL = "http://127.0.0.1:8000/docs"
READY_TIMEOUT = 30


def _backend_ready() -> bool:
    try:
        import urllib.request
        req = urllib.request.Request(DOCS_URL, method="GET")
        urllib.request.urlopen(req, timeout=2)
        return True
    except Exception:
        return False


def main():
    os.chdir(AGENT_DIR)
    argv = [a for a in sys.argv[1:] if a != "--llm" and not a.startswith("-")]
    use_llm = "--llm" in sys.argv

    # Start backend in subprocess (same Python, backend dir)
    env = os.environ.copy()
    env.setdefault("PYTHONPATH", "")
    if BACKEND_DIR not in env["PYTHONPATH"].split(os.pathsep):
        env["PYTHONPATH"] = BACKEND_DIR + os.pathsep + env["PYTHONPATH"]

    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000"],
        cwd=BACKEND_DIR,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    print("Starting backend...", end=" ", flush=True)
    start = time.monotonic()
    while not _backend_ready():
        if time.monotonic() - start > READY_TIMEOUT:
            print("timeout.")
            proc.terminate()
            sys.exit(1)
        time.sleep(0.5)
    print("ready.")

    try:
        from run_agent import run
        if not argv:
            run(use_llm=use_llm)
        elif len(argv) == 1 and os.path.isdir(argv[0]):
            run(folder=argv[0], use_llm=use_llm)
        else:
            run(files=argv, use_llm=use_llm)
    finally:
        proc.terminate()
        proc.wait(timeout=5)
    print("Backend stopped.")


if __name__ == "__main__":
    main()

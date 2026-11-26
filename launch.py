import json
import os
import threading
import urllib.error
import urllib.request
import webbrowser


port = int(os.environ.get("MUSIC_ANALYSIS_PORT", "8765"))
url = f"http://127.0.0.1:{port}"


def ready():
    try:
        with urllib.request.urlopen(url + "/api/health", timeout=1) as response:
            return json.load(response).get("app") == "music-analysis"
    except (OSError, ValueError):
        return False


def open_after_start():
    for _ in range(100):
        if ready():
            webbrowser.open(url)
            return
        exit_wait.wait(.2)


if __name__ == "__main__":
    if ready():
        webbrowser.open(url)
    else:
        import logging
        import uvicorn
        from music_analysis.server import app

        logging.basicConfig(level=logging.INFO)
        exit_wait = threading.Event()
        threading.Thread(target=open_after_start, daemon=True).start()
        uvicorn.run(app, host="127.0.0.1", port=port, access_log=False)

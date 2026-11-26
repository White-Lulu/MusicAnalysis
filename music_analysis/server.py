import json
import logging
import os
import re
import secrets
import subprocess
import tempfile
import threading
from collections import OrderedDict
from contextlib import asynccontextmanager
from mimetypes import add_type
from pathlib import Path

import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field


ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.environ.get("MUSIC_ANALYSIS_DATA", ROOT / "data")).resolve()
ASSETS = Path(os.environ.get("MUSIC_ANALYSIS_MODELS", ROOT / "models")).resolve()
STATIC = Path(__file__).with_name("web")
TOKEN = secrets.token_urlsafe(32)
PORT = int(os.environ.get("MUSIC_ANALYSIS_PORT", "8765"))
os.environ.setdefault("HF_HOME", str(ASSETS / "huggingface"))
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
os.environ.setdefault("TF_NUM_INTRAOP_THREADS", "4")
os.environ.setdefault("TF_NUM_INTEROP_THREADS", "2")
os.environ.setdefault("OMP_NUM_THREADS", "4")
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")

from .models import Models, essentia_frames
from .signal import RATE, export_stereo_audio, load_audio, rhythm_and_harmony
from .store import AUDIO_EXTENSIONS, Library, verified_audio_path
from .taxonomy import DEFAULT_TAGS, canonical_label
from .ingest import ENCRYPTED_EXTENSIONS

LOG = logging.getLogger("music_analysis")
stopped, changed = threading.Event(), threading.Event()
library = Library(DATA)
scratch = DATA / "tmp"
scratch.mkdir(exist_ok=True)
# UploadFile rolls large bodies onto disk. Keep those files on the app volume.
tempfile.tempdir = str(scratch)
UPLOADS = DATA / "uploads"
UPLOADS.mkdir(exist_ok=True)
MAX_FILE_BYTES = 120 * 1024 * 1024
MAX_BATCH_BYTES = 1024 ** 3
REPORT_VERSION = 13
DEVICE = os.environ.get("MUSIC_ANALYSIS_DEVICE", "cpu")
models = Models(ASSETS, device=DEVICE, cache_dir=DATA / "features" / "clap")
playback_lock = threading.Lock()
playback_cache = OrderedDict()


def validated_audio(item):
    return verified_audio_path(item["path"], item["id"])


def audio_for_request(item):
    try:
        return validated_audio(item)
    except OSError as exc:
        raise HTTPException(404, "找不到原始音频，请重新导入同一文件。") from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


def analyze_essentia(y, silences):
    instruments, mood = models.jamendo_and_deam(y)
    for point in mood["curve"]:
        if any(gap["start"] <= point["time"] <= gap["end"] for gap in silences):
            point.update(valence=None, arousal=None)
    return instruments, mood


def analyze(path, previous=None):
    issues = dict(previous.get("issues", {})) if previous else {}

    def stage(label, fn, fallback):
        try:
            return fn()
        except Exception as exc:
            LOG.exception("Analysis stage %s failed", label)
            issues[label] = str(exc).splitlines()[0][:260] or type(exc).__name__
            return fallback

    def semantics(duration, genres, culture_only=False):
        return stage("LAION CLAP", lambda: models.semantics(path, duration, library.tag_settings(), genres,
                                                           culture_only=culture_only), {})

    if previous:
        issues.pop("LAION CLAP", None)
        culture_only = previous["version"] in (11, 12)
        semantic = {} if previous["rhythm"]["source"] == "静音" else semantics(previous["duration"], previous["genres"], culture_only)
        if culture_only and not semantic.get("culture") and previous["rhythm"]["source"] != "静音":
            raise RuntimeError("文化审美更新失败，请重试；其他已有分析已保留。")
        if culture_only:
            semantic["candidates"] = [row for row in previous.get("semantic", {}).get("candidates", [])
                                      if row.get("kind") == "style"] + [row for row in semantic.get("candidates", []) if row.get("kind") == "scene"]
        instruments = previous.get("instruments", [])
        if not culture_only:
            instruments = [] if previous["rhythm"]["source"] == "静音" else stage(
                "Instruments", lambda: models.instruments_from_embeddings(
                    models.discogs_embeddings(essentia_frames(load_audio(path)))), instruments)
        return {**previous, "version": REPORT_VERSION, "semantic": semantic, "instruments": instruments, "issues": issues}

    y = load_audio(path)
    duration = round(len(y) / RATE, 4)
    if float(abs(y).max()) < .0001:
        rhythm, harmony, _ = rhythm_and_harmony(y)
        return {
            "version": REPORT_VERSION, "duration": duration, "rhythm": rhythm, "harmony": harmony,
            "genres": [], "genre_bin": None, "instruments": [], "semantic": {},
            "mood": {"tags": [], "curve": []}, "issues": {},
        }
    positions = None
    beat_source = None
    if (ASSETS / "beat-this" / "final0.ckpt").is_file():
        positions = stage("Beat This!", lambda: models.beat_positions(path), None)
        if positions is not None:
            beat_source = "Beat This!"
    rhythm, harmony, silences = rhythm_and_harmony(y, positions, beat_source)
    genres, stride = stage("MAEST 519", lambda: models.genre(y, silences), ([], None))
    semantic = semantics(duration, genres)
    phonk = stage("NemoraSonar", lambda: models.brazilian_phonk(path), {})
    instruments, mood = stage(
        "Essentia", lambda: analyze_essentia(y, silences), ([], {"tags": [], "curve": []})
    )
    return {
        "version": REPORT_VERSION, "duration": duration, "rhythm": rhythm, "harmony": harmony,
        "genres": genres, "genre_bin": stride, "instruments": instruments,
        "semantic": semantic,
        "mood": mood, "phonk": phonk, "issues": issues,
    }


def worker():
    import torch
    torch.set_num_threads(max(1, int(os.environ.get("MUSIC_ANALYSIS_THREADS", "4"))))
    while not stopped.is_set():
        track = library.claim_next()
        if track is None:
            changed.wait(timeout=2)
            changed.clear()
            continue
        try:
            path = validated_audio(track)
            previous = json.loads(track["previous"]) if track["previous"] else None
            result = analyze(path, previous)
            validated_audio(track)
            library.finish(track["id"], result)
        except Exception as exc:
            LOG.exception("Analysis failed")
            library.finish(track["id"], error=str(exc).splitlines()[0][:280] or type(exc).__name__)


@asynccontextmanager
async def lifespan(_app):
    library.upgrade_reports(REPORT_VERSION)
    thread = threading.Thread(target=worker, daemon=True, name="audio-analysis")
    thread.start()
    yield
    stopped.set()
    changed.set()


app = FastAPI(title="音乐分析", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
add_type("image/webp", ".webp")
add_type("font/woff2", ".woff2")
app.mount("/assets", StaticFiles(directory=STATIC), name="assets")


@app.middleware("http")
async def local_requests(request: Request, call_next):
    host = request.headers.get("host", "")
    accepted = {f"127.0.0.1:{PORT}", f"localhost:{PORT}"}
    if host not in accepted:
        return JSONResponse({"detail": "此服务只能通过本机地址访问。"}, status_code=403)
    if request.method not in {"GET", "HEAD"}:
        origin = request.headers.get("origin")
        if request.headers.get("x-local-token") != TOKEN or (origin and origin != f"http://{host}"):
            return JSONResponse({"detail": "请刷新本机应用页面后重试。"}, status_code=403)
        if request.url.path == "/api/uploads":
            try:
                size = int(request.headers.get("content-length", "0"))
            except ValueError:
                return JSONResponse({"detail": "文件请求格式有误。"}, status_code=400)
            if size > MAX_BATCH_BYTES + 64 * 1024:
                return JSONResponse({"detail": "每批文件合计最多 1 GiB。"}, status_code=413)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; media-src 'self' blob:; object-src 'none'; frame-ancestors 'none'"
    )
    if request.url.path.startswith("/api/") or request.url.path == "/":
        response.headers["Cache-Control"] = "no-store"
    return response


def get_track(track_id):
    if not re.fullmatch(r"[a-f0-9]{64}", track_id):
        raise HTTPException(404, "曲目不存在。")
    try:
        return library.track(track_id)
    except KeyError:
        raise HTTPException(404, "曲目不存在。")


def public_track(track):
    report = track.get("report")
    if report and report.get("semantic"):
        semantic = report["semantic"]
        current = set(DEFAULT_TAGS) | {canonical_label(label) for label in library.tag_settings()}
        semantic["candidates"] = [row for row in semantic["candidates"] if row["label"] in current]
    return track


@app.get("/", response_class=HTMLResponse)
def index():
    return (STATIC / "index.html").read_text(encoding="utf-8").replace("__LOCAL_TOKEN__", TOKEN)


@app.get("/api/health")
def health():
    return {"app": "music-analysis"}


@app.get("/api/tracks")
def tracks(q: str = Query("", max_length=120)):
    return library.tracks(q)


@app.get("/api/tracks/{track_id}")
def track(track_id: str):
    return public_track(get_track(track_id))


@app.get("/api/tracks/{track_id}/audio")
def audio(track_id: str, compatible: bool = False):
    path = audio_for_request(get_track(track_id))
    if not compatible and path.suffix.lower() not in {".aif", ".aiff"}:
        return FileResponse(path)
    with playback_lock:
        if track_id not in playback_cache:
            folder = tempfile.TemporaryDirectory(prefix="playback-", dir=scratch, ignore_cleanup_errors=True)
            try:
                export_stereo_audio(path, Path(folder.name) / "audio.flac", "flac")
            except (OSError, ValueError, subprocess.SubprocessError) as exc:
                folder.cleanup()
                raise HTTPException(422, "当前文件无法转换成可播放音频。") from exc
            playback_cache[track_id] = folder
        playback_cache.move_to_end(track_id)
        if len(playback_cache) > 3:
            _, obsolete = playback_cache.popitem(last=False)
            obsolete.cleanup()
        return FileResponse(Path(playback_cache[track_id].name) / "audio.flac", media_type="audio/flac")


@app.get("/api/tracks/{track_id}/report")
def report(track_id: str):
    item = public_track(get_track(track_id))
    item.pop("path", None)
    return JSONResponse(item, headers={"Content-Disposition": 'attachment; filename="music-analysis.json"'})


def save_upload(file):
    original = Path((file.filename or "").replace(chr(92), "/")).name
    suffix = Path(original).suffix.lower()
    if suffix not in AUDIO_EXTENSIONS | ENCRYPTED_EXTENSIONS:
        raise ValueError("音频格式未支持")
    with tempfile.NamedTemporaryFile(dir=scratch, prefix="upload-", suffix=suffix, delete=False) as temporary:
        candidate = Path(temporary.name)
        try:
            size = 0
            for block in iter(lambda: file.file.read(1024 * 1024), b""):
                size += len(block)
                if size > MAX_FILE_BYTES:
                    raise ValueError("文件超过 120 MiB")
                temporary.write(block)
        except BaseException:
            temporary.close()
            candidate.unlink(missing_ok=True)
            raise
    try:
        if not size:
            raise ValueError("文件为空")
        return library.import_audio(candidate, original_name=original)["id"]
    finally:
        candidate.unlink(missing_ok=True)


@app.post("/api/uploads")
def upload(files: list[UploadFile] = File(), title: str = Form(default="", max_length=120)):
    if not 1 <= len(files) <= 50:
        raise HTTPException(400, "每批可提交 1–50 首歌曲。")
    if sum(file.size or 0 for file in files) > MAX_BATCH_BYTES:
        raise HTTPException(413, "每批文件合计最多 1 GiB。")
    ids, errors = [], []
    for file in files:
        try:
            ids.append(save_upload(file))
        except (ValueError, OSError) as exc:
            errors.append({"file": file.filename, "reason": str(exc)})
        finally:
            file.file.close()
    ids = list(dict.fromkeys(ids))
    if not ids:
        return JSONResponse({"detail": errors[0]["reason"] if errors else "没有收到音频。", "errors": errors}, status_code=400)
    name = title.strip() or (Path(files[0].filename or "").stem if len(files) == 1 else f"上传批次 · {len(ids)} 首")
    batch = library.create_batch(name, ids)
    changed.set()
    return {"batch": batch, "ids": ids, "count": len(ids), "errors": errors}


@app.get("/api/batches")
def batches():
    return library.batches()


@app.get("/api/formats")
def formats():
    return {"extensions": sorted(AUDIO_EXTENSIONS), "output": "mp3"}


@app.get("/api/collection")
def collection(batch: str | None = Query(None, max_length=40), weighted: bool = True):
    try:
        return library.collection_summary(batch, weighted)
    except KeyError:
        raise HTTPException(404, "批次不存在。")


class Metadata(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    artist: str = Field(max_length=240)


@app.patch("/api/tracks/{track_id}/metadata")
def update_metadata(track_id: str, body: Metadata):
    get_track(track_id)
    if not body.title.strip():
        raise HTTPException(400, "请输入歌名。")
    library.update_metadata(track_id, body.title.strip(), body.artist.strip())
    return {"ok": True}


@app.post("/api/tracks/{track_id}/retry")
def retry(track_id: str):
    get_track(track_id)
    library.retry(track_id)
    changed.set()
    return {"ok": True}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    uvicorn.run(app, host="127.0.0.1", port=PORT, access_log=False)

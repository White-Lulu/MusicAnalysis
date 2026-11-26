import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import threading
import time
import unicodedata
import uuid
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path

from mutagen import File as read_tags

from .summary import profile_fields, summarize_tracks
from .taxonomy import limit_scene_candidates
from .ingest import AUDIO_EXTENSIONS, ENCRYPTED_EXTENSIONS, convert_mp3


def lookup_text(value):
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def lookup_key(title, artist):
    return "\x1f".join(map(lookup_text, (title, artist)))


def file_digest(path):
    with Path(path).open("rb") as audio:
        return hashlib.file_digest(audio, "sha256").hexdigest()


@lru_cache(maxsize=256)
def source_digest(path, _size, _mtime, _ctime):
    return file_digest(path)


def verified_audio_path(path, identity):
    path = Path(path)
    info = path.stat()
    if source_digest(path, info.st_size, info.st_mtime_ns, info.st_ctime_ns) != identity:
        raise ValueError("原文件内容已改变，请重新导入当前文件。")
    return path


def identify(path, identity=None, original_name=None):
    identity = identity or file_digest(path)
    fallback = Path(original_name).stem if original_name else path.stem
    try:
        tags = read_tags(path, easy=True)
    except Exception:
        tags = None
    if tags is None:
        return identity, fallback, "", None
    title = (tags.get("title") or [fallback])[0] or fallback
    artist = (tags.get("artist") or [""])[0]
    duration = getattr(tags.info, "length", None)
    return identity, str(title), str(artist), duration


class Library:
    def __init__(self, data_dir):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db = self.data_dir / "library.sqlite3"
        self.import_lock = threading.Lock()
        with self.connect() as con:
            con.executescript("""
                PRAGMA journal_mode = WAL;
                CREATE TABLE IF NOT EXISTS tracks (
                    id TEXT PRIMARY KEY, path TEXT NOT NULL, title TEXT NOT NULL,
                    artist TEXT NOT NULL, lookup TEXT NOT NULL, duration REAL,
                    added REAL NOT NULL, state TEXT NOT NULL, report TEXT, error TEXT
                );
                CREATE INDEX IF NOT EXISTS tracks_lookup ON tracks(lookup);
                CREATE TABLE IF NOT EXISTS tag_settings (
                    label TEXT PRIMARY KEY, description TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS batches (
                    id TEXT PRIMARY KEY, label TEXT NOT NULL, created REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS batch_tracks (
                    batch_id TEXT NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
                    track_id TEXT NOT NULL REFERENCES tracks(id) ON DELETE CASCADE,
                    PRIMARY KEY(batch_id, track_id)
                );
                CREATE INDEX IF NOT EXISTS batch_tracks_by_track ON batch_tracks(track_id);
                CREATE TABLE IF NOT EXISTS imports (
                    source_id TEXT PRIMARY KEY,
                    track_id TEXT NOT NULL REFERENCES tracks(id) ON DELETE CASCADE
                );
            """)
            if "profile" not in {column["name"] for column in con.execute("PRAGMA table_info(tracks)")}:
                con.execute("ALTER TABLE tracks ADD COLUMN profile TEXT")
            con.execute("""
                INSERT OR IGNORE INTO batches(id,label,created)
                SELECT 'legacy', '此前导入', MIN(added) FROM tracks
                WHERE NOT EXISTS (SELECT 1 FROM batch_tracks WHERE batch_tracks.track_id=tracks.id)
                HAVING MIN(added) IS NOT NULL
            """)
            con.execute("""
                INSERT OR IGNORE INTO batch_tracks(batch_id,track_id)
                SELECT 'legacy',id FROM tracks
                WHERE NOT EXISTS (SELECT 1 FROM batch_tracks WHERE batch_tracks.track_id=tracks.id)
            """)
            con.execute("UPDATE tracks SET state = 'queued' WHERE state = 'running'")

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.db, timeout=30)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            with connection:
                yield connection
        finally:
            connection.close()

    def register(self, path, title=None, artist=None, identity=None, original_name=None):
        path = Path(path).expanduser().resolve(strict=True)
        if not path.is_file() or path.suffix.lower() not in AUDIO_EXTENSIONS:
            raise ValueError("请选择支持的音频文件。")
        track_id, tagged_title, tagged_artist, duration = identify(path, identity, original_name)
        title = tagged_title if title is None else title.strip() or tagged_title
        artist = tagged_artist if artist is None else artist.strip()
        with self.connect() as con:
            con.execute("BEGIN IMMEDIATE")
            existing = con.execute("SELECT path FROM tracks WHERE id=?", (track_id,)).fetchone()
            uploads = self.data_dir / "uploads"
            if existing and path.parent != uploads and Path(existing["path"]).parent == uploads:
                try:
                    path = verified_audio_path(existing["path"], track_id)
                except (OSError, ValueError):
                    pass
            con.execute("""
                INSERT INTO tracks(id,path,title,artist,lookup,duration,added,state)
                VALUES(?,?,?,?,?,?,?,'queued')
                ON CONFLICT(id) DO UPDATE SET path = excluded.path
            """, (track_id, str(path), title, artist, lookup_key(title, artist), duration, time.time()))
        return self.track(track_id)

    def import_audio(self, path, original_name=None):
        path = Path(path).expanduser().resolve(strict=True)
        suffix = Path(original_name or path.name).suffix.lower()
        if suffix in ENCRYPTED_EXTENSIONS:
            raise ValueError("此加密格式当前未支持，请从原播放器导出 MP3 或 FLAC 后导入。")
        if not path.is_file() or suffix not in AUDIO_EXTENSIONS:
            raise ValueError("请选择支持的音频文件。")
        with self.import_lock:
            source_id = file_digest(path)
            with self.connect() as con:
                row = con.execute("SELECT track_id FROM imports WHERE source_id=?", (source_id,)).fetchone()
            existing = None
            try:
                existing = self.track(row["track_id"] if row else source_id)
                verified_audio_path(existing["path"], existing["id"])
                return existing
            except (KeyError, OSError, ValueError):
                pass
            uploads = self.data_dir / "uploads"
            uploads.mkdir(exist_ok=True)
            with tempfile.TemporaryDirectory(prefix="convert-", dir=uploads) as folder:
                if existing and existing["id"] == source_id:
                    restored = Path(folder) / ("restore" + suffix)
                    shutil.copyfile(path, restored)
                    verified_audio_path(restored, source_id)
                    destination = uploads / (source_id + suffix)
                    os.replace(restored, destination)
                    return self.register(destination, identity=source_id, original_name=original_name or path.name)
                target = Path(folder) / "audio.mp3"
                convert_mp3(path, target, folder)
                if file_digest(path) != source_id:
                    raise ValueError("原文件内容已改变，请重新导入当前文件。")
                identity = file_digest(target)
                destination = uploads / (identity + ".mp3")
                try:
                    verified_audio_path(destination, identity)
                except (OSError, ValueError):
                    os.replace(target, destination)
                registered = self.register(destination, identity=identity, original_name=original_name or path.name)
                with self.connect() as con:
                    con.execute("INSERT OR REPLACE INTO imports VALUES(?,?)", (source_id, identity))
                return registered

    def create_batch(self, name, tracks):
        if not tracks:
            return None
        batch_id = uuid.uuid4().hex
        with self.connect() as con:
            con.execute("INSERT INTO batches(id,label,created) VALUES(?,?,?)",
                        (batch_id, name.strip()[:120] or "未命名批次", time.time()))
            con.executemany("INSERT OR IGNORE INTO batch_tracks VALUES(?,?)", ((batch_id, track) for track in tracks))
        return batch_id

    def batches(self):
        with self.connect() as con:
            return [dict(row) for row in con.execute("""
                SELECT b.id,b.label,COUNT(t.id) AS count, SUM(t.state='done') AS analysed,
                       SUM(t.state IN ('queued','running')) AS pending
                FROM batches b JOIN batch_tracks bt ON bt.batch_id=b.id JOIN tracks t ON bt.track_id=t.id
                GROUP BY b.id ORDER BY b.created DESC
            """)]

    def collection_summary(self, batch_id, weighted):
        with self.connect() as con:
            batch = con.execute("SELECT label FROM batches WHERE id=?", (batch_id,)).fetchone() if batch_id else None
            if batch_id and batch is None:
                raise KeyError(batch_id)
            rows = con.execute("""
                SELECT id,title,artist,state,profile, CASE WHEN profile IS NULL THEN report END AS legacy_report
                FROM tracks WHERE ? IS NULL OR id IN (
                    SELECT track_id FROM batch_tracks WHERE batch_id=?
                ) ORDER BY added DESC
            """, (batch_id, batch_id))
            tracks = []
            for row in rows:
                if row["profile"]:
                    report = json.loads(row["profile"])
                elif row["legacy_report"]:
                    report = profile_fields(json.loads(row["legacy_report"]))
                else:
                    report = None
                tracks.append({"id": row["id"], "title": row["title"], "artist": row["artist"], "state": row["state"],
                               "report": report})
        return {**summarize_tracks(tracks, weighted), "label": batch["label"] if batch else "全部提交"}

    def upgrade_reports(self, version):
        with self.connect() as con:
            # Version 7 only needs its saved profile regenerated.
            for row in con.execute("""
                SELECT id, report FROM tracks
                WHERE report IS NOT NULL AND COALESCE(json_extract(report, '$.version'),0) < ?
            """, (version,)).fetchall():
                report = json.loads(row["report"])
                if report.get("version") == 9:
                    report["version"] = 10
                    report.pop("recording_context", None)
                    if candidates := report.get("semantic", {}).get("candidates"):
                        report["semantic"]["candidates"] = limit_scene_candidates(candidates)
                    payload = json.dumps(report, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
                    con.execute("UPDATE tracks SET report=? WHERE id=?", (payload, row["id"]))
                    continue
                if report.get("version") == 7:
                    report["version"] = 8
                if report.get("version", 0) < 6:
                    for key in ("waveform", "notes"):
                        report.pop(key, None)
                    rhythm = report.get("rhythm", {})
                    rhythm["beat_count"] = len(rhythm.pop("beats", []))
                    for key in ("alternatives", "downbeats", "curve", "offbeat_share", "segments", "roles", "structure_source"):
                        rhythm.pop(key, None)
                    harmony = report.get("harmony", {})
                    for key in ("keys", "chords", "pitch", "silence"):
                        harmony.pop(key, None)
                    if harmony.get("source") == "色度匹配 · 滑窗和变点稳定化":
                        harmony["source"] = "色度匹配"
                    semantic = report.get("semantic", {})
                    semantic.pop("embedding", None)
                    semantic.pop("references", None)
                    report.get("issues", {}).pop("All-In-One", None)
                if report.get("version") == 5:
                    report["version"] = 6
                report.pop("instrument_candidates", None)
                report["genres"] = [item for item in report.get("genres", []) if item["coverage"] > 0]
                for item in report["genres"]:
                    item.pop("intervals", None)
                for item in report.get("instruments", []):
                    item.pop("peak_start", None)
                    item.pop("peak_end", None)
                payload = json.dumps(report, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
                compact = json.dumps(profile_fields(report), separators=(",", ":"), ensure_ascii=False, allow_nan=False)
                con.execute("UPDATE tracks SET report=?,profile=? WHERE id=?", (payload, compact, row["id"]))
            # Refresh compact profiles from saved reports without running audio models.
            for row in con.execute("""
                SELECT id,report FROM tracks WHERE report IS NOT NULL
                AND json_type(profile, '$.semantic') IS NULL
            """).fetchall():
                compact = json.dumps(profile_fields(json.loads(row["report"])), separators=(",", ":"),
                                     ensure_ascii=False, allow_nan=False)
                con.execute("UPDATE tracks SET profile=? WHERE id=?", (compact, row["id"]))
            return con.execute("""
                UPDATE tracks SET state='queued'
                WHERE state='done' AND report IS NOT NULL AND COALESCE(json_extract(report, '$.version'),0) < ?
            """, (version,)).rowcount

    def tracks(self, query=""):
        with self.connect() as con:
            rows = con.execute("""
                SELECT id,title,artist,duration,state,
                    json_extract(report, '$.rhythm.bpm') AS bpm,
                    json_extract(report, '$.harmony.key') AS musical_key,
                    json_extract(report, '$.genres[0].label') AS genre
                FROM tracks
                WHERE instr(replace(lookup, char(31), ' '), ?) > 0
                ORDER BY added DESC
            """, (lookup_text(query),))
            return [dict(row) for row in rows]

    def track(self, track_id):
        with self.connect() as con:
            row = con.execute("SELECT * FROM tracks WHERE id=?", (track_id,)).fetchone()
            if row is None:
                raise KeyError(track_id)
            track = dict(row)
            track.pop("lookup")
            track.pop("profile")
            track["report"] = json.loads(track["report"]) if track["report"] else None
            return track

    def claim_next(self):
        with self.connect() as con:
            return con.execute("""
                UPDATE tracks SET state = 'running', error = NULL WHERE id = (
                  SELECT id FROM tracks WHERE state = 'queued' ORDER BY added LIMIT 1
                ) RETURNING id,path,CASE WHEN json_extract(report,'$.version') IN (6,8,10,11) THEN report END AS previous
            """).fetchone()

    def finish(self, track_id, report=None, error=None):
        with self.connect() as con:
            if report is not None:
                payload = json.dumps(report, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
                compact = json.dumps(profile_fields(report), separators=(",", ":"), ensure_ascii=False, allow_nan=False)
                con.execute("UPDATE tracks SET state='done',report=?,profile=?,duration=?,error=NULL WHERE id=?",
                            (payload, compact, report["duration"], track_id))
            else:
                con.execute("UPDATE tracks SET state='error',error=? WHERE id=?", (error, track_id))

    def retry(self, track_id):
        self.track(track_id)
        with self.connect() as con:
            con.execute("UPDATE tracks SET state='queued',error=NULL WHERE id=? AND state!='running'", (track_id,))

    def update_metadata(self, track_id, title, artist):
        self.track(track_id)
        with self.connect() as con:
            con.execute("UPDATE tracks SET title=?,artist=?,lookup=? WHERE id=?",
                        (title, artist, lookup_key(title, artist), track_id))

    def tag_settings(self):
        with self.connect() as con:
            return dict(con.execute("SELECT label,description FROM tag_settings ORDER BY label"))

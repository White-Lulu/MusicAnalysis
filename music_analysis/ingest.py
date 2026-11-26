"""Local container decoding and MP3 import. NCM format reference is in README."""

import base64
import json
import struct
import subprocess
from pathlib import Path

import imageio_ffmpeg
import numpy as np
from Cryptodome.Cipher import AES
from Cryptodome.Util.Padding import unpad
from mutagen import File as read_tags
from mutagen.mp3 import MP3


AUDIO_EXTENSIONS = {
    ".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg", ".opus", ".aiff", ".aif", ".aifc",
    ".wma", ".ape", ".wv", ".m4b", ".mp2", ".mpga", ".oga", ".mka", ".caf", ".au", ".snd",
    ".w64", ".ac3", ".eac3", ".amr", ".mp4", ".webm", ".dsf", ".dff", ".ncm", ".uc",
}
ENCRYPTED_EXTENSIONS = {".qmc", ".qmc0", ".qmc3", ".qmcflac", ".qmcogg", ".mgg", ".mflac", ".kgm", ".kgma", ".vpr"}


def read_exact(stream, length):
    if length < 0 or length > 16 * 1024 * 1024:
        raise ValueError("NCM 文件中的字段长度无效。")
    data = stream.read(length)
    if len(data) != length:
        raise ValueError("NCM 文件不完整。")
    return data


def ncm_audio(source, output):
    def number(stream):
        return struct.unpack("<I", read_exact(stream, 4))[0]

    metadata = {}
    with Path(source).open("rb") as stream, Path(output).open("wb") as audio:
        if read_exact(stream, 8) != b"CTENFDAM":
            raise ValueError("NCM 文件头无效。")
        read_exact(stream, 2)
        encrypted_key = read_exact(stream, number(stream))
        try:
            padded = AES.new(bytes.fromhex("687a4852416d736f356b496e62617857"), AES.MODE_ECB).decrypt(
                bytes(value ^ 0x64 for value in encrypted_key))
            key = unpad(padded, 16)
        except ValueError as exc:
            raise ValueError("NCM 音频密钥无效，无法解包此文件。") from exc
        if not key.startswith(b"neteasecloudmusic") or len(key) <= 17:
            raise ValueError("NCM 音频密钥无效，无法解包此文件。")
        key = key[17:]
        box = list(range(256))
        position = 0
        for index in range(256):
            position = (position + box[index] + key[index % len(key)]) % 256
            box[index], box[position] = box[position], box[index]
        mask = np.array([box[(box[(index + 1) % 256] +
                             box[(box[(index + 1) % 256] + index + 1) % 256]) % 256]
                         for index in range(256)], dtype=np.uint8)
        encrypted_meta = read_exact(stream, number(stream))
        if encrypted_meta:
            try:
                encoded = bytes(value ^ 0x63 for value in encrypted_meta)
                content = AES.new(bytes.fromhex("2331346c6a6b5f215c5d2630553c2728"), AES.MODE_ECB).decrypt(
                    base64.b64decode(encoded[22:], validate=True))
                kind, payload = unpad(content, 16).split(b":", 1)
                data = json.loads(payload)
                data = data.get("mainMusic", {}) if kind == b"dj" else data
                metadata = {"title": str(data.get("musicName", ""))[:240],
                            "artist": "/".join(str(artist[0]) for artist in data.get("artist", []) if artist)[:240]}
            except (ValueError, TypeError, KeyError, IndexError, AttributeError):
                # Optional tags must not prevent an otherwise readable audio import.
                metadata = {}
        read_exact(stream, 5)  # CRC32 and image version.
        cover_frame, cover_size = number(stream), number(stream)
        if cover_size > cover_frame or stream.tell() + cover_frame >= Path(source).stat().st_size:
            raise ValueError("NCM 封面或音频数据不完整。")
        stream.seek(cover_frame, 1)
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            decoded = np.bitwise_xor(np.frombuffer(block, dtype=np.uint8), np.resize(mask, len(block)))
            audio.write(decoded.tobytes())
    return metadata


def convert_mp3(source, output, scratch):
    source, output = Path(source), Path(output)
    metadata = {}
    with source.open("rb") as stream:
        header = stream.read(8)
    if source.suffix.lower() == ".ncm" or header == b"CTENFDAM":
        decoded = Path(scratch) / "decoded.audio"
        metadata = ncm_audio(source, decoded)
        source = decoded
    elif source.suffix.lower() == ".uc":
        decoded = Path(scratch) / "decoded.audio"
        with source.open("rb") as cached, decoded.open("wb") as audio:
            for block in iter(lambda: cached.read(1024 * 1024), b""):
                audio.write(np.bitwise_xor(np.frombuffer(block, dtype=np.uint8), 0xA3).tobytes())
        source = decoded
    try:
        tags = read_tags(source)
    except Exception:
        tags = None
    codec = ["-c:a", "copy"] if isinstance(tags, MP3) else ["-c:a", "libmp3lame", "-b:a", "320k", "-ar", "48000", "-ac", "2"]
    command = [imageio_ffmpeg.get_ffmpeg_exe(), "-nostdin", "-v", "error", "-n",
               "-protocol_whitelist", "file,pipe", "-i", str(source), "-map", "0:a:0", "-vn",
               "-t", "3601", "-map_metadata", "0", *codec]
    for key, value in metadata.items():
        if value:
            command += ["-metadata", key + "=" + value]
    command += ["-id3v2_version", "3", str(output)]
    try:
        result = subprocess.run(command, capture_output=True, timeout=300,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except subprocess.TimeoutExpired as exc:
        raise ValueError("音频转换超时，请检查文件或缩短时长后重试。") from exc
    if result.returncode:
        raise ValueError("无法解码此文件，文件可能损坏或使用尚未支持的加密格式。")
    try:
        duration = MP3(output).info.length
    except Exception as exc:
        raise ValueError("转换结果不是有效的 MP3 音频。") from exc
    if not 1 <= duration <= 3600:
        raise ValueError("请导入 1 秒至 60 分钟的音频。")

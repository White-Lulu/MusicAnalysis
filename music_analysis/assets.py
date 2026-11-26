import hashlib
import os
import shutil
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from zipfile import ZipFile

import requests


MAEST = ("mtg-upf/discogs-maest-30s-pw-129e-519l", "6c35f32a350f74351870937d5ae0bae1d898d1df",
         {"config.json": "7e67242387d27954e28fce3120f2ce8e68bcf85b",
          "feature_extraction_maest.py": "593f9332598434b8d1f109c48fb8e52abe03ec38",
          "preprocessor_config.json": "39b8883f8bb1322f383ef24ae4dadee628fbdf63",
          "model.safetensors": "881cec6abdcb6ef986367e6c0db02dc760cc0f88a52b625cb9d6e2b54d505548"})
CLAP = ("laion/clap-htsat-unfused", "8fa0f1c6d0433df6e97c127f64b2a1d6c0dcda8a",
        {"config.json": "9efb9557bc804f2ca6e394486af2e45dfed0b18554909735a99c6220b84e4288",
         "merges.txt": "fe36cab26d4f4421ed725e10a2e9ddb7f799449c603a96e7f29b5a3c82a95862",
         "preprocessor_config.json": "9739f58296aa6f9ac18008fd0150fb2649bc554985fbde86d0a4041c882ac753",
         "pytorch_model.bin": "1cd3c601bc4afe0fa87be3de4c13dd2cfadd249fac1e29acf74a9b296c3219bb",
         "special_tokens_map.json": "06e405a36dfe4b9604f484f6a1e619af1a7f7d09e34a8555eb0b77b66318067f",
         "tokenizer.json": "77ef92283d67f0d97e1454909a964afcbfa2019f0fb9f18f8e88d5c25c3ba729",
         "tokenizer_config.json": "377f91458f7729a4574a84c77bdce67dbc3c58c1a345a29bbf8c4eb1307948a3",
         "vocab.json": "ed19656ea1707df69134c4af35c8ceda2cc9860bf2c3495026153a133670ab5e"})
ESSENTIA_BASE = "https://essentia.upf.edu/models/"
ESSENTIA = {
    "effnet": "feature-extractors/discogs-effnet/discogs-effnet-bs64-1",
    "instrument": "classification-heads/mtg_jamendo_instrument/mtg_jamendo_instrument-discogs-effnet-1",
    "mood": "classification-heads/mtg_jamendo_moodtheme/mtg_jamendo_moodtheme-discogs-effnet-1",
    "musicnn": "autotagging/msd/msd-musicnn-1",
    "deam": "classification-heads/deam/deam-msd-musicnn-2",
}
ESSENTIA_HASHES = {
    "effnet.pb": "3ed9af50d5367c0b9c795b294b00e7599e4943244f4cbd376869f3bfc87721b1",
    "effnet.json": "a35003202384735c33154e20264267f9941705218a7b93202b655a1d408d4ff6",
    "instrument.pb": "2e8c3003c722e098da371b6a1f7ad0ce62fac0dcfc09c7c7997d430941196c2a",
    "instrument.json": "7d02204c6451b5615e2968ec6364bbae3b915c886e608f05f00d3a38dc5177c4",
    "mood.pb": "03f2b047020aee4ab39f8880da7bdae2a36d06a1508d656c6d424ad4d6de07a9",
    "mood.json": "d62cd90263e4d613fa7fcce7a831e339450394794af63685f96e065c1a896ab0",
    "musicnn.pb": "cdea0722bcee7f731286843f2233e3aa69887bb5c3e2dce011eff55f38d04f3e",
    "musicnn.json": "24842b068b5c09dce033a0bcb41d450e4e469352b799e831ac7728c93bbfb6be",
    "deam.pb": "beb5eeb0909266eeb78b8d6bb1323b10829cf2fe55e3c01a13fa1846fa98b371",
    "deam.json": "079df8d538d093ba35c34b7fbee01ff2773c4469be5281520f55d585295a3c58",
}
NEMORA_URL = "https://github.com/Nikenmar/NemoraSonar/releases/download/v1.1/nemorasonar-phonk-1.1.zip"
NEMORA_SHA = "e590bb4be15196ea93db3900b45fcd06d7d40914ba28eb6852edfddb516a26d4"
NEMORA_HASHES = {
    "model.onnx": "00697c165a7d2ae4a7c92490a1e3493a42ad1736c4aa9d8bc2d2a1733a3e1bd0",
    "onnx_meta.json": "32168fe8fd20b129bc059eb0f90133591a451ba437c4108acb07a6d542b153cb",
    "labels.json": "1941cc00cb17812d161e734ef0a50d3d85b8064006de73a609368006c31cbdb3",
    "LICENSE": "8e6b11bd70ada63e1fdea38f4472664581a2b7dae99e8959db6bcff46c71eb4a",
    "THIRD_PARTY_LICENSES.md": "875cd69b4d1e71b439da1197ef33f71530c4505ed50ebb524002ebd948755260",
}
BEAT_SHA = "8c328b45f59d8dd3dff219253ff6a8d6482be57d0133a29140e2febbf8eb8331"
BEAT_URLS = (
    "https://cloud.cp.jku.at/public.php/dav/files/7ik4RrBKTS273gp/final0.ckpt",
    "https://huggingface.co/rtikw/localmusic-assets/resolve/main/analysis/beat_this-final0.ckpt",
)


def matches_checksum(path, checksum, method):
    if not path.is_file() or not path.stat().st_size:
        return False
    with path.open("rb") as content:
        if method == "git-blob":
            digest = hashlib.sha1(f"blob {path.stat().st_size}\0".encode())
            for block in iter(lambda: content.read(1024 * 1024), b""):
                digest.update(block)
        else:
            digest = hashlib.file_digest(content, method)
    return digest.hexdigest() == checksum


def download(url, target, checksum, method="sha256"):
    target = Path(target)
    if matches_checksum(target, checksum, method):
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=target.parent, prefix=target.name + ".", suffix=".part", delete=False) as out:
        part = Path(out.name)
        try:
            with requests.get(url, stream=True, timeout=(15, 120), headers={"Accept-Encoding": "identity"}) as response:
                response.raise_for_status()
                response.raw.decode_content = True
                shutil.copyfileobj(response.raw, out, length=1024 * 1024)
            out.close()
            if not matches_checksum(part, checksum, method):
                raise OSError(f"模型文件校验未通过：{target.name}")
            os.replace(part, target)
        finally:
            out.close()
            part.unlink(missing_ok=True)
    return target


def prepare_beat(base):
    target = base / "beat-this" / "final0.ckpt"
    if matches_checksum(target, BEAT_SHA, "sha256"):
        return
    for url in BEAT_URLS:
        try:
            download(url, target, BEAT_SHA)
            print("beat-this/final0.ckpt · 81.1 MB", flush=True)
            return
        except (OSError, requests.RequestException):
            pass
    print("Beat This! unavailable; the app uses librosa beat tracking as a fallback.", flush=True)


def hf_assets(base, name, specification):
    repo, revision, files = specification
    for filename, checksum in files.items():
        method = "git-blob" if len(checksum) == 40 else "sha256"
        yield (f"https://huggingface.co/{repo}/resolve/{revision}/{filename}", base / name / filename, checksum, method)


def essentia_assets(base):
    for name, path in ESSENTIA.items():
        for suffix in (".pb", ".json"):
            filename = name + suffix
            yield (ESSENTIA_BASE + path + suffix, base / "essentia" / filename, ESSENTIA_HASHES[filename], "sha256")


def prepare(base):
    tasks = [*hf_assets(base, "maest", MAEST), *hf_assets(base, "clap-unfused", CLAP), *essentia_assets(base)]

    def fetch(task):
        url, target, checksum, method = task
        for attempt in range(3):
            try:
                download(url, target, checksum, method)
                print(f"{target.relative_to(base)} · {target.stat().st_size / 1e6:.1f} MB", flush=True)
                break
            except (requests.RequestException, OSError):
                if attempt == 2:
                    raise

    with ThreadPoolExecutor(max_workers=5) as pool:
        list(pool.map(fetch, tasks))
    nemora = base / "nemorasonar"
    if not all(matches_checksum(nemora / name, digest, "sha256") for name, digest in NEMORA_HASHES.items()):
        archive = download(NEMORA_URL, base / "nemorasonar-download.zip", NEMORA_SHA)
        nemora.mkdir(exist_ok=True)
        with ZipFile(archive) as release:
            for name in NEMORA_HASHES:
                (nemora / name).write_bytes(release.read("NemoraSonar-Phonk-1.1/" + name))
        archive.unlink()
    prepare_beat(base)


if __name__ == "__main__":
    import sys
    prepare(Path(sys.argv[1]))

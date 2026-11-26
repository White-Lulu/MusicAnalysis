import hashlib
import json
import math
import os
import tempfile
from pathlib import Path
from zipfile import BadZipFile

import librosa
import numpy as np

from .signal import RATE, audible_portions, decode_audio, load_audio
from .taxonomy import STYLES, SCENES, CATALOG, canonical_label, rank_candidates
from .culture import VERSION as CULTURE_VERSION, culture_prompts, culture_evidence


INSTRUMENT = {"electricguitar": "电吉他", "acousticguitar": "原声吉他", "guitar": "吉他",
              "bass": "贝斯", "drums": "鼓组", "percussion": "打击乐", "voice": "人声",
              "synthesizer": "合成器", "drummachine": "鼓机", "piano": "钢琴", "electricpiano": "电钢琴",
              "keyboard": "键盘", "violin": "小提琴", "strings": "弦乐", "saxophone": "萨克斯",
              "trumpet": "小号", "flute": "长笛", "cello": "大提琴", "brass": "铜管", "organ": "管风琴"}
ESSENTIA_HOP = 256
DISCOGS_PATCH = 128
DISCOGS_STRIDE = 62
def window_start(y, center, size):
    return min(max(0, int(center * RATE) - size // 2), max(0, len(y) - size))


def interval_genres(matrix, spans, labels, threshold=.30, silences=()):
    matrix = np.asarray(matrix)
    weights = np.array([sum(b - a for a, b in audible_portions(start, end, silences)) for start, end in spans])
    duration = sum(end - start for start, end in spans)
    if not weights.any():
        return []
    average = np.average(matrix, axis=0, weights=weights)
    covered = weights @ (matrix >= threshold) / duration
    order = np.argsort(-(average + .2 * covered), kind="stable")
    selected = order[covered[order] > 0][:8]
    return [{
        "label": labels[index].split("---")[-1],
        "full_label": labels[index],
        "score": round(float(average[index]), 4),
        "coverage": float(100 * covered[index]),
    } for index in selected]


def top_tags(values, labels, translated=None, limit=8, minimum=.08):
    means = np.mean(values, axis=0)
    order = np.argsort(-means)[:limit]
    return [{"label": (translated or {}).get(labels[i], labels[i]), "id": labels[i],
             "score": round(float(means[i]), 4)} for i in order if means[i] >= minimum]


def instrument_evidence(values, labels):
    scores = np.asarray(values)
    means = np.mean(scores, axis=0)
    hits = np.count_nonzero(scores >= .25, axis=0)
    strong_hits = np.count_nonzero(scores >= .35, axis=0)
    peaks = np.max(scores, axis=0)
    order = np.argsort(-means, kind="stable")
    main = [i for i in order if strong_hits[i] * 5 >= len(scores)][:6]
    additional = [i for i in order if i not in main and hits[i] * 10 >= len(scores)][:min(2, 6 - len(main))]
    return [
        {"label": INSTRUMENT.get(labels[i], labels[i]), "id": labels[i],
         "score": round(float(means[i]), 4), "support": float(hits[i] / len(scores)),
         "peak_score": round(float(peaks[i]), 4), "supplementary": i in additional}
        for i in main + additional
    ]


def essentia_frames(y):
    # TensorflowInputMusiCNN uses area-normalized Slaney triangles ("unit_tri").
    magnitude = abs(librosa.stft(y, n_fft=512, hop_length=ESSENTIA_HOP, window=np.hanning(512)))
    mel = librosa.feature.melspectrogram(S=magnitude ** 2, sr=RATE, n_fft=512, n_mels=96, norm="slaney")
    return np.log10(1 + 10000 * mel).T.astype(np.float32)


def essentia_patches(frames, length, stride):
    data = np.pad(frames, ((0, max(0, length - len(frames))), (0, 0)), mode="edge")
    positions = list(range(0, len(data) - length + 1, stride))
    return positions, np.stack([data[start:start + length] for start in positions])


def normalize(vector):
    array = np.asarray(vector, dtype=np.float32)
    return array / np.maximum(np.linalg.norm(array, axis=-1, keepdims=True), 1e-12)


class Models:
    def __init__(self, root, device="cpu", cache_dir=None):
        self.root = Path(root)
        self.device = device
        self.maest = None
        self.clap = None
        self.beats = None
        self.nemora = None
        self.graphs = {}
        self.prompts = {}
        self.cache_dir = Path(cache_dir) if cache_dir else None

    def genre(self, y, silences=()):
        import torch
        from transformers import AutoFeatureExtractor, AutoModelForAudioClassification

        if self.maest is None:
            folder = self.root / "maest"
            feature = AutoFeatureExtractor.from_pretrained(folder, trust_remote_code=True, local_files_only=True)
            model = AutoModelForAudioClassification.from_pretrained(folder, local_files_only=True).to(self.device).eval()
            self.maest = feature, model
        feature, model = self.maest
        duration = len(y) / RATE
        stride = max(10, math.ceil(duration / 88))
        spans = [(float(start), min(float(start + stride), duration)) for start in range(0, math.ceil(duration), stride)]
        size = 30 * RATE
        indices = [window_start(y, (start + end) / 2, size) for start, end in spans]
        unique = list(dict.fromkeys(indices))
        evaluated = {}
        batch_size = 4 if self.device.startswith("cuda") else 2
        with torch.inference_mode():
            for index in range(0, len(unique), batch_size):
                batch = unique[index:index + batch_size]
                clips = [y[start:start + size] for start in batch]
                data = feature(clips, sampling_rate=RATE, return_tensors="pt")
                outputs = torch.sigmoid(model(input_values=data.input_values.to(self.device)).logits).cpu().numpy()
                evaluated.update(zip(batch, outputs))
        scores = [evaluated[start] for start in indices]
        labels = [model.config.id2label[i] for i in range(len(scores[0]))]
        return interval_genres(scores, spans, labels, silences=silences), stride

    def clap_components(self):
        from transformers import ClapModel, ClapProcessor
        if self.clap is None:
            folder = self.root / "clap-unfused"
            processor = ClapProcessor.from_pretrained(folder, local_files_only=True)
            model = ClapModel.from_pretrained(folder, local_files_only=True).to(self.device).eval()
            self.clap = processor, model
            controls = self.clap_text(["A solo piano performance.", "Heavy metal with distorted guitars.",
                                       "Birds chirping outdoors.", "A person speaking."])
            if np.min(controls @ controls.T) >= .98:
                self.clap = None
                raise ValueError("The audio-text model failed its text-discrimination check.")
        return self.clap

    def audio_cache_path(self, path, duration):
        if self.cache_dir is None:
            return None
        path = Path(path).resolve()
        source = path.stat()
        checkpoint = (self.root / "clap-unfused/pytorch_model.bin").stat()
        frontend = (self.root / "clap-unfused/preprocessor_config.json").stat()
        key = hashlib.sha256(json.dumps([str(path), source.st_size, source.st_mtime_ns, source.st_ctime_ns,
            round(duration, 4), checkpoint.st_size, checkpoint.st_mtime_ns, frontend.st_size,
            frontend.st_mtime_ns, "clap-unfused-audio-v1"]).encode()).hexdigest()
        return self.cache_dir / (key + ".npz")

    def clap_audio(self, path, duration):
        import torch
        processor, model = self.clap_components()
        cache = self.audio_cache_path(path, duration)
        if cache and cache.is_file():
            try:
                with np.load(cache, allow_pickle=False) as data:
                    vectors, rms = data["vectors"], data["rms"]
                    if (vectors.ndim == 2 and vectors.shape[1] == model.config.projection_dim and
                            0 < len(vectors) <= 8 and rms.shape == (len(vectors),) and
                            np.isfinite(vectors).all() and np.isfinite(rms).all() and
                            (np.linalg.norm(vectors, axis=1) > .9).all()):
                        return vectors, rms
            except (OSError, ValueError, KeyError, BadZipFile):
                pass
        count = min(8, max(1, math.ceil(duration / 13)))
        centers = [(index + .5) * duration / count for index in range(count)]
        frontend = processor.feature_extractor
        clip_seconds = frontend.max_length_s
        rate = frontend.sampling_rate
        max_start = max(0, duration - clip_seconds)
        starts = [min(max(0, center - clip_seconds / 2), max_start) for center in centers]
        unique = list(dict.fromkeys(starts))
        evaluated, amplitudes = {}, {}
        batch_size = 4 if self.device.startswith("cuda") else 2
        with torch.inference_mode():
            for index in range(0, len(unique), batch_size):
                batch = unique[index:index + batch_size]
                clips = [decode_audio(path, rate, start=start, seconds=clip_seconds) for start in batch]
                amplitudes.update((start, float(np.sqrt(np.mean(clip ** 2)))) for start, clip in zip(batch, clips))
                data = processor(audio=clips, sampling_rate=rate, return_tensors="pt")
                output = model.get_audio_features(**data.to(self.device))
                if not isinstance(output, torch.Tensor):
                    output = output.pooler_output
                evaluated.update(zip(batch, normalize(output.cpu().numpy())))
        vectors = np.stack([evaluated[start] for start in starts])
        rms = np.array([amplitudes[start] for start in starts], dtype=np.float32)
        if not np.isfinite(vectors).all() or not (np.linalg.norm(vectors, axis=1) > .9).all():
            raise ValueError("The audio-text model returned invalid audio features.")
        if cache:
            cache.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=cache.parent, suffix=".npz", delete=False) as output:
                temporary = Path(output.name)
                try:
                    np.savez_compressed(output, vectors=vectors, rms=rms)
                    output.close()
                    os.replace(temporary, cache)
                finally:
                    output.close()
                    temporary.unlink(missing_ok=True)
        return vectors, rms

    def clap_text(self, texts):
        import torch
        processor, model = self.clap_components()
        limit = min(processor.tokenizer.model_max_length, model.config.text_config.max_position_embeddings - 2)
        vectors = []
        with torch.inference_mode():
            for first in range(0, len(texts), 16):
                data = processor(text=texts[first:first + 16], padding=True, truncation=True,
                                 max_length=limit, return_tensors="pt")
                output = model.get_text_features(**data.to(self.device))
                if not isinstance(output, torch.Tensor):
                    output = output.pooler_output
                vectors.append(normalize(output.cpu().numpy()))
        result = np.concatenate(vectors)
        if not np.isfinite(result).all() or not (np.linalg.norm(result, axis=1) > .9).all():
            raise ValueError("The audio-text model returned invalid text features.")
        return result

    def semantics(self, path, duration, tag_settings, genres=(), culture_only=False):
        vectors, rms = self.clap_audio(path, duration)
        overrides = {canonical_label(label): text for label, text in tag_settings.items()}
        settings = {tag.label: overrides.get(tag.label, tag.description) for tag in STYLES}
        settings.update({label: text for label, text in overrides.items() if label not in CATALOG})
        fingerprint = hashlib.sha256(json.dumps(settings, sort_keys=True).encode()).hexdigest()
        if not culture_only and self.prompts.get("style", (None,))[0] != fingerprint:
            labels = list(settings)
            self.prompts["style"] = fingerprint, labels, self.clap_text(list(settings.values()))
        tags = SCENES
        descriptions = [text for tag in tags for pair in culture_prompts(tag) for text in pair]
        scene_fingerprint = hashlib.sha256(json.dumps([CULTURE_VERSION, descriptions]).encode()).hexdigest()
        if self.prompts.get("culture", (None,))[0] != scene_fingerprint:
            self.prompts["culture"] = scene_fingerprint, self.clap_text(descriptions).reshape(len(tags), 2, 3, -1)
        _, scene_vectors = self.prompts["culture"]
        if "presence" not in self.prompts:
            self.prompts["presence"] = self.clap_text(["The sound of a singing voice in music.",
                                                      "Instrumental music played only by musical instruments."])
        presence = vectors @ self.prompts["presence"].T
        vocal_margin = presence[:, 0] - presence[:, 1]
        scenes, metadata = culture_evidence(vectors, rms, tags, scene_vectors[:, 0], scene_vectors[:, 1],
                                           genres, vocal_margin)
        metadata["fingerprint"] = scene_fingerprint
        audible = vectors[rms >= .0001]
        styles = []
        if not culture_only and len(audible):
            _, labels, text_vectors = self.prompts["style"]
            styles = rank_candidates(labels, text_vectors @ normalize(audible.mean(axis=0)), genres)
        return {
            "candidates": styles + scenes, "culture": metadata,
            "source": "LAION CLAP HTSAT Unfused",
        }

    def beat_positions(self, path):
        from beat_this.inference import Audio2Beats
        if self.beats is None:
            self.beats = Audio2Beats(checkpoint_path=str(self.root / "beat-this" / "final0.ckpt"),
                                    device=self.device, dbn=False)
        beat_rate = 22050
        return self.beats(load_audio(path, rate=beat_rate), beat_rate)

    def brazilian_phonk(self, path):
        import onnxruntime as ort

        if self.nemora is None:
            root = self.root / "nemorasonar"
            options = ort.SessionOptions()
            options.intra_op_num_threads = 4
            model = ort.InferenceSession(str(root / "model.onnx"), sess_options=options,
                                         providers=["CPUExecutionProvider"])
            meta, labels = [json.loads((root / filename).read_text(encoding="utf-8"))
                            for filename in ("onnx_meta.json", "labels.json")]
            self.nemora = model, meta, labels
        model, meta, labels = self.nemora
        target_rate = meta["sample_rate"]
        waveform = load_audio(path, rate=target_rate)
        window, hop = meta["window_samples"], meta["hop_samples"]
        waveform = np.pad(waveform, (0, max(0, window - len(waveform))))
        last = len(waveform) - window
        starts = list(range(0, last + 1, hop))
        if starts[-1] != last:
            starts.append(last)
        if len(starts) > 32:
            starts = [starts[index] for index in np.linspace(0, len(starts) - 1, 32, dtype=int)]
        genre, scores, ordering = model.run(None, {meta["input"]: np.stack([
            waveform[start:start + window] for start in starts
        ]).astype(np.float32)})
        genre = labels["genres"][int(np.argmax(genre[0]))]
        tags = []
        if genre["id"] != "other_music":
            thresholds = meta["thresholds"]
            for index, (_, related, full, loose) in enumerate(scores[0]):
                if loose >= max(thresholds["loose"], full, related):
                    strength, style, rank = loose, "宽泛类别", loose
                elif full >= max(thresholds["full"], related):
                    strength, style, rank = full, "主要风格", ordering[0, index, 0]
                elif related >= thresholds["related"]:
                    strength, style, rank = related, "相近风格", ordering[0, index, 1]
                else:
                    continue
                tags.append((float(rank), {"label": labels["styles"][index]["name"], "type": style,
                                           "score": round(float(strength), 3)}))
        return {"genre": genre["name"], "is_phonk": genre["id"] != "other_music",
                "styles": [row for _, row in sorted(tags, key=lambda item: -item[0])],
                "source": meta["model"], "windows": len(starts)}

    def graph(self, name, output, data):
        import tensorflow as tf

        key = name, output
        if key not in self.graphs:
            folder = self.root / "essentia"
            meta = json.loads((folder / (name + ".json")).read_text(encoding="utf-8"))
            source = meta["schema"]["inputs"][0]["name"]
            graph_def = tf.compat.v1.GraphDef()
            graph_def.ParseFromString((folder / (name + ".pb")).read_bytes())
            wrapped = tf.compat.v1.wrap_function(lambda: tf.import_graph_def(graph_def, name=""), [])
            origin = wrapped.graph.get_tensor_by_name(source if ":" in source else source + ":0")
            target = wrapped.graph.get_tensor_by_name(output if ":" in output else output + ":0")
            self.graphs[key] = wrapped.prune(origin, target)
        return self.graphs[key](tf.convert_to_tensor(data, dtype=tf.float32)).numpy()

    def discogs_embeddings(self, frames):
        _, inputs = essentia_patches(frames, DISCOGS_PATCH, DISCOGS_STRIDE)
        embeddings = []
        for offset in range(0, len(inputs), 64):
            batch = inputs[offset:offset + 64]
            padded = np.pad(batch, ((0, 64 - len(batch)), (0, 0), (0, 0)))
            embeddings.append(self.graph("effnet", "PartitionedCall:1", padded)[:len(batch)])
        return np.concatenate(embeddings)

    def essentia_labels(self, name):
        return json.loads((self.root / "essentia" / (name + ".json")).read_text(encoding="utf-8"))["classes"]

    def instruments_from_embeddings(self, embeddings):
        scores = self.graph("instrument", "model/Sigmoid", embeddings)
        return instrument_evidence(scores, self.essentia_labels("instrument"))

    def jamendo_and_deam(self, y):
        frames = essentia_frames(y)
        embeddings = self.discogs_embeddings(frames)
        instruments = self.instruments_from_embeddings(embeddings)
        mood = self.graph("mood", "model/Sigmoid", embeddings)
        positions, inputs = essentia_patches(frames, 187, 93)
        values = []
        for offset in range(0, len(inputs), 32):
            batch = inputs[offset:offset + 32]
            vectors = self.graph("musicnn", "model/dense/BiasAdd", batch).reshape(len(batch), 200)
            values.append(self.graph("deam", "model/Identity", vectors).reshape(len(batch), 2))
        values = np.clip(np.concatenate(values), 1, 9)

        return instruments, {
            "tags": top_tags(mood, self.essentia_labels("mood"), limit=7, minimum=.02),
            "curve": [{"time": round(min((start + 93) * ESSENTIA_HOP / RATE, len(y) / RATE), 2),
                       "valence": round(float(valence), 2), "arousal": round(float(arousal), 2)}
                      for start, (valence, arousal) in zip(positions, values)],
            "source": "MTG-Jamendo + DEAM",
        }

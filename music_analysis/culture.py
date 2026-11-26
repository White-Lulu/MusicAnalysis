"""Conservative audio cues, compared with matched ordinary-music descriptions."""
import numpy as np

VERSION = 1
def culture_prompts(tag):
    name, description = tag.reference.split(" :: ", 1)
    return ((f"This is {tag.name} music.", f"Music featuring {tag.description}."),
            (f"This is {name} music.", f"Music featuring {description}."))
MIN_CONCEPT_SIMILARITY = .30
MIN_SOUND_SIMILARITY = .45
MIN_MARGIN = .02
WINDOW_MARGIN = .01
MIN_SUPPORT = .5
MIN_CONTEXT_COVERAGE = 20
VOCAL_CUES = {"cue-call-and-response", "cue-voice-recitation", "cue-family-chorus", "cue-sing-along",
              "cue-movement-song", "cue-gospel-choir", "cue-synthetic-singer", "cue-musical-theatre"}


def compatible_context(tag, genres):
    """Require independent genre context for claims with a narrow musical setting."""
    labels = [row.get("full_label", "") for row in genres if row.get("coverage", 0) >= MIN_CONTEXT_COVERAGE]
    if tag.family == "地区与传统":
        return any(label.startswith("Folk, World, & Country---") or any(
            word in label for word in ("Chinese Classical", "Indian Classical", "Gamelan", "Flamenco")) for label in labels)
    if tag.id == "cue-y2k":
        return any(label.startswith("Hip Hop---") or any(word in label for word in
            ("Synth-pop", "Contemporary R&B", "RnB/Swing", "Teen Pop", "Dance-pop", "UK Garage")) for label in labels)
    if tag.id == "cue-nineties-sampling":
        return any(label.startswith("Hip Hop---") and any(word in label for word in
            ("Boom Bap", "Instrumental", "Jazzy", "Jazz-Rap", "Abstract", "Turntablism")) or
            "Trip Hop" in label for label in labels)
    if tag.id == "cue-vintage-studio":
        return any(label.startswith(("Rock---", "Jazz---", "Funk / Soul---")) for label in labels)
    if tag.id == "cue-processional":
        return any(label.startswith("Brass & Military---") or "March" in label or
                   label.startswith("Folk, World, & Country---") for label in labels)
    if tag.id in {"cue-family-chorus", "cue-sing-along", "cue-movement-song"}:
        return any(label.startswith("Children's---") for label in labels)
    if tag.id in {"cue-club-build", "cue-festival-drop", "cue-warehouse-rave", "cue-ballroom-runway"}:
        return any(label.startswith("Electronic---") and not any(word in label for word in
            ("Ambient", "Downtempo", "IDM", "Drone", "New Age")) for label in labels)
    if tag.id == "cue-plugg-keys":
        return any(label.startswith("Hip Hop---") for label in labels)
    if tag.id in {"cue-diy-band", "cue-emo-dynamics", "cue-postrock-build"}:
        return any(label.startswith("Rock---") for label in labels)
    if tag.id == "cue-goth-electronic":
        return any(word in label for label in labels for word in ("Darkwave", "Goth", "Synth-pop", "Post-Punk"))
    if tag.id == "cue-ambient-immersive":
        return any(word in label for label in labels for word in ("Ambient", "Drone", "New Age"))
    if tag.id == "cue-experimental-collage":
        return any(word in label for label in labels for word in ("Glitch", "Breakcore", "Experimental", "Noise", "Avantgarde"))
    return True


def culture_evidence(vectors, rms, tags, positive, reference, genres=(), vocal_margin=None, mono_check=False):
    """Scores are contrastive evidence, never probabilities or cultural identity."""
    vectors = np.asarray(vectors)
    valid = np.isfinite(vectors).all(axis=1) & np.isfinite(rms) & (np.asarray(rms) >= .0001)
    minimum = MIN_MARGIN * (2 if valid.sum() == 1 else 1)
    metadata = {"version": VERSION, "status": "insufficient_evidence",
                "sampled_windows": len(vectors), "valid_windows": int(valid.sum()),
                "tested_labels": len(tags), "score_type": "contrastive_evidence",
                "criteria": {"concept_similarity": MIN_CONCEPT_SIMILARITY, "sound_similarity": MIN_SOUND_SIMILARITY, "mean_margin": minimum,
                             "window_margin": WINDOW_MARGIN, "support": MIN_SUPPORT,
                             "context_coverage": MIN_CONTEXT_COVERAGE}}
    if not valid.any():
        return [], metadata
    if not np.isfinite(positive).all() or not np.isfinite(reference).all():
        metadata["status"] = "invalid_model_features"
        return [], metadata
    similarity = np.einsum("wd,tpd->wtp", vectors[valid], positive)
    baseline = np.einsum("wd,tpd->wtp", vectors[valid], reference)
    gaps = similarity - baseline
    raw = similarity.mean(axis=(0, 2))
    prompt_similarity = similarity.mean(axis=0)
    margin = gaps.mean(axis=(0, 2))
    # Both phrasings must beat their matched references in a supporting window.
    hits = (gaps >= WINDOW_MARGIN).all(axis=2).sum(axis=0)
    support = hits / valid.sum()
    agreement = gaps.mean(axis=0).min(axis=1)
    ranking = []
    for index, tag in enumerate(tags):
        if (prompt_similarity[index, 0] < MIN_CONCEPT_SIMILARITY or prompt_similarity[index, 1] < MIN_SOUND_SIMILARITY or margin[index] < minimum or
                agreement[index] < WINDOW_MARGIN or support[index] < MIN_SUPPORT or not compatible_context(tag, genres)):
            continue
        if tag.id == "cue-early-mono" and not mono_check:
            continue
        if tag.id in VOCAL_CUES and (vocal_margin is None or np.mean(np.asarray(vocal_margin)[valid]) < .01 or
                                    np.mean(np.asarray(vocal_margin)[valid] >= .01) < MIN_SUPPORT):
            continue
        score = float(margin[index] * support[index])
        ranking.append({"label": tag.label, "label_en": tag.name, "id": tag.id, "kind": "scene", "family": tag.family,
                        "branch": tag.branch, "score": round(score, 4),
                        "audio_similarity": round(float(raw[index]), 4),
                        "reference_similarity": round(float(baseline[:, index].mean()), 4),
                        "margin": round(float(margin[index]), 4), "support": round(float(support[index]), 4),
                        "support_windows": int(hits[index]), "windows": int(valid.sum()),
                        "evidence": "Matched-reference contrast and window agreement"})
    ranking.sort(key=lambda row: (-row["score"], row["id"]))
    selected, families = [], set()
    for row in ranking:
        if row["family"] in families:
            continue
        selected.append(row)
        families.add(row["family"])
        if len(selected) == 3:
            break
    if selected:
        metadata["status"] = "matched"
    return selected, metadata

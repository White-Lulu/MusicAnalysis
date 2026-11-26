"""Aesthetic associations requiring a concept and two independent sound descriptions."""
import numpy as np

VERSION = 2
def culture_prompts(tag):
    return ((f"Music associated with {tag.name}.", *(f"Music featuring {cue.description}." for cue in tag.cues)),
            (f"Music associated with {tag.reference}.", *(f"Music featuring {cue.reference}." for cue in tag.cues)))
MIN_CONCEPT_SIMILARITY = .30
MIN_SOUND_SIMILARITY = .45
MIN_MARGIN = .02
WINDOW_MARGIN = .01
MIN_SUPPORT = .5
MIN_CONTEXT_COVERAGE = 20
MIN_CONCEPT_GAP = .01
VOCAL_CUES = {"cue-y2k", "cue-swag-2000s", "cue-digicore", "cue-scenecore", "cue-nightcore",
              "cue-synthetic-singer", "cue-emo-dynamics", "cue-goth-electronic", "cue-diy-band",
              "cue-ballroom-runway", "cue-musical-theatre", "cue-arabic-ensemble",
              "cue-west-african-strings", "cue-flamenco", "cue-gospel-choir", "cue-sacred-chant"}


def compatible_context(tag, genres):
    """Require independent genre context for claims with a narrow musical setting."""
    labels = [row.get("full_label", "") for row in genres if row.get("coverage", 0) >= MIN_CONTEXT_COVERAGE]
    return any(word in label for label in labels for word in tag.contexts)


def culture_evidence(vectors, rms, tags, positive, reference, genres=(), vocal_margin=None):
    """Scores are contrastive evidence, never probabilities or cultural identity."""
    vectors = np.asarray(vectors)
    valid = np.isfinite(vectors).all(axis=1) & np.isfinite(rms) & (np.asarray(rms) >= .0001)
    minimum = MIN_MARGIN * (2 if valid.sum() == 1 else 1)
    metadata = {"version": VERSION, "status": "insufficient_evidence",
                "sampled_windows": len(vectors), "valid_windows": int(valid.sum()),
                "tested_labels": len(tags), "score_type": "aesthetic_evidence",
                "criteria": {"concept_similarity": MIN_CONCEPT_SIMILARITY, "sound_similarity": MIN_SOUND_SIMILARITY, "mean_margin": minimum,
                             "window_margin": WINDOW_MARGIN, "support": MIN_SUPPORT,
                             "context_coverage": MIN_CONTEXT_COVERAGE, "sound_descriptions": 2,
                             "competing_concept_gap": MIN_CONCEPT_GAP}}
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
    # The concept and both sound descriptions must agree within the same excerpt.
    hits = (gaps >= WINDOW_MARGIN).all(axis=2).sum(axis=0)
    support = hits / valid.sum()
    agreement = gaps.mean(axis=0).min(axis=1)
    ranking = []
    for index, tag in enumerate(tags):
        if (prompt_similarity[index, 0] < MIN_CONCEPT_SIMILARITY or prompt_similarity[index, 1:].min() < MIN_SOUND_SIMILARITY or margin[index] < minimum or
                agreement[index] < WINDOW_MARGIN or support[index] < MIN_SUPPORT or not compatible_context(tag, genres)):
            continue
        if tag.id in VOCAL_CUES and (vocal_margin is None or np.mean(np.asarray(vocal_margin)[valid]) < .01 or
                                    np.mean(np.asarray(vocal_margin)[valid] >= .01) < MIN_SUPPORT):
            continue
        score = float(agreement[index] * support[index])
        ranking.append({"label": tag.label, "label_en": tag.name, "id": tag.id, "kind": "scene", "family": tag.family,
                        "branch": tag.branch, "score": round(score, 4),
                        "audio_similarity": round(float(raw[index]), 4),
                        "reference_similarity": round(float(baseline[:, index].mean()), 4),
                        "margin": round(float(margin[index]), 4), "support": round(float(support[index]), 4),
                        "support_windows": int(hits[index]), "windows": int(valid.sum()),
                        "interpretation": tag.interpretation, "interpretation_en": tag.interpretation_en,
                        "concept_similarity": round(float(prompt_similarity[index, 0]), 4),
                        "concept_margin": round(float(gaps[:, index, 0].mean()), 4),
                        "sound_evidence": [
                            {"label": cue.label, "label_en": cue.name,
                             "similarity": round(float(prompt_similarity[index, view]), 4),
                             "margin": round(float(gaps[:, index, view].mean()), 4),
                             "support_windows": int(np.count_nonzero(gaps[:, index, view] >= WINDOW_MARGIN)),
                             "windows": int(valid.sum())}
                            for view, cue in enumerate(tag.cues, 1)],
                        "evidence": "Concept and two matched-reference sound descriptions; excerpt agreement"})
    ranking.sort(key=lambda row: (-row["score"], row["id"]))
    ambiguous = set()
    for row in ranking:
        for other in ranking:
            if row["id"] != other["id"] and row["branch"] == other["branch"] and abs(row["concept_margin"] - other["concept_margin"]) < MIN_CONCEPT_GAP:
                ambiguous.update((row["id"], other["id"]))
    metadata["ambiguous_concepts"] = len(ambiguous)
    selected, families, branches = [], set(), set()
    for row in ranking:
        if row["family"] in families or row["branch"] in branches or row["id"] in ambiguous:
            continue
        selected.append(row)
        families.add(row["family"])
        branches.add(row["branch"])
        if len(selected) == 3:
            break
    if selected:
        metadata["status"] = "matched"
    return selected, metadata

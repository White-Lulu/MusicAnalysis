from collections import Counter, defaultdict
from math import isfinite, sqrt
from statistics import mean, median
from .culture import VERSION as CULTURE_VERSION
from .taxonomy import CATALOG


MOOD_AXES = ("valence", "arousal")
MOOD_BOUNDS = (4.5, 5.5)
VALENCE_TONES = ("偏沉郁", "明暗居中", "偏明快")
AROUSAL_TONES = ("较平静", "激发程度居中", "推动感较强")


def percentile(ordered, fraction):
    rank = (len(ordered) - 1) * fraction
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (rank - lower)


def track_mood(curve):
    pairs = [tuple(row.get(axis) for axis in MOOD_AXES) for row in curve]
    valid = [pair for pair in pairs if all(isinstance(value, (int, float)) and isfinite(value) and
                                          1 <= value <= 9 for value in pair)]
    result = {"windows": len(valid)}
    if not valid:
        return result
    for axis, column in zip(MOOD_AXES, zip(*valid)):
        values = sorted(column)
        result[axis] = mean(values)
        result[axis + "_median"] = round(median(values), 2)
        if len(values) >= 5:
            result[axis + "_range"] = [round(percentile(values, p), 2) for p in (.1, .9)]
    return result


def mood_band(value):
    low, high = MOOD_BOUNDS
    return 0 if value < low else 2 if value > high else 1


def drive_and_tone(counts, total, english=False):
    energy = list(map(sum, counts))
    tones = list(map(sum, zip(*counts)))
    dominant = max(range(3), key=energy.__getitem__)
    energy_words = ("calm", "moderate in arousal", "high in energy and drive") if english else AROUSAL_TONES
    tone_words = ("somber", "balanced", "bright") if english else VALENCE_TONES
    if total == 1:
        if english:
            return f"This track is generally {energy_words[dominant]}, with a {tone_words[tones.index(1)]} emotional tone."
        return f"这首歌整体{AROUSAL_TONES[dominant]}，情绪底色{VALENCE_TONES[tones.index(1)]}。"
    if energy[dominant] >= .6 * total:
        focus = counts[dominant]
        scope = f"这 {energy[dominant]} 首歌里"
        result = f"{energy[dominant]}/{total} 首{AROUSAL_TONES[dominant]}。"
        if english:
            scope = f"Among these {energy[dominant]} tracks"
            result = f"{energy[dominant]} of {total} tracks are {energy_words[dominant]}. "
    else:
        focus = tones
        scope = "全部有听感数据的曲目里"
        result = f"整体激发程度各有分布，偏平静 {energy[0]} 首、居中 {energy[1]} 首、偏激发 {energy[2]} 首。"
        if english:
            scope = "Across the selection"
            result = f"Arousal varies, with {energy[0]} calm, {energy[1]} moderate and {energy[2]} high-energy tracks. "
    common_tone = max(range(3), key=focus.__getitem__)
    if min(focus[0], focus[2]) >= max(2, .25 * sum(focus)):
        if english:
            return result + f"{scope}, {focus[0]} are somber and {focus[2]} are bright. Both tones recur in your selection."
        result += f"{scope}，{focus[0]} 首偏沉郁，{focus[2]} 首偏明快，两种情绪底色都常出现在选曲中。"
    elif focus[common_tone] >= .6 * sum(focus):
        if english:
            return result + f"{scope}, {focus[common_tone]} have a {tone_words[common_tone]} emotional tone."
        result += f"{scope}，有 {focus[common_tone]} 首的情绪底色{VALENCE_TONES[common_tone]}。"
    else:
        if english:
            return result + f"{scope}, {focus[0]} are somber, {focus[1]} balanced and {focus[2]} bright."
        result += f"{scope}，偏沉郁 {focus[0]} 首、明暗居中 {focus[1]} 首、偏明快 {focus[2]} 首。"
    return result


def separated_mood_groups(coordinates):
    minimum = max(2, .2 * len(coordinates))
    best = (0, 0.)
    groups = []
    # Inspect both axes and the two diagonals, using actual gaps between songs.
    for slope_x, slope_y in ((1, 0), (0, 1), (1, 1), (1, -1)):
        norm = sqrt(slope_x**2 + slope_y**2)
        projections = sorted(((x * slope_x + y * slope_y) / norm, x, y) for x, y in coordinates)
        splits = [i for i in range(1, len(projections)) if projections[i][0] - projections[i - 1][0] >= 1]
        edges = [0, *splits, len(projections)]
        spans = [(start, end) for start, end in zip(edges, edges[1:]) if end - start >= minimum]
        if len(spans) < 2:
            continue
        gap = min(projections[next_start][0] - projections[end - 1][0]
                  for (_, end), (next_start, _) in zip(spans, spans[1:]))
        quality = (sum(end - start for start, end in spans), gap)
        if quality > best:
            best = quality
            groups = [(end - start, median(x for _, x, _ in projections[start:end]),
                       median(y for _, _, y in projections[start:end])) for start, end in spans]
    return sorted(groups, key=lambda group: (-group[0], group[1], group[2]))


def taste_distribution(points, axes, english=False):
    total = len(points)
    if total < 4:
        if english:
            return "Add a few more tracks to assess whether your selection is focused or forms distinct groups."
        return "当前曲目较少，再加入几首后可判断选曲是否集中或分群。"
    coordinates = [tuple(point[axis + "_median"] for axis in MOOD_AXES) for point in points]
    groups = separated_mood_groups(coordinates) if total >= 6 else []
    if groups:
        if english:
            descriptions = [f"One group has {size} tracks with a {('somber', 'balanced', 'bright')[mood_band(x)]} tone "
                            f"and {('low', 'moderate', 'high')[mood_band(y)]} arousal "
                            f"(median valence {x:.2f}, arousal {y:.2f})" for size, x, y in groups]
            other = total - sum(group[0] for group in groups)
            tail = f" Another {other} tracks sit outside these groups." if other else ""
            return f"The selection tentatively forms {len(groups)} groups. " + ". ".join(descriptions) + "." + tail
        descriptions = [f"一群有 {size} 首，整体{VALENCE_TONES[mood_band(x)]}、{AROUSAL_TONES[mood_band(y)]}"
                        f"（效价 {x:.2f}，唤醒度 {y:.2f}）" for size, x, y in groups]
        other = total - sum(group[0] for group in groups)
        tail = f"，另有 {other} 首分布在其他区域" if other else ""
        return f"当前选曲初步呈现 {len(groups)} 群。" + "。".join(descriptions) + tail + "。括号里是各群的中位数。"
    center_x, center_y = (axes[axis]["median"] for axis in MOOD_AXES)
    near = sum(abs(x - center_x) <= .75 and abs(y - center_y) <= .75 for x, y in coordinates)
    if near >= 2 * total / 3:
        if english:
            return (f"The overall feel is concentrated, with {near} of {total} tracks close to the median on both axes. "
                    f"The common direction is {('somber', 'balanced', 'bright')[mood_band(center_x)]} "
                    f"with {('low', 'moderate', 'high')[mood_band(center_y)]} arousal.")
        return (f"选曲的总体听感较集中，{near}/{total} 首在两轴上都接近中位数。"
                f"常见的底色是{VALENCE_TONES[mood_band(center_x)]}、{AROUSAL_TONES[mood_band(center_y)]}。")
    valence_width, arousal_width = (axes[axis]["middle_half"][1] - axes[axis]["middle_half"][0] for axis in MOOD_AXES)
    if english:
        if abs(valence_width - arousal_width) < .5:
            variation = "Valence and arousal span similar ranges across tracks. "
        elif valence_width > arousal_width:
            variation = "Emotional brightness varies more than arousal across tracks. "
        else:
            variation = "Arousal varies more than emotional brightness across tracks. "
        grouping = "At least 6 tracks are needed to assess grouping." if total < 6 else "No groups have enough support yet."
        return "Your selection spans a broad range of overall moods. " + variation + grouping
    if abs(valence_width - arousal_width) < .5:
        variation = "整体明暗与激发程度的跨度相近。"
    elif valence_width > arousal_width:
        variation = "曲目间的情绪明暗，比激发程度变化更大。"
    else:
        variation = "曲目间的激发程度，比情绪明暗变化更大。"
    grouping = "至少有 6 首曲目后再判断分群。" if total < 6 else "暂未看到有足够曲目支撑的分群。"
    return "选曲的总体听感较分散。" + variation + grouping


def track_dynamics(points, axes, english=False):
    swings = [round(max(point[axis + "_range"][1] - point[axis + "_range"][0] for axis in MOOD_AXES), 2)
              for point in points if all(axis + "_range" in point for axis in MOOD_AXES)]
    count = len(swings)
    if not count:
        if english:
            return "At least 5 valid analysis windows per track are needed to assess changes within a song."
        return "曲目需要至少 5 个有效分析窗，才可估计曲内听感起伏。"
    steady = sum(value <= 1 for value in swings)
    strong = sum(value >= 2 for value in swings)
    medium = count - steady - strong
    if english:
        text = f"Among {count} tracks with enough data, {steady} are steady, {medium} vary moderately and {strong} vary strongly. "
        if count < 3 or count * 2 < len(points):
            return text + "More tracks are needed to assess your preference for these changes."
        if steady >= .6 * count:
            text += "Your selection mostly sustains a steady atmosphere. "
        elif strong >= .6 * count:
            text += "Your selection mostly features strong changes within each song. "
        elif medium >= .6 * count:
            text += "Moderate variation is most common. "
        elif min(steady, strong) >= .25 * count:
            text += "Both steady atmospheres and strong changes recur. "
        else:
            text += "The amount of change varies across tracks. "
        difference = round(axes["valence"]["typical_swing"] - axes["arousal"]["typical_swing"], 2)
        if difference >= .5:
            text += "Emotional brightness usually changes more within a song."
        elif difference <= -.5:
            text += "Arousal usually changes more within a song."
        return text.strip()
    text = f"{count} 首可估计起伏的曲目里，{steady} 首较稳定、{medium} 首起伏适中、{strong} 首起伏明显。"
    if count < 3 or count * 2 < len(points):
        return text + "可估计的曲目较少，起伏偏好还需更多数据。"
    if steady >= .6 * count:
        text += "这组选曲多保持相对稳定的氛围。"
    elif strong >= .6 * count:
        text += "这组选曲多在一首歌内出现明显的听感变化。"
    elif medium >= .6 * count:
        text += "选曲以适度变化为主。"
    elif min(steady, strong) >= .25 * count:
        text += "稳定的氛围和明显的曲内变化，在选曲里都占有一定比例。"
    else:
        text += "曲内起伏幅度各有分布。"
    difference = round(axes["valence"]["typical_swing"] - axes["arousal"]["typical_swing"], 2)
    if difference >= .5:
        text += "单曲内部，情绪明暗的变化通常更明显。"
    elif difference <= -.5:
        text += "单曲内部，激发程度的变化通常更明显。"
    return text


def listening_profile(points):

    counts = [[0, 0, 0] for _ in range(3)]
    for point in points:
        x, y = (mood_band(point[axis + "_median"]) for axis in MOOD_AXES)
        counts[y][x] += 1

    axes = {}
    if points:
        for axis in MOOD_AXES:
            values = sorted(point[axis + "_median"] for point in points)
            data = {"median": round(median(values), 2)}
            if len(values) >= 4:
                data["middle_half"] = [round(percentile(values, p), 2) for p in (.25, .75)]
            ranges = [point[axis + "_range"] for point in points if axis + "_range" in point]
            if ranges:
                data["typical_swing"] = round(median(high - low for low, high in ranges), 2)
            axes[axis] = data
    observations = []
    if points:
        observations = [
            {"title": "推动感与情绪底色", "text": drive_and_tone(counts, len(points)),
             "text_en": drive_and_tone(counts, len(points), english=True)},
            {"title": "口味集中与分群", "text": taste_distribution(points, axes),
             "text_en": taste_distribution(points, axes, english=True)},
            {"title": "稳定氛围与曲内起伏", "text": track_dynamics(points, axes),
             "text_en": track_dynamics(points, axes, english=True)},
        ]
    return {"points": points, "bounds": MOOD_BOUNDS, "axes": axes, "observations": observations}


def semantic_candidates(report):
    selected, seen, branches = [], set(), set()
    counts = Counter()
    for row in report.get("semantic", {}).get("candidates", []):
        kind, label, score = row.get("kind"), row.get("label"), row.get("score")
        if kind not in {"style", "scene"} or not label or counts[kind] >= 3 or (kind, label) in seen:
            continue
        if kind == "scene" and report.get("semantic", {}).get("culture", {}).get("version") != CULTURE_VERSION:
            continue
        if not isinstance(score, (int, float)) or not isfinite(score) or not -1 <= score <= (2 if kind == "scene" else 1):
            continue
        branch = (row.get("family"), row["branch"]) if row.get("branch") else (label,)
        if kind == "style":
            if branch in branches:
                continue
            branches.add(branch)
        seen.add((kind, label))
        counts[kind] += 1
        selected.append({"label": label, "kind": kind, "score": score})
        if counts["style"] == counts["scene"] == 3:
            break
    return selected


def profile_fields(report):
    harmony = report.get("harmony", {})
    mood = report.get("mood", {})
    result = {"rhythm": {"bpm": report.get("rhythm", {}).get("bpm")},
              "harmony": {key: harmony.get(key) for key in ("key", "key_evidence", "strength")},
              "genres": [{key: row[key] for key in ("label", "full_label", "score", "coverage") if key in row}
                         for row in report.get("genres", [])],
              "mood": {"source": mood.get("source"), "tags": mood.get("tags", []),
                       **track_mood(mood.get("curve", []))},
              "issues": report.get("issues", {}),
              "semantic": {"candidates": semantic_candidates(report),
                           "culture": report.get("semantic", {}).get("culture", {})}}
    return result


def summarize_tracks(tracks, weighted=True):
    """One vote per distinct analysed recording, independent of time and play history."""
    usable = [track for track in tracks if track["state"] == "done" and track["report"] is not None]
    distributions = defaultdict(Counter)
    occurrences = defaultdict(Counter)
    eligible = Counter()
    tempos = defaultdict(list)
    emotion = defaultdict(list)
    mood_points = []

    def register(dimension, label, weight=1.0):
        if not label or weight <= 0:
            return
        occurrences[dimension][label] += 1
        distributions[dimension][label] += weight

    for track in usable:
        report = track["report"]
        candidates = semantic_candidates(report)
        for kind in {item["kind"] for item in candidates if item["kind"] == "style"}:
            eligible[kind] += 1
        culture = report.get("semantic", {}).get("culture", {})
        if culture.get("version") == CULTURE_VERSION and culture.get("valid_windows", 0):
            eligible["scene"] += 1
        for item in candidates:
            dimension, label = item["kind"], item["label"]
            distributions[dimension][label] += item["score"]
            occurrences[dimension][label] += 1
        rhythm = report.get("rhythm", {})
        if bpm := rhythm.get("bpm"):
            band = int(bpm // 10) * 10
            tempos[band].append({"id": track["id"], "title": track["title"], "artist": track["artist"],
                                 "bpm": bpm, "weight": 1.0})
        harmony = report.get("harmony", {})
        if key := harmony.get("key"):
            values = harmony.get("key_evidence") or {}
            score = max(.0, min(1.0, values.get("score", harmony.get("strength") or .5)))
            eligible["keys"] += 1
            if weighted and values.get("alternative") and values.get("margin", 1) < .1:
                runner = min(.5, (.1 - max(0.0, values["margin"])) * 5)
                register("keys", values["alternative"], score * runner)
                register("keys", key, score * (1 - runner))
            else:
                register("keys", key, score if weighted else 1)
        genres = report.get("genres", [])
        if genres:
            eligible["genres"] += 1
            families = Counter()
            for item in genres:
                score = (item["score"] if weighted else 1) * item["coverage"] / 100
                full_label = item.get("full_label", item["label"])
                family = full_label.split("---", 1)[0]
                families[family] = max(families[family], score)
                register("genres", full_label.replace("---", " › "), score)
            for family, score in families.items():
                register("genre_families", family, score)
        if "Essentia" not in report.get("issues", {}) and (report.get("mood") or {}).get("source"):
            eligible["moods"] += 1
            for item in report["mood"].get("tags", []):
                if item["score"] >= .05:
                    label = item["label"]
                    score = item["score"] if weighted else 1
                    register("moods", label, score)
            for axis in MOOD_AXES:
                if (value := report["mood"].get(axis)) is not None:
                    emotion[axis].append(value)
            mood = report["mood"]
            if mood.get("windows"):
                point = {key: track[key] for key in ("id", "title", "artist")}
                point["windows"] = mood["windows"]
                for axis in MOOD_AXES:
                    point[axis + "_median"] = mood[axis + "_median"]
                    if axis + "_range" in mood:
                        point[axis + "_range"] = mood[axis + "_range"]
                mood_points.append(point)
    def rows(dimension, base, limit=16):
        ordered = sorted(distributions[dimension].items(), key=lambda item: (-round(item[1], 12), item[0]))
        return [{"label": label, "share": round(100 * value / base, 1),
                 "tracks": occurrences[dimension][label]} for label, value in ordered[:limit]] if base else []

    def semantic_profile(kind):
        ordered = sorted(distributions[kind].items(), key=lambda item: (-round(item[1], 12), item[0]))
        return {"tracks": eligible[kind], "rows": [
            {"label": label, "score": round(score, 4), "tracks": occurrences[kind][label],
             **({"label_en": CATALOG[label].name,
                 "interpretation": CATALOG[label].interpretation,
                 "interpretation_en": CATALOG[label].interpretation_en,
                 "sound_evidence": [{"label": cue.label, "label_en": cue.name} for cue in CATALOG[label].cues]}
                if kind == "scene" and label in CATALOG else {})}
            for label, score in ordered[:6]]}

    key_scores = distributions["keys"]
    key_total = sum(key_scores.values())
    key_modes = []
    if key_total:
        major = sum(score for key, score in key_scores.items() if key.endswith(" 大调"))
        major_share = round(100 * major / key_total, 1)
        key_modes = [{"label": "大调", "share": major_share}, {"label": "小调", "share": round(100 - major_share, 1)}]

    bpm_count = sum(map(len, tempos.values()))
    bpm_bands = []
    if bpm_count:
        for band in range(min(tempos), max(tempos) + 10, 10):
            members = tempos.get(band, [])
            bpm_bands.append({"label": f"{band}–{band + 9}", "share": round(100 * len(members) / bpm_count, 1),
                              "count": len(members), "tracks": members})
    return {
        "track_count": len(tracks), "analysed": len(usable), "bpm_count": bpm_count,
        "pending": sum(track["state"] in {"queued", "running"} for track in tracks),
        "errors": sum(track["state"] == "error" for track in tracks),
        "tempo_median": round(median(t["bpm"] for entries in tempos.values() for t in entries), 1) if bpm_count else None,
        "bpm": bpm_bands, "weighted": weighted,
        "emotion": {axis: round(mean(values), 2) for axis, values in emotion.items()},
        "emotion_profile": listening_profile(mood_points),
        "genres": rows("genres", eligible["genres"]),
        "keys": rows("keys", eligible["keys"]),
        "moods": rows("moods", eligible["moods"]),
        "genre_profile": {"tracks": eligible["genres"], "rows": rows("genre_families", eligible["genres"], 6)},
        "key_profile": {"tracks": eligible["keys"], "modes": key_modes, "rows": rows("keys", key_total, 3)},
        "mood_profile": {"tracks": eligible["moods"], "rows": rows("moods", eligible["moods"], 6)},
        "microgenre_profile": semantic_profile("style"),
        "culture_profile": semantic_profile("scene"),
    }

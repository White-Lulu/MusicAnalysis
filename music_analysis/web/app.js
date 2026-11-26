"use strict";

const $ = (id) => document.getElementById(id);
const t = UI.t;
const TOKEN = document.querySelector('meta[name="local-token"]').content;
const state = { track: null, tracks: [], batch: "", weighted: true, tempoBand: null,
  emotionMetric: "valence", audioTrack: null, libraryLoaded: false };
const audio = $("audio");
const importButtons = [$("choose-files"), $("choose-folder")];
const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)");
const statuses = { queued: "等待分析", running: "分析中", done: "已分析", error: "分析失败" };
const sleeveArt = ["01-botanical-shadow", "02-ocean-nocturne", "03-mountain-mist", "04-ivory-bloom",
  "05-ink-drift", "07-city-after-rain", "08-heron-flight", "09-cobalt-interlock", "10-silver-facets",
  "11-indigo-herbarium", "12-stone-halftone", "13-silver-afterglow",
  "14-branch-impressions", "15-tidal-print", "16-lunar-archive", "17-eroded-ridges", "18-window-afterimage"];
const sleeveSlots = new Map();
const sleeveCounts = sleeveArt.map(() => 0);
let noticeTimer, pendingPlayhead, playbackFallback = false, lastListRequest = 0, summaryRequest = 0;

function element(tag, text = "", className = "") {
  const node = document.createElement(tag);
  if (text !== "") node.textContent = text;
  if (className) node.className = className;
  return node;
}

function button(text, onClick, type = "secondary") {
  const node = element("button", text, type);
  node.type = "button";
  node.addEventListener("click", () => Promise.resolve(onClick()).catch(showError));
  return node;
}

async function request(url, body, method = "POST") {
  const options = body === undefined ? {} : {
    method, headers: {"Content-Type": "application/json", "X-Local-Token": TOKEN},
    body: JSON.stringify(body),
  };
  const response = await fetch(url, options);
  const value = await response.json();
  if (!response.ok) throw new Error(typeof value.detail === "string" ? value.detail : "请求的数据格式有误。");
  return value;
}

function notice(text) {
  clearTimeout(noticeTimer);
  state.notice = typeof text === "function" ? text : () => t(text);
  renderNotice();
  $("notice").hidden = false;
  noticeTimer = setTimeout(() => { $("notice").hidden = true; }, 4500);
}

function renderNotice() { if (state.notice) $("notice").textContent = state.notice(); }

function showError(error) { notice(() => failureDetails(error.files) || t(error.message) || t("操作失败。")); }

function failureDetails(errors = []) {
  return errors.slice(0, 3).map(error => error.file + " · " + t(error.reason)).join(" / ");
}
function secondsLabel(n) { return Math.floor(n / 60) + ":" + String(Math.floor(n % 60)).padStart(2, "0"); }
function percent(n) { return n + "%"; }
function coverageLabel(n) { return n > 0 && n < .1 ? t("不足 0.1%") : percent(Number(n.toFixed(1))); }

function pageHeader(title, describe, tools, context = "") {
  const row = element("div", "", "page-head");
  const caption = element("div", "", "page-title");
  if (context) caption.append(element("span", context, "page-context"));
  caption.append(element("h2", title));
  if (describe) caption.append(element("p", describe));
  row.append(caption);
  if (tools.length) {
    const actions = element("div", "", "tools");
    actions.append(...tools);
    row.append(actions);
  }
  return row;
}

function card(title, subtitle = "") {
  const box = element("section", "", "card");
  box.append(element("h2", title));
  if (subtitle) box.append(element("p", subtitle, "info"));
  return box;
}

function stats(rows) {
  const grid = element("section", "", "summary-grid");
  for (const [title, value, note] of rows) {
    const tile = element("div", "", "stat");
    tile.append(element("small", title), element("strong", value));
    if (note) tile.append(element("small", note));
    grid.append(tile);
  }
  return grid;
}

function sleeveIndex(id) {
  if (!sleeveSlots.has(id)) {
    const minimum = Math.min(...sleeveCounts);
    let slot = Number.parseInt(id.slice(0, 8), 16) % sleeveCounts.length;
    while (sleeveCounts[slot] > minimum) slot = (slot + 1) % sleeveCounts.length;
    sleeveSlots.set(id, slot);
    sleeveCounts[slot]++;
  }
  return sleeveSlots.get(id);
}

function sleeve(index) {
  const art = element("span", "", "sleeve");
  art.dataset.sleeve = index;
  art.style.backgroundImage = `url("/assets/sleeves/${sleeveArt[index]}.webp?v=palette-2")`;
  art.setAttribute("aria-hidden", "true");
  return art;
}

function dataBar(value) {
  const track = element("div", "", "bar-bg");
  const mark = element("span");
  mark.style.width = Math.min(100, Math.max(0, value)) + "%";
  track.append(mark);
  return track;
}

function resultRows(rows, makeRight, makeExtra) {
  const list = element("div");
  for (const item of rows) {
    const row = element("div", "", "tag-row");
    row.append(element("strong", UI.language === "en" && item.label_en ? item.label_en : UI.label(item.label), "tag-title"), makeRight(item));
    const extra = makeExtra?.(item);
    if (extra) {
      extra.classList.add("extra");
      row.append(extra);
    }
    list.append(row);
  }
  if (!rows.length) list.append(element("p", t("暂无可显示结果。"), "compact-empty"));
  return list;
}

function drawSeries(container, series, config) {
  const canvas = element("canvas", "", "chart");
  canvas.setAttribute("role", "img");
  canvas.setAttribute("aria-label", config.title);
  container.append(canvas);
  const observer = new ResizeObserver(render);
  observer.observe(canvas);
  const root = document.documentElement;
  const theme = new MutationObserver(render);
  theme.observe(root, {attributes: true, attributeFilter: ["data-theme"]});
  const detach = new MutationObserver(() => {
    if (!canvas.isConnected) {
      observer.disconnect();
      theme.disconnect();
      detach.disconnect();
    }
  });
  detach.observe($("layout"), {childList: true, subtree: true});

  function render() {
    const width = canvas.clientWidth, height = canvas.clientHeight, dpr = window.devicePixelRatio || 1;
    if (width < 75 || height < 50) return;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    const context = canvas.getContext("2d");
    context.scale(dpr, dpr);
    const palette = getComputedStyle(canvas);
    const token = name => palette.getPropertyValue(name).trim();
    const plot = { left: config.unit ? 43 : 30, right: width - 12, top: 13, bottom: height - 25 };
    const xRange = config.xRange;
    const all = series.flatMap(line => line.points.map(point => point[1]).filter(Number.isFinite));
    if (!all.length) {
      context.fillStyle = token("--muted");
      context.font = "12px " + token("--ui");
      context.fillText(t("暂无可绘制数据"), plot.left, height / 2);
      return;
    }
    const min = config.min ?? Math.min(...all);
    const max = Math.max(min + 1, config.max ?? Math.max(...all));
    const toX = (x) => xRange[0] === xRange[1] ? (plot.left + plot.right) / 2 :
      plot.left + (x - xRange[0]) / (xRange[1] - xRange[0]) * (plot.right - plot.left);
    const toY = (y) => plot.bottom - (y - min) / (max - min) * (plot.bottom - plot.top);
    canvas.onclick = config.click ? event => {
      const offset = event.clientX - canvas.getBoundingClientRect().left;
      const fraction = Math.max(0, Math.min(1, (offset - plot.left) / (plot.right - plot.left)));
      config.click(xRange[0] + fraction * (xRange[1] - xRange[0]));
    } : null;
    canvas.style.cursor = config.click ? "pointer" : "default";
    context.font = "11px " + token("--mono");
    context.fillStyle = token("--muted");
    context.setLineDash([2, 4]);
    for (let i = 0; i <= 4; i++) {
      const y = min + (max - min) * i / 4;
      const position = toY(y);
      context.beginPath();
      context.strokeStyle = token("--grid-line");
      context.moveTo(plot.left, position);
      context.lineTo(plot.right, position);
      context.stroke();
      context.textAlign = "right";
      context.fillText(Math.round(y * 10) / 10 + (config.unit || ""), plot.left - 5, position + 3);
    }
    context.setLineDash([]);
    const steps = xRange[0] === xRange[1] ? 0 : config.ordinal ? Math.min(4, xRange[1] - xRange[0]) : 4;
    const ticks = new Set(Array.from({length: steps + 1}, (_, index) => {
      const value = xRange[0] + (xRange[1] - xRange[0]) * index / Math.max(1, steps);
      return config.ordinal ? Math.round(value) : value;
    }));
    for (const x of ticks) {
      context.textAlign = ticks.size === 1 ? "center" : x === xRange[0] ? "left" : x === xRange[1] ? "right" : "center";
      context.fillText(config.label(x), toX(x), height - 6);
    }
    series.forEach((line, index) => {
      context.fillStyle = context.strokeStyle = token(line.color || "--series-" + (index + 1));
      context.lineWidth = 2;
      context.setLineDash(line.color === "--series-2" ? [5, 3] : []);
      context.lineJoin = "round";
      context.beginPath();
      let started = false;
      for (const [x, y] of line.points) {
        if (!Number.isFinite(y)) { started = false; continue; }
        if (!started) context.moveTo(toX(x), toY(y));
        else context.lineTo(toX(x), toY(y));
        started = true;
      }
      context.stroke();
      for (const [i, [x, y]] of line.points.entries()) {
        if (!Number.isFinite(y)) continue;
        if (line.points.length > 16 && (Number.isFinite(line.points[i - 1]?.[1]) ||
          Number.isFinite(line.points[i + 1]?.[1]))) continue;
        context.beginPath();
        context.arc(toX(x), toY(y), 3, 0, Math.PI * 2);
        context.fill();
      }
    });
  }
  if (series.length > 1) {
    const legend = element("div", "", "chart-legend");
    series.forEach((line, index) => {
      const label = element("span", line.name);
      label.style.setProperty("--series", "var(" + (line.color || "--series-" + (index + 1)) + ")");
      legend.append(label);
    });
    container.append(legend);
  }
  return canvas;
}

function layoutSections(...sections) {
  const group = element("div", "", "sections");
  group.append(...sections);
  return group;
}

function columns(className, ...sections) {
  const group = element("div", "", "grid " + className);
  group.append(...sections);
  return group;
}

function shelfView() {
  const host = $("shelf");
  $("track-count").textContent = state.tracks.length + t(" 首");
  const search = $("search").value.trim();
  const subtitle = !state.libraryLoaded ? t("正在读取曲库…") : state.tracks.length ? "" :
    search ? t("没有匹配的曲目。") : t("导入音频后，可打开曲目的分析报告。");
  if (!state.tracks.length) {
    host.replaceChildren(element("p", subtitle, "compact-empty"));
    return;
  }

  const shelf = element("section", "", "record-shelf");
  shelf.setAttribute("aria-label", t("唱片架曲目"));
  for (const track of state.tracks) {
    const tile = button("", async () => {
      await selectTrack(track.id);
      if (state.track?.id === track.id) navigateTo("analysis");
    }, "record-tile");
    tile.dataset.track = track.id;
    tile.setAttribute("aria-pressed", String(state.track?.id === track.id));
    const facts = element("span", "", "record-facts");
    facts.append(element("strong", track.title), element("small", track.artist || t("未知艺人")));
    if (track.state !== "done") facts.append(element("small", t(statuses[track.state]), "record-status"));
    const image = element("span", "", "sleeve-frame");
    image.append(sleeve(sleeveIndex(track.id)));
    tile.append(image, facts);
    shelf.append(tile);
  }
  host.replaceChildren(shelf);
}

function libraryView() {
  const host = $("view");
  const track = state.track;
  if (!track) {
    host.replaceChildren(pageHeader(t("单曲解析"), t("从曲库选择一首歌，查看曲风、乐器、情绪和听感变化。"), []));
    return;
  }
  const data = track.report;
  const download = element("a", t("导出 JSON"), "secondary");
  download.href = "/api/tracks/" + track.id + "/report";
  const retry = button(t("重新分析"), async () => {
    await request("/api/tracks/" + track.id + "/retry", {});
    await selectTrack(track.id);
  });
  const edit = button(t("编辑曲目信息"), () => editMetadata(track));
  const back = button(t("返回曲库"), () => navigateTo("library"), "quiet");
  const head = pageHeader(track.title, [track.artist || t("未知艺人"), track.duration && secondsLabel(track.duration), t(statuses[track.state])].filter(Boolean).join(" · "),
    track.state === "done" ? [back, edit, retry, download] : track.state === "error" ? [back, retry, edit] : [back, edit], t("单曲报告"));
  const cover = element("div", "", "report-cover sleeve-frame");
  cover.append(sleeve(sleeveIndex(track.id)));
  head.append(cover);
  host.replaceChildren(head);
  if (!data || track.state !== "done") {
    const task = card(t(statuses[track.state]), t(track.error) || t("分析在本机排队进行。可以先播放歌曲或导入其他曲目。"));
    host.append(task);
    return;
  }
  const rhythm = data.rhythm, harmony = data.harmony;
  const overview = stats([
    [t("主速度"), rhythm.bpm ? rhythm.bpm + " BPM" : t("待定"), UI.label(rhythm.source)],
    [t("主调"), UI.label(harmony.key) || t("待定"), harmony.key_evidence ?
      t("匹配 ") + harmony.key_evidence.score.toFixed(2) + t(" · 次选 ") + UI.label(harmony.key_evidence.alternative) : UI.label(harmony.source)],
    [t("曲风候选"), data.genres[0]?.label || t("暂无"), data.genres[0] ? t("覆盖 ") + coverageLabel(data.genres[0].coverage) : ""],
    [t("拍点"), rhythm.beat_count, rhythm.beats_per_bar ? t("约每小节 ") + rhythm.beats_per_bar + t(" 拍") : ""],
  ]);
  const genre = card(t("曲风覆盖"), t("覆盖比例按独立时间区间计算。同一时间可以命中多个标签。"));
  genre.append(resultRows(data.genres, row =>
    element("small", t("覆盖 ") + coverageLabel(row.coverage) + t(" · 匹配 ") + row.score.toFixed(2), "tag-score")));
  if (data.genre_bin) genre.append(element("p", t("每 ") + data.genre_bin + t(" 秒估计一次，模型使用约 30 秒的音频上下文。"), "info"));
  const instruments = card(t("乐器与情绪标签"), t("最多 6 项，含最多 2 项较弱的补充线索。支持窗按匹配分 0.25 计算，分数来自 MTG-Jamendo。"));
  const instrumentScore = item => element("small", t("均分 ") + item.score.toFixed(3) +
    (Number.isFinite(item.support) ? t(" · 支持窗 ") + (item.support * 100).toFixed(2) + "%" : ""), "tag-score");
  instruments.append(resultRows(data.instruments, instrumentScore, item =>
    Number.isFinite(item.peak_score) ? element("small", (item.supplementary ? t("补充线索 · ") : "") +
      t("最高窗 ") + item.peak_score.toFixed(3), "info") : null));
  const themes = element("div", "", "tag-list mood-tags");
  for (const item of data.mood.tags) themes.append(element("span", UI.label(item.label) + " " + item.score.toFixed(2), "tag"));
  instruments.append(element("hr"), element("h3", t("情绪候选")), themes);

  const mood = card(t("听感变化"), t("效价从负面到正面，唤醒度从平静到激发。两者都是模型估计，范围 1–9。"));
  mood.classList.add("featured-chart");
  const emotionModes = element("div", "", "mode");
  const emotionPlot = element("div", "", "chart-surface");
  const axes = [["valence", t("效价")], ["arousal", t("唤醒度")], ["both", t("叠加")]];
  const emotionButtons = axes.map(([id, title]) => button(title, () => {
    state.emotionMetric = id;
    plotEmotion();
  }, "secondary active-control"));
  emotionModes.append(...emotionButtons);
  mood.append(emotionModes, emotionPlot);
  function plotEmotion() {
    emotionPlot.replaceChildren();
    emotionButtons.forEach((control, index) => control.setAttribute("aria-pressed", String(axes[index][0] === state.emotionMetric)));
    const lines = axes.slice(0, 2).filter(([id]) => state.emotionMetric === "both" || state.emotionMetric === id)
      .map(([id, title]) => ({name: title, color: id === "valence" ? "--series-1" : "--series-2",
        points: data.mood.curve.map(point => [point.time, point[id]])}));
    drawSeries(emotionPlot, lines, {title: t("情绪效价和唤醒度"), min: 1, max: 9, xRange: [0, data.duration], label: secondsLabel, click: seek});
  }
  plotEmotion();

  const candidates = data.semantic.candidates || [];
  const branches = new Set();
  const styles = [];
  for (const row of candidates) {
    if (row.kind !== "style") continue;
    const branch = row.branch ? row.family + " / " + row.branch : row.label;
    if (branches.has(branch)) continue;
    branches.add(branch);
    styles.push(row);
    if (styles.length === 3) break;
  }
  const score = item => element("small", item.score.toFixed(3), "tag-score");
  const semantic = card(t("微曲风候选"), t("每个分支取一个候选。排序参考曲风覆盖，显示 CLAP 相似度。"));
  semantic.append(resultRows(styles, score, item => item.branch && element("small", UI.label(item.branch), "info")));

  const culture = card(t("文化审美倾向"), t("最多三项审美关联，附文化解读与声音依据；不据此认定年代、地域或身份。"));
  const scenes = candidates.filter(row => row.kind === "scene");
  if (scenes.length) culture.append(resultRows(scenes,
    item => element("small", t("证据 ") + item.score.toFixed(3), "tag-score"),
    cultureDetails));
  else culture.append(element("p", t("暂无有充分声音依据的文化审美倾向。"), "compact-empty"));
  head.append(overview);
  const stylesAndCulture = layoutSections(genre, semantic, culture);
  const report = layoutSections(columns("analysis-grid", layoutSections(mood, instruments), stylesAndCulture));
  host.append(report);
  if (data.phonk?.is_phonk) {
    const phonk = card(t("Brazilian Phonk 专项候选"));
    phonk.append(resultRows(data.phonk.styles.slice(0, 3),
      item => element("small", t(item.type) + " · " + item.score.toFixed(3))));
    stylesAndCulture.append(phonk);
  }
  if (Object.keys(data.issues).length) {
    const details = element("details", "", "card");
    details.append(element("summary", t("分析模块状态")));
    for (const [name, error] of Object.entries(data.issues)) details.append(element("p", name + " · " + t(error)));
    report.append(details);
  }
}

function editMetadata(track) {
  const dialog = element("dialog", "", "card");
  const form = element("form", "", "form-stack");
  const [title, artist] = [element("input"), element("input")];
  title.required = true;
  title.value = track.title;
  artist.value = track.artist;
  const titleLabel = element("label", t("歌名"));
  const artistLabel = element("label", t("艺人"));
  titleLabel.append(title);
  artistLabel.append(artist);
  const submit = element("button", t("保存"), "primary");
  submit.type = "submit";
  form.append(element("h2", t("编辑曲目信息")), titleLabel, artistLabel, submit,
    button(t("取消"), () => dialog.close(), "quiet"));
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      await request("/api/tracks/" + track.id + "/metadata", {title: title.value, artist: artist.value}, "PATCH");
      dialog.close();
      await selectTrack(track.id);
    } catch (error) { showError(error); }
  });
  dialog.append(form);
  dialog.addEventListener("close", () => dialog.remove(), {once: true});
  document.body.append(dialog);
  dialog.showModal();
}

function emotionCard(profile, analysed) {
  const {points, bounds, axes, observations} = profile;
  const panel = card(t("听感画像"), points.length + " / " + analysed + t(" 首已分析曲目有听感数据 · 每首等权"));
  if (!points.length) {
    panel.append(element("p", t("暂无可用于听感画像的数据。"), "compact-empty"));
    return panel;
  }
  const report = element("div", "", "emotion-report");
  report.append(element("h3", t("选曲听感报告")), element("p", points.length < 8 ?
    t("基于当前 ") + points.length + t(" 首有数据的曲目，样本较少。") : t("基于当前选曲的听感估计。"), "info"));
  const findings = element("dl");
  for (const observation of observations) {
    findings.append(element("dt", t(observation.title)), element("dd", UI.language === "en" ? observation.text_en : observation.text));
  }
  report.append(findings);

  const names = [["valence", t("效价")], ["arousal", t("唤醒度")]];
  const fmt = value => value.toFixed(2);
  const formatRange = range => range.map(fmt).join("–");
  const metricCards = stats(names.map(([axis, name]) => {
    const {median, middle_half, typical_swing} = axes[axis];
    const details = [];
    if (middle_half) details.push(t("曲目中间一半 ") + formatRange(middle_half));
    if (Number.isFinite(typical_swing)) details.push(t("单曲典型起伏 ") + fmt(typical_swing));
    return [name + t("中位数"), fmt(median) + " / 9", details.join(" · ")];
  }));
  metricCards.classList.add("emotion-metrics");

  const plot = element("div", "", "emotion-plane");
  plot.setAttribute("role", "group");
  plot.setAttribute("aria-label", t("曲目散点图。横轴效价，纵轴唤醒度"));
  const position = value => (value - 1) * 12.5 + "%";
  for (const bound of bounds) {
    const vertical = element("span", "", "emotion-guide vertical");
    vertical.style.left = position(bound);
    const horizontal = element("span", "", "emotion-guide horizontal");
    horizontal.style.bottom = position(bound);
    plot.append(vertical, horizontal);
  }
  const chart = element("div", "", "emotion-chart");
  chart.append(element("span", t("唤醒度"), "info"));
  const frame = element("div", "", "emotion-frame");
  const ticks = element("div", "", "emotion-ticks");
  ticks.append(...[9, 5, 1].map(n => element("small", String(n))));
  frame.append(ticks, plot);
  const axis = element("div", "", "emotion-x");
  axis.append(element("small", "1"), element("small", t("5 · 效价")), element("small", "9"));
  chart.append(frame, axis);

  const detail = element("div", "", "emotion-detail");
  detail.setAttribute("aria-live", "polite");
  detail.hidden = true;
  chart.append(element("p", t("每个点代表一首歌。点击点查看单曲听感。"), "info"), detail, metricCards);
  panel.append(columns("emotion-layout", chart, report));

  let activeDot;
  function choose(point, dot) {
    activeDot?.setAttribute("aria-pressed", "false");
    activeDot = dot;
    activeDot.setAttribute("aria-pressed", "true");
    detail.hidden = false;
    detail.replaceChildren(element("p", point.title + (point.artist ? " · " + point.artist : "")),
      element("p", names.map(([key, label]) => label + " " + fmt(point[key + "_median"])).join(" · "), "info"));
    if (point.valence_range && point.arousal_range) {
      detail.append(element("p", names.map(([key, label]) =>
        label + " " + formatRange(point[key + "_range"])).join(" · ") + t("（曲内中间 80%）"), "info"));
    }
    detail.append(button(t("打开单曲分析"), () => openFromSummary(point.id), "quiet"));
  }

  for (const point of points) {
    const dot = button("", () => choose(point, dot), "emotion-dot");
    dot.title = point.title + t(" · 效价 ") + fmt(point.valence_median) + t(" · 唤醒度 ") + fmt(point.arousal_median);
    dot.setAttribute("aria-label", dot.title);
    dot.style.left = position(point.valence_median);
    dot.style.bottom = position(point.arousal_median);
    dot.setAttribute("aria-pressed", "false");
    plot.append(dot);
  }
  return panel;
}

const genreFamilies = {
  Electronic: "电子", Rock: "摇滚", Jazz: "爵士", Classical: "古典", Pop: "流行", Blues: "布鲁斯",
  "Hip Hop": "嘻哈", "Funk / Soul": "放克／灵魂乐", "Latin": "拉丁", Reggae: "雷鬼",
  "Folk, World, & Country": "民谣／地区传统／乡村", "Stage & Screen": "舞台／影视",
  "Brass & Military": "铜管／军乐", "Children's": "儿童音乐", "Non-Music": "声音作品",
};

function directionChart(rows, maximum = Math.max(5, Math.ceil(rows[0].share / 5) * 5)) {
  const chart = element("div", "", "profile-chart");
  const scale = element("div", "", "profile-scale");
  scale.append(element("small", "0%"), element("small", percent(maximum)));
  const list = resultRows(rows, item => element("small",
    (item.share ? coverageLabel(item.share) : "0%") + (item.tracks ? " · " + item.tracks + t(" 首") : ""), "tag-score"),
  item => dataBar(item.share / maximum * 100));
  list.classList.add("profile-rows");
  chart.append(scale, list);
  return chart;
}

function directionProfile(title, profile, note, examples = []) {
  const {tracks} = profile;
  const rows = profile.rows.map(row => ({...row, label: UI.label(row.label)}));
  const panel = card(title, t("基于 ") + tracks + t(" 首有相关分析的曲目。") + note);
  if (!rows.length) {
    panel.append(element("p", t("暂无足够的匹配证据。"), "compact-empty"));
    return panel;
  }
  const [lead, next] = rows;
  const nearby = rows.slice(1, 3).filter(row => row.share >= .75 * lead.share);
  const description = nearby.length ? t("证据较接近的方向有") + [lead, ...nearby].map(row => row.label).join(t("、")) + t("。") :
    t("当前选曲最偏向") + lead.label + t("，有 ") + lead.tracks + t(" 首出现这一方向。") + (next ? t("其次是") + next.label + t("。") : "");
  panel.append(element("p", description, "profile-reading"), directionChart(rows));
  if (examples.length) panel.append(element("p", t("这一门类里较明显的细分风格有 ") + examples.join(t("、")) + t("。"), "info"));
  return panel;
}

function cultureDetails(item) {
  const detail = element("div", "", "culture-reading");
  const reading = UI.language === "en" ? item.interpretation_en : item.interpretation;
  if (reading) detail.append(element("p", reading, "culture-interpretation"));
  if (item.sound_evidence?.length) detail.append(element("p", t("声音依据（描述匹配）：") +
    item.sound_evidence.map(cue => UI.language === "en" ? cue.label_en : cue.label).join(" · "), "info"));
  if (Number.isFinite(item.support_windows)) detail.append(element("small",
    t("支持片段 ") + item.support_windows + " / " + item.windows, "info"));
  return detail;
}

function semanticProfile(title, profile, culture = false) {
  const panel = card(title, t("基于 ") + profile.tracks + t(" 首有相关分析的曲目。") +
    t(culture ? "累加有声音依据的文化审美关联，最多显示六项；证据不足的曲目不分配标签。" :
      "同一曲目只计一次，累加各曲目前三项候选的匹配分数。"));
  if (culture && !profile.rows.length) {
    panel.append(element("p", t("暂无有充分声音依据的文化审美倾向。"), "compact-empty"));
    return panel;
  }
  const maximum = Math.max(0, ...profile.rows.map(row => row.score));
  panel.append(resultRows(profile.rows, row => element("small",
    t(culture ? "累计证据 " : "累计 ") + row.score.toFixed(3) + " · " + row.tracks + t(" 首"), "tag-score"),
  row => {
    const extra = culture ? cultureDetails(row) : element("div");
    if (row.score > 0 && maximum > 0) extra.prepend(dataBar(row.score / maximum * 100));
    return extra;
  }));
  return panel;
}

function tonalityCard({tracks, modes, rows}) {
  const panel = card(t("调性画像"), t("基于 ") + tracks + t(" 首有主调估计的曲目。大小调份额按全部调性证据归一化。"));
  if (!modes.length) {
    panel.append(element("p", t("暂无可汇总的调性。"), "compact-empty"));
    return panel;
  }
  const [major, minor] = modes;
  const ratio = major.share >= 60 ? t("大调的证据更多。") : minor.share >= 60 ? t("小调的证据更多。") : t("大调和小调的证据比较接近。");
  const leading = rows[0];
  const description = ratio + (tracks < 3 ? t("当前样本较少。") : leading.share >= 35 ?
    t("最集中的具体调性是 ") + UI.label(leading.label) + t("。") : t("具体调性分布较分散。"));
  panel.append(element("p", description, "profile-reading"), directionChart(modes, 100),
    element("p", t("证据较多的具体调性有 ") + rows.map(row => UI.label(row.label) + " (" + percent(row.share) + ")").join(t("、")) + t("。"), "info"));
  return panel;
}

async function collectionView() {
  const sequence = ++summaryRequest;
  const query = new URLSearchParams({weighted: String(state.weighted)});
  if (state.batch) query.set("batch", state.batch);
  const [batches, summary] = await Promise.all([request("/api/batches"), request("/api/collection?" + query)]);
  if (sequence !== summaryRequest) return;
  state.collectionPending = summary.pending;
  state.summary = summary;
  state.batches = batches;
  renderCollection();
}

function renderCollection() {
  if (!state.summary) return;
  const {summary, batches} = state;
  const host = $("collection-view");

  const scope = element("select");
  scope.setAttribute("aria-label", t("汇总范围"));
  const everything = element("option", t("全部提交"));
  everything.value = "";
  scope.append(everything);
  for (const batch of batches) {
    const option = element("option", UI.batchLabel(batch.label, batch.id) + " · " + batch.count + t(" 首"));
    option.value = batch.id;
    scope.append(option);
  }
  scope.value = state.batch;
  scope.addEventListener("change", () => {
    state.batch = scope.value;
    state.tempoBand = null;
    collectionView().catch(showError);
  });
  const weight = element("select");
  weight.setAttribute("aria-label", t("画像加权方式"));
  for (const [value, title] of [["true", t("按分析证据加权")], ["false", t("每首等权")]]) {
    const option = element("option", title);
    option.value = value;
    weight.append(option);
  }
  weight.value = String(state.weighted);
  weight.addEventListener("change", () => {
    state.weighted = weight.value === "true";
    collectionView().catch(showError);
  });
  const title = state.batch ? t("批次汇总") : t("全部提交画像");
  const caption = !summary.track_count ? t("上传至少一首歌，完成分析后即可在这里查看汇总。") :
    state.batch ? UI.batchLabel(summary.label, state.batch) : t("每首不同的歌曲独立计入。");
  const head = pageHeader(title, caption, [scope, weight]);
  host.replaceChildren(head);
  if (!summary.track_count) return;
  const overview = stats([
    [t("提交"), summary.track_count + t(" 首"), t("按内容去重")],
    [t("已分析"), summary.analysed + t(" 首"), summary.pending ? summary.pending + t(" 首排队或分析中") : t("已完成本批")],
    [t("中位 BPM"), summary.tempo_median ? summary.tempo_median + " BPM" : t("待定"), summary.bpm_count + t(" 首有速度")],
    [t("分析失败"), summary.errors + t(" 首"), summary.errors ? t("可打开单曲查看原因") : ""],
  ]);
  const speed = card(t("速度分布"), t("按 10 BPM 分组，可查看每个区间的曲目。"));
  const bands = summary.bpm;
  const items = element("div", "", "timeline-list");
  const picker = element("select");
  picker.setAttribute("aria-label", t("速度区间"));
  const first = bands[0] ? parseInt(bands[0].label, 10) : 0;
  function selectBand(index) {
    const band = bands[index];
    if (!band) return;
    state.tempoBand = band.label;
    picker.value = band.label;
    items.replaceChildren(...band.tracks.map(track => button(track.title + " · " + track.bpm + " BPM",
      () => openFromSummary(track.id), "timeline-row")));
    if (!items.childElementCount) items.append(element("p", t("该区间暂无曲目。"), "compact-empty"));
  }
  const speedPlot = element("div", "", "chart-surface");
  speed.append(speedPlot);
  drawSeries(speedPlot, [{name: t("曲目占比"), points: bands.map((band, i) => [first + i * 10, band.share])}],
    {title: t("速度分布"), min: 0, unit: "%", xRange: [first, first + Math.max(0, bands.length - 1) * 10],
      label: (value) => Math.round(value) + " BPM", click: x => selectBand(Math.round((x - first) / 10))});
  for (const band of bands) {
    const option = element("option", band.label + " BPM · " + band.count + t(" 首"));
    option.value = band.label;
    picker.append(option);
  }
  picker.addEventListener("change", () => selectBand(bands.findIndex(band => band.label === picker.value)));
  if (bands.length) {
    speed.append(picker, items);
    selectBand(Math.max(0, bands.findIndex(band => band.label === state.tempoBand)));
  }
  const genres = summary.genre_profile;
  const leadingFamily = genres.rows[0]?.label;
  const examples = summary.genres.filter(row => row.label.startsWith(leadingFamily + " › "))
    .slice(0, 3).map(row => row.label.split(" › ")[1]);
  const genre = directionProfile(t("曲风画像"), {...genres,
    rows: genres.rows.map(row => ({...row, label: genreFamilies[row.label] || row.label}))},
    t("条形长度表示平均曲风覆盖证据。每首歌在同一门类只取证据最强的子曲风。门类可重叠。"), examples);
  const subgenres = directionProfile(t("细分曲风排名"), {tracks: genres.tracks,
    rows: summary.genres.slice(0, 10).map(row => {
      const [family, ...style] = row.label.split(" › ");
      return {...row, label: [UI.label(genreFamilies[family] || family), ...style].join(" › ")};
    })}, t("按平均覆盖证据排序，显示前十项；加权方式与大类画像一致。"));
  const mood = directionProfile(t("情绪标签画像"), summary.mood_profile,
    t("汇总单曲的原始情绪候选，显示前十项；标签可重叠。") +
    (summary.weighted ? t("百分比是平均标签匹配证据。") : t("百分比是出现该标签的曲目比例。")));
  mood.classList.add("split-ranking");
  const emotion = emotionCard(summary.emotion_profile, summary.analysed);
  head.append(overview);
  host.append(layoutSections(emotion, columns("genre-overview", genre, subgenres,
    layoutSections(tonalityCard(summary.key_profile), speed)),
    columns("analysis-grid", semanticProfile(t("微曲风画像"), summary.microgenre_profile),
      semanticProfile(t("文化审美画像"), summary.culture_profile, true)),
    mood));
}

async function importMusic(selected, batchTitle = "") {
  if (!selected.length) return;
  if (state.importing) throw new Error("正在导入，请稍候。");
  state.importing = true;
  importButtons.forEach(control => { control.disabled = true; });
  try {
    const {extensions} = await formatsReady;
    const supported = new Set(extensions);
    const files = Array.from(selected).filter(file => supported.has("." + file.name.split(".").pop().toLowerCase()));
    if (!files.length) throw new Error("没有找到支持的音频文件。");
    if (files.length > 50 || files.some(file => file.size > 120 * 1024 * 1024) ||
        files.reduce((size, file) => size + file.size, 0) > 1024 * 1024 * 1024) {
      throw new Error("每批最多 50 首、合计 1 GiB，单个文件最多 120 MiB。");
    }
    const form = new FormData();
    files.forEach(file => form.append("files", file));
    if (batchTitle) form.append("title", batchTitle.slice(0, 120));
    notice(() => t("正在提交 ") + files.length + t(" 首歌曲…"));
    const response = await fetch("/api/uploads", {method: "POST", headers: {"X-Local-Token": TOKEN}, body: form});
    const result = await response.json();
    if (!response.ok) {
      const error = new Error(typeof result.detail === "string" ? result.detail : "上传失败。");
      error.files = result.errors;
      throw error;
    }
    await refresh();
    notice(() => t("已提交 ") + result.count + t(" 首。")
      + (result.errors?.length ? t("其中 ") + result.errors.length + t(" 个文件未能加入。") + failureDetails(result.errors) : ""));
    if (result.count === 1) {
      await selectTrack(result.ids[0]);
      navigateTo("analysis");
    } else {
      state.batch = result.batch;
      await collectionView();
      navigateTo("collection");
    }
  } finally {
    $("upload-files").value = "";
    $("upload-folder").value = "";
    state.importing = false;
    importButtons.forEach(control => { control.disabled = false; });
  }
}

async function droppedMusic(transfer) {
  const entries = Array.from(transfer.items || []).filter(item => item.kind === "file")
    .map(item => item.webkitGetAsEntry?.()).filter(Boolean);
  if (!entries.length) return {files: Array.from(transfer.files), title: ""};
  const files = [];
  async function collect(entry) {
    if (entry.isFile) {
      files.push(await new Promise((resolve, reject) => entry.file(resolve, reject)));
      return;
    }
    const reader = entry.createReader();
    // Chromium returns directory entries in batches, often 100 at a time.
    let children;
    do {
      children = await new Promise((resolve, reject) => reader.readEntries(resolve, reject));
      for (const child of children) await collect(child);
    } while (children.length);
  }
  for (const entry of entries) await collect(entry);
  return {files, title: entries.length === 1 && entries[0].isDirectory ? entries[0].name : ""};
}

function navigateTo(section) {
  if (section === "preferences") section = "collection";
  if (!$(section)) section = "top";
  history.replaceState(null, "", "#" + section);
  $(section).scrollIntoView({block: "start", behavior: reducedMotion.matches ? "instant" : "smooth"});
}

function revealOnScroll() {
  if (reducedMotion.matches || !("IntersectionObserver" in window)) return;
  const selector = ".intro-copy,.upload-panel,.section-heading,.record-tile,.page-head,.card";
  const targets = root => [...(root.matches(selector) ? [root] : []), ...root.querySelectorAll(selector)];
  const revealed = new Set();
  const observer = new IntersectionObserver(entries => {
    for (const {target, isIntersecting} of entries) {
      if (!isIntersecting) continue;
      target.classList.add("is-visible");
      revealed.add(target.dataset.revealKey);
      observer.unobserve(target);
    }
  }, {threshold: .04});
  function watch(root) {
    for (const node of targets(root)) {
      if (node.classList.contains("reveal")) continue;
      const scope = node.closest(".page-section")?.id || "top";
      const key = node.dataset.track ? "record:" + node.dataset.track :
        scope + ":" + Array.from($(scope).querySelectorAll(selector)).indexOf(node);
      node.dataset.revealKey = key;
      node.classList.add("reveal");
      if (revealed.has(key)) node.classList.add("is-visible");
      else observer.observe(node);
    }
  }
  watch($("layout"));
  new MutationObserver(records => {
    for (const record of records) {
      for (const node of record.removedNodes) {
        if (node instanceof Element && !node.isConnected) for (const target of targets(node)) observer.unobserve(target);
      }
      for (const node of record.addedNodes) if (node instanceof Element) watch(node);
    }
  }).observe($("layout"), {childList: true, subtree: true});
}

async function openFromSummary(id) {
  await selectTrack(id);
  if (state.selected === id) navigateTo("analysis");
}

async function refresh(automatic = false, includeSummary = true) {
  const sequence = ++lastListRequest;
  const next = await request("/api/tracks?q=" + encodeURIComponent($("search").value));
  if (sequence !== lastListRequest) return;
  const prior = state.track && next.find(track => track.id === state.track.id);
  const updated = JSON.stringify(state.tracks) !== JSON.stringify(next);
  if (!automatic || updated) {
    state.tracks = next;
    state.libraryLoaded = true;
    shelfView();
  }
  if (prior && prior.id === state.selected && prior.state !== state.track.state) await selectTrack(prior.id);
  if (includeSummary && (!automatic || updated || state.collectionPending)) await collectionView();
}

async function selectTrack(id) {
  state.selected = id;
  const item = await request("/api/tracks/" + id);
  if (state.selected !== id) return;
  state.track = item;
  for (const tile of $("shelf").querySelectorAll(".record-tile")) {
    tile.setAttribute("aria-pressed", String(tile.dataset.track === id));
  }
  libraryView();
  $("player").hidden = false;
  $("player-title").textContent = item.title;
  $("player-artist").textContent = item.artist;
  if (state.audioTrack !== id) {
    state.audioTrack = id;
    pendingPlayhead = null;
    playbackFallback = false;
    audio.src = "/api/tracks/" + id + "/audio";
  }
}

function seek(time) {
  if (!state.track || !Number.isFinite(time)) return;
  const at = Math.min(time, state.track.duration ?? time);
  if (audio.readyState) audio.currentTime = at;
  else pendingPlayhead = at;
  audio.play().catch(showError);
}

audio.addEventListener("loadedmetadata", () => { if (pendingPlayhead !== null) audio.currentTime = pendingPlayhead; pendingPlayhead = null; });
audio.addEventListener("error", () => {
  if (playbackFallback || !state.audioTrack) {
    notice("音频无法读取。请检查原文件，必要时重新导入。");
    return;
  }
  playbackFallback = true;
  pendingPlayhead ??= audio.currentTime;
  audio.src = "/api/tracks/" + state.audioTrack + "/audio?compatible=true";
});
for (const [buttonId, inputId] of [["choose-files", "upload-files"], ["choose-folder", "upload-folder"]]) {
  $(buttonId).addEventListener("click", () => $(inputId).click());
  $(inputId).addEventListener("change", () => {
    const files = Array.from($(inputId).files);
    const title = inputId === "upload-folder" ? files[0]?.webkitRelativePath.split("/")[0] || "" : "";
    importMusic(files, title).catch(showError);
  });
}
const importZone = $("import-zone");
let dragDepth = 0;
importZone.addEventListener("dragenter", event => {
  if (!Array.from(event.dataTransfer.types).includes("Files")) return;
  event.preventDefault();
  dragDepth++;
  importZone.classList.add("drag-over");
});
importZone.addEventListener("dragover", event => {
  if (Array.from(event.dataTransfer.types).includes("Files")) {
    event.preventDefault();
    event.dataTransfer.dropEffect = "copy";
  }
});
importZone.addEventListener("dragleave", () => {
  dragDepth = Math.max(0, dragDepth - 1);
  if (!dragDepth) importZone.classList.remove("drag-over");
});
importZone.addEventListener("drop", async event => {
  event.preventDefault();
  dragDepth = 0;
  importZone.classList.remove("drag-over");
  try {
    const {files, title} = await droppedMusic(event.dataTransfer);
    await importMusic(files, title);
  } catch (error) { showError(error); }
});
for (const link of document.querySelectorAll('.topbar a[href^="#"]')) {
  link.addEventListener("click", event => {
    event.preventDefault();
    navigateTo(link.hash.slice(1));
  });
}
$("search").addEventListener("input", () => refresh(false, false).catch(showError));

const themeToggle = $("theme-toggle");
UI.apply();
$("language-toggle").addEventListener("click", () => {
  UI.setLanguage(UI.language === "en" ? "zh" : "en");
  shelfView();
  libraryView();
  renderCollection();
  renderNotice();
});
const formatsReady = request("/api/formats");
formatsReady.then(result => { $("upload-files").accept = result.extensions.join(","); }).catch(showError);
function setTheme(dark) {
  document.documentElement.dataset.theme = dark ? "dark" : "paper";
  themeToggle.setAttribute("aria-pressed", String(dark));
}
try { setTheme(localStorage.getItem("music-analysis-theme") === "dark"); }
catch { setTheme(false); }
themeToggle.addEventListener("click", () => {
  const dark = document.documentElement.dataset.theme !== "dark";
  setTheme(dark);
  try { localStorage.setItem("music-analysis-theme", dark ? "dark" : "paper"); }
  catch { /* The selected theme stays active until the page is refreshed. */ }
});

revealOnScroll();
libraryView();
shelfView();
refresh().then(() => {
  if (location.hash) navigateTo(location.hash.slice(1));
}).catch(showError);
setInterval(() => {
  if (state.track && ["queued", "running"].includes(state.track.state) ||
      state.tracks.some(track => ["queued", "running"].includes(track.state)) ||
      state.collectionPending) refresh(true).catch(() => {});
}, 3200);

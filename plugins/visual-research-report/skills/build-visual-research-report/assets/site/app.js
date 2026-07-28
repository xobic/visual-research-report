(() => {
  "use strict";

  const report = window.REPORT_DATA;
  const app = document.getElementById("app");
  const drawer = document.getElementById("evidence-drawer");
  const drawerContent = document.getElementById("drawer-content");
  const drawerClose = document.getElementById("drawer-close");
  const drawerScrim = document.getElementById("drawer-scrim");
  const skipLink = document.querySelector(".skip-link");
  const noScript = document.querySelector("noscript");
  let returnFocus = null;
  let bodyOverflowBeforeDrawer = "";

  if (!report || !report.meta) {
    app.innerHTML = '<main class="report-shell"><h1>Report data could not be loaded / 报告数据无法加载</h1></main>';
    return;
  }

  const EN = {
    skip_to_report: "Skip to report",
    javascript_required: "Enable JavaScript to use charts and evidence drilldowns.",
    interactive_research: "Interactive research",
    as_of: "As of {date}",
    theme_atom: "Theme atom: {name}",
    schematic_fallback: "Schematic fallback",
    physical_system: "physical system",
    sources: "Sources",
    evidence_for_paragraph: "Evidence for paragraph",
    additional_units: "{count} additional {unit}",
    units: "units",
    flow_links: "Flow links",
    dimension: "Dimension",
    horizon: "Horizon",
    trigger: "Trigger",
    line_chart: "Line chart",
    analyst_note: "Analyst note",
    analyst_annotation: "Analyst annotation",
    decision_takeaways: "Decision takeaways",
    report_dashboard: "Report dashboard",
    key_numbers: "Key numbers",
    contents: "Contents",
    research_contract: "Research contract",
    contract_summary: "{facts} facts · {sources} sources · as of {date}",
    evidence_hint: "Every marked number opens its basis, date and sources.",
    methods_evidence: "Methods & evidence",
    how_to_read: "How to read this report",
    methodology: "Methodology",
    disclosures: "Disclosures",
    decision_framework: "Decision framework",
    source_register: "Source register",
    close: "Close",
    close_drawer: "Close evidence drawer",
    evidence: "Evidence",
    basis: "Basis",
    date: "Date",
    unit: "Unit",
    derived_from: "Derived from",
    formula: "Formula",
    comparison_basis: "Comparison basis",
    adjustment_scope: "Adjustment scope",
    boundary: "Boundary",
    precision: "Precision",
    source_type: "Source type",
    classification: "Classification",
    locator: "Locator",
    accessed: "Accessed",
    stack_total: "Total: {value}",
    negative_stack_note: "Negative values use a shared zero-axis comparison.",
    contained_table_hint: "Wide scorecard · scroll inside this region",
    long_forces: "Upside forces",
    short_forces: "Downside forces",
    tripwires: "Tripwires",
  };

  const ZH = {
    skip_to_report: "跳至报告正文",
    javascript_required: "请启用 JavaScript 以使用图表与证据钻取。",
    interactive_research: "交互研究报告",
    as_of: "截至 {date}",
    theme_atom: "主题原子：{name}",
    schematic_fallback: "示意图占位",
    physical_system: "物理系统",
    sources: "来源",
    evidence_for_paragraph: "本段证据",
    additional_units: "另有 {count} 个{unit}",
    units: "单位",
    flow_links: "流向关系",
    dimension: "维度",
    horizon: "期限",
    trigger: "触发条件",
    line_chart: "折线图",
    analyst_note: "分析师注释",
    analyst_annotation: "分析师判断",
    decision_takeaways: "决策要点",
    report_dashboard: "研究仪表盘",
    key_numbers: "关键数字",
    contents: "目录",
    research_contract: "研究口径",
    contract_summary: "{facts} 项事实 · {sources} 个来源 · 截至 {date}",
    evidence_hint: "点击任何标记数字可查看依据、日期和来源。",
    methods_evidence: "方法与证据",
    how_to_read: "如何阅读本报告",
    methodology: "研究方法",
    disclosures: "披露与限制",
    decision_framework: "决策框架",
    source_register: "来源登记",
    close: "关闭",
    close_drawer: "关闭证据抽屉",
    evidence: "证据",
    basis: "依据",
    date: "日期",
    unit: "单位",
    derived_from: "推导自",
    formula: "公式",
    comparison_basis: "比较口径",
    adjustment_scope: "调整范围",
    boundary: "边界",
    precision: "精度",
    source_type: "来源类型",
    classification: "来源级别",
    locator: "定位",
    accessed: "访问日期",
    stack_total: "合计：{value}",
    negative_stack_note: "负值采用共享零轴比较。",
    contained_table_hint: "宽表格 · 请在此区域内横向滚动",
    long_forces: "多头力量",
    short_forces: "空头力量",
    tripwires: "失效触发器",
  };

  const language = String(report.meta.language || "en-US");
  const labels = { ...(language.toLowerCase().startsWith("zh") ? ZH : EN), ...(report.ui_labels || {}) };
  const t = (key, values = {}) => Object.entries(values).reduce(
    (text, [name, value]) => text.replaceAll(`{${name}}`, () => String(value)),
    labels[key] ?? EN[key] ?? key,
  );

  document.documentElement.lang = language;
  document.documentElement.dataset.designPreset = report.presentation?.preset || "institutional-rail";
  document.title = report.meta.title || "Visual Research Report";
  skipLink.textContent = t("skip_to_report");
  noScript.textContent = t("javascript_required");
  drawerClose.textContent = `${t("close")} ×`;
  drawerClose.setAttribute("aria-label", t("close_drawer"));

  const facts = new Map((report.facts || []).map((fact) => [fact.id, fact]));
  const sources = new Map((report.sources || []).map((source) => [source.id, source]));
  const SERIES_COLORS = ["#1457ff", "#d53c36", "#18745b", "#d97706", "#7656c9", "#008f9c", "#c43f84", "#6f5b45"];

  const escapeHtml = (value) => String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");

  const safeUrl = (value) => {
    if (!value) return "";
    try {
      const url = new URL(value);
      return ["http:", "https:"].includes(url.protocol) ? escapeHtml(url.href) : "";
    } catch (_error) {
      return "";
    }
  };

  const displayValue = (item, fallback) => escapeHtml(item?.display ?? fallback ?? item?.value ?? "—");
  const sourceLinks = (ids = []) => ids.filter((id) => sources.has(id)).map((id) => `<a href="#source-${escapeHtml(id)}">[${escapeHtml(id)}]</a>`).join(" ");
  const factControl = (factId, label, className = "fact-chip") => {
    const fact = facts.get(factId);
    if (!fact) return "";
    return `<button class="${className}" type="button" data-fact-id="${escapeHtml(factId)}" data-kind="${escapeHtml(fact.kind)}">${escapeHtml(label ?? fact.display)}</button>`;
  };

  const renderCoverVisual = (view) => {
    const atom = report.theme_atom || {};
    if (view.asset) return `<img class="cover-image" src="${escapeHtml(view.asset)}" alt="${escapeHtml(view.alt)}">`;
    return `<div class="atom-schematic" role="img" aria-label="${escapeHtml(view.alt)}">
      <span class="schematic-tag">${escapeHtml(t("schematic_fallback"))}</span>
      <span class="atom-layer layer-b"></span><span class="atom-layer layer-a"></span><span class="atom-core"></span>
      <strong class="atom-name">${escapeHtml(atom.name)}</strong>
      <span class="atom-caption"><span>${escapeHtml(view.label)}</span><span>${escapeHtml(atom.material || t("physical_system"))}</span></span>
    </div>`;
  };

  const renderCover = () => {
    const meta = report.meta;
    const views = report.theme_atom?.views || [];
    const active = views[0] || { id: "recursive", label: "Recursive", alt: report.theme_atom?.name || "Theme atom" };
    return `<header class="masthead"><span class="masthead-mark">${escapeHtml(meta.publisher)}</span><span class="masthead-meta"><span>${escapeHtml(t("interactive_research"))}</span> · ${escapeHtml(meta.as_of)}</span></header>
      <section class="cover" aria-labelledby="report-title"><div class="cover-grid"><div class="cover-copy">
        <p class="kicker">${escapeHtml(meta.kicker)}</p><h1 class="cover-title" id="report-title">${escapeHtml(meta.title)}</h1>
        <p class="cover-subtitle">${escapeHtml(meta.subtitle)}</p><p class="cover-summary">${escapeHtml(meta.summary)}</p>
        <div class="cover-meta"><span>${escapeHtml(t("as_of", { date: meta.as_of }))}</span>${meta.reading_time ? `<span>${escapeHtml(meta.reading_time)}</span>` : ""}<span>${escapeHtml(t("theme_atom", { name: report.theme_atom?.name }))}</span></div>
      </div><div class="cover-media">
        <div class="cover-stage" id="cover-stage" role="tabpanel" aria-live="polite" aria-labelledby="cover-tab-${escapeHtml(active.id)}" data-cover-mode="${escapeHtml(active.id)}">${renderCoverVisual(active)}</div>
        <div class="cover-switcher" role="tablist" aria-label="${escapeHtml(t("theme_atom", { name: report.theme_atom?.name }))}">
          ${views.map((view, index) => `<button id="cover-tab-${escapeHtml(view.id)}" type="button" role="tab" aria-controls="cover-stage" data-cover-view="${escapeHtml(view.id)}" aria-selected="${index === 0 ? "true" : "false"}" tabindex="${index === 0 ? "0" : "-1"}">${escapeHtml(view.label)}</button>`).join("")}
        </div>
      </div></div></section>`;
  };

  const renderDataDisclosure = () => {
    const disclosure = report.data_disclosure;
    if (!disclosure || !(disclosure.placements || []).includes("top-banner")) return "";
    return `<aside class="data-disclosure" role="note"><strong>${escapeHtml(disclosure.label)}</strong><span>${escapeHtml(disclosure.scope)}</span></aside>`;
  };

  const renderBodyBlock = (block) => {
    const chips = (block.fact_ids || []).map((id) => factControl(id)).join("");
    if (block.type === "quote") return `<div class="quote-block"><blockquote>${escapeHtml(block.text)}</blockquote><p class="block-source">${escapeHtml(t("sources"))} ${sourceLinks(block.source_ids)}</p></div>`;
    if (block.type === "callout") return `<div class="callout-block"><h3>${escapeHtml(block.title)}</h3><p>${escapeHtml(block.text)}</p>${chips ? `<div>${chips}</div>` : ""}</div>`;
    return `<div class="prose"><p>${escapeHtml(block.text)}</p>${chips ? `<div aria-label="${escapeHtml(t("evidence_for_paragraph"))}">${chips}</div>` : ""}</div>`;
  };

  const renderEntityRamp = (data) => {
    const unitSize = Number(data.unit_size) > 0 ? Number(data.unit_size) : 1;
    return `<div class="entity-ramp">${(data.periods || []).map((period) => {
      const rawCount = Math.max(0, Math.round(Number(period.value) / unitSize));
      const count = Math.min(rawCount, 28);
      return `<button class="entity-period" type="button" data-fact-id="${escapeHtml(period.fact_id)}"><span class="entity-value">${displayValue(period, period.value)}</span><span class="entity-label">${escapeHtml(period.label)}</span><span class="entity-units" aria-hidden="true">${Array.from({ length: count }, () => '<i class="entity-unit"></i>').join("")}</span>${rawCount > count ? `<span class="entity-overflow">${escapeHtml(t("additional_units", { count: rawCount - count, unit: data.entity_label || t("units") }))}</span>` : ""}</button>`;
    }).join("")}</div>`;
  };

  const renderFlow = (data) => {
    const stageNames = [...new Set((data.nodes || []).map((node) => node.stage))];
    const nodeLookup = new Map((data.nodes || []).map((node) => [node.id, node]));
    const stages = stageNames.map((stage) => `<div class="flow-stage"><p class="flow-stage-label">${escapeHtml(stage)}</p>${(data.nodes || []).filter((node) => node.stage === stage).map((node) => {
      const tag = node.fact_id ? "button" : "div";
      const attrs = node.fact_id ? `type="button" data-fact-id="${escapeHtml(node.fact_id)}"` : "";
      return `<${tag} class="flow-node" ${attrs}><strong>${escapeHtml(node.label)}</strong>${node.value != null && node.fact_id ? `<small>${displayValue(node, node.value)}</small>` : ""}</${tag}>`;
    }).join("")}</div>`).join("");
    const links = (data.links || []).map((link) => {
      const route = `${nodeLookup.get(link.source)?.label || link.source} → ${nodeLookup.get(link.target)?.label || link.target}`;
      const content = link.fact_id ? `${route}: ${link.display ?? link.value}` : route;
      return link.fact_id ? `<button class="flow-link" type="button" data-fact-id="${escapeHtml(link.fact_id)}">${escapeHtml(content)}</button>` : `<span class="flow-link">${escapeHtml(content)}</span>`;
    }).join("");
    return `<div class="flow-grid">${stages}</div><div class="flow-links" aria-label="${escapeHtml(t("flow_links"))}">${links}</div>`;
  };

  const renderTimeline = (data) => `<div class="timeline">${(data.events || []).map((event) => `<article class="timeline-event"><time class="timeline-date">${escapeHtml(event.date)}</time><div class="timeline-card"><h4 class="timeline-title">${escapeHtml(event.title)}</h4><p class="timeline-description">${escapeHtml(event.description)}</p>${event.fact_id ? factControl(event.fact_id) : ""}${event.source_ids?.length ? `<p class="block-source">${sourceLinks(event.source_ids)}</p>` : ""}</div></article>`).join("")}</div>`;

  const renderMatrix = (data) => {
    const values = (data.rows || []).flatMap((row) => row.values || []).map((cell) => Number(cell.value)).filter(Number.isFinite);
    const domain = data.scale?.domain;
    const min = Array.isArray(domain) && Number.isFinite(Number(domain[0])) ? Number(domain[0]) : Math.min(...values, 0);
    const max = Array.isArray(domain) && Number.isFinite(Number(domain[1])) ? Number(domain[1]) : Math.max(...values, 1);
    const span = max - min || 1;
    const cell = (entry, rowLabel, columnLabel) => {
      const ratio = Math.max(0, Math.min(1, (Number(entry.value) - min) / span));
      const foreground = ratio > 0.7 ? "#ffffff" : "#151922";
      const aria = `${rowLabel}, ${columnLabel}, ${entry.display ?? entry.value}`;
      return `<td style="background:rgba(20,87,255,${(0.08 + ratio * 0.5).toFixed(3)});color:${foreground}"><button class="heat-cell" type="button" data-fact-id="${escapeHtml(entry.fact_id)}" aria-label="${escapeHtml(aria)}">${displayValue(entry, entry.value)}</button></td>`;
    };
    return `<p class="contained-overflow-hint">${escapeHtml(t("contained_table_hint"))}</p><div class="matrix-wrap" data-contained-overflow="true" role="region" aria-label="${escapeHtml(t("contained_table_hint"))}" tabindex="0"><table class="matrix"><thead><tr><th>${escapeHtml(t("dimension"))}</th>${(data.columns || []).map((column) => `<th>${escapeHtml(column)}</th>`).join("")}</tr></thead><tbody>${(data.rows || []).map((row) => `<tr><th class="matrix-row-label">${escapeHtml(row.label)}</th>${(row.values || []).map((entry, index) => cell(entry, row.label, data.columns?.[index] ?? index + 1)).join("")}</tr>`).join("")}</tbody></table></div>`;
  };

  const renderStack = (data) => {
    const layers = data.layers || [];
    const values = layers.map((layer) => Number(layer.value));
    if (values.some((value) => value < 0)) {
      const extent = Math.max(...values.map(Math.abs), 1);
      return `<div class="diverging-stack" data-stack-mode="diverging"><p class="stack-mode-note">${escapeHtml(t("negative_stack_note"))}</p>${layers.map((layer) => {
        const value = Number(layer.value);
        const width = Math.abs(value) / extent * 50;
        const left = value < 0 ? 50 - width : 50;
        return `<button class="diverging-row" type="button" data-fact-id="${escapeHtml(layer.fact_id)}"><span class="stack-label"><strong>${escapeHtml(layer.label)}</strong><small>${escapeHtml(layer.description || "")}</small></span><span class="diverging-track"><i class="zero-axis"></i><i class="diverging-measure ${value < 0 ? "is-negative" : "is-positive"}" style="left:${left.toFixed(3)}%;width:${width.toFixed(3)}%"></i></span><span class="stack-value">${displayValue(layer, layer.value)}</span></button>`;
      }).join("")}</div>`;
    }
    const total = values.reduce((sum, value) => sum + Math.max(0, value), 0) || 1;
    const encoding = data.encoding || "absolute";
    const segments = layers.map((layer, index) => {
      const share = Math.max(0, Number(layer.value)) / total * 100;
      return `<span class="stack-segment" data-stack-value="${escapeHtml(layer.value)}" data-stack-share="${share.toFixed(6)}" style="width:${share.toFixed(6)}%;background:${SERIES_COLORS[index % SERIES_COLORS.length]}" title="${escapeHtml(layer.label)}"></span>`;
    }).join("");
    const legend = layers.map((layer, index) => `<button class="stack-layer" type="button" data-fact-id="${escapeHtml(layer.fact_id)}"><i style="background:${SERIES_COLORS[index % SERIES_COLORS.length]}"></i><span><strong>${escapeHtml(layer.label)}</strong>${layer.description ? `<small>${escapeHtml(layer.description)}</small>` : ""}</span><span class="stack-value">${displayValue(layer, layer.value)}</span></button>`).join("");
    return `<div class="value-stack" data-stack-mode="${escapeHtml(encoding)}"><div class="stack-ribbon" aria-hidden="true">${segments}</div><div class="stack-legend">${legend}</div>${data.total_display ? `<p class="stack-total">${escapeHtml(t("stack_total", { value: data.total_display }))}</p>` : ""}</div>`;
  };

  const renderOdds = (data) => `<div class="odds-grid">${(data.items || []).map((item) => {
    const probability = Math.max(0, Math.min(1, Number(item.probability)));
    return `<button class="odds-card" type="button" data-fact-id="${escapeHtml(item.fact_id)}"><span class="odds-value">${Math.round(probability * 100)}%</span><strong class="odds-label">${escapeHtml(item.label)}</strong><span class="odds-track"><i class="odds-fill" style="width:${(probability * 100).toFixed(2)}%"></i></span><span class="odds-meta">${item.horizon ? `${escapeHtml(t("horizon"))}: ${escapeHtml(item.horizon)}<br>` : ""}${item.trigger ? `${escapeHtml(t("trigger"))}: ${escapeHtml(item.trigger)}` : ""}</span></button>`;
  }).join("")}</div>`;

  const distributeLabels = (labels, minY, maxY, gap = 14) => {
    const groups = new Map();
    labels.forEach((label) => {
      const key = Math.round(label.x / 36);
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(label);
    });
    groups.forEach((group) => {
      group.sort((a, b) => a.y - b.y);
      group.forEach((label, index) => { label.labelY = Math.max(minY, index ? group[index - 1].labelY + gap : label.y); });
      const overflow = group[group.length - 1].labelY - maxY;
      if (overflow > 0) group.forEach((label) => { label.labelY -= overflow; });
      for (let index = group.length - 2; index >= 0; index -= 1) group[index].labelY = Math.min(group[index].labelY, group[index + 1].labelY - gap);
    });
    return labels;
  };

  const renderLine = (data) => {
    const width = 900;
    const height = 340;
    const pad = { left: 58, right: 150, top: 30, bottom: 48 };
    const allPoints = (data.series || []).flatMap((series) => series.points || []);
    const ys = allPoints.map((point) => Number(point.y)).filter(Number.isFinite);
    const domain = data.scale?.domain;
    const minY = Array.isArray(domain) && Number.isFinite(Number(domain[0])) ? Number(domain[0]) : Math.min(...ys);
    const maxY = Array.isArray(domain) && Number.isFinite(Number(domain[1])) ? Number(domain[1]) : Math.max(...ys);
    const ySpan = maxY - minY || 1;
    const xLabels = [...new Set(allPoints.map((point) => String(point.x)))];
    const xAt = (x) => pad.left + (xLabels.indexOf(String(x)) / Math.max(1, xLabels.length - 1)) * (width - pad.left - pad.right);
    const yAt = (y) => pad.top + (1 - (Number(y) - minY) / ySpan) * (height - pad.top - pad.bottom);
    const ticks = Array.isArray(data.scale?.ticks) && data.scale.ticks.length > 1
      ? data.scale.ticks.map(Number)
      : Array.from({ length: 5 }, (_, index) => minY + (index / 4) * ySpan);
    const horizontal = [...ticks].reverse().map((label) => {
      const y = yAt(label);
      return `<line class="line-grid" x1="${pad.left}" y1="${y}" x2="${width - pad.right}" y2="${y}"></line><text class="line-axis-label" x="${pad.left - 8}" y="${y + 4}" text-anchor="end">${escapeHtml(label.toFixed(label % 1 ? 1 : 0))}</text>`;
    }).join("");
    const xAxis = xLabels.map((label) => `<text class="line-axis-label" x="${xAt(label)}" y="${height - 17}" text-anchor="middle">${escapeHtml(label)}</text>`).join("");
    const labelsToPlace = [];
    (data.series || []).forEach((series, seriesIndex) => {
      const points = series.points || [];
      const candidates = new Set([points.length - 1]);
      if (points.length > 2) {
        const numbers = points.map((point) => Number(point.y));
        candidates.add(numbers.indexOf(Math.max(...numbers)));
        candidates.add(numbers.indexOf(Math.min(...numbers)));
      }
      candidates.forEach((pointIndex) => {
        if (pointIndex < 0) return;
        const point = points[pointIndex];
        const isEnd = pointIndex === points.length - 1;
        if (isEnd) labelsToPlace.push({ x: xAt(point.x) + 9, y: yAt(point.y), text: series.name, color: series.color || SERIES_COLORS[seriesIndex % SERIES_COLORS.length], seriesIndex, anchor: "start", kind: "end" });
      });
    });
    distributeLabels(labelsToPlace, pad.top + 6, height - pad.bottom - 6);
    const seriesSvg = (data.series || []).map((series, seriesIndex) => {
      const color = series.color || SERIES_COLORS[seriesIndex % SERIES_COLORS.length];
      const points = series.points || [];
      const polyline = points.map((point) => `${xAt(point.x)},${yAt(point.y)}`).join(" ");
      const marks = points.map((point) => `<g class="line-mark" role="button" tabindex="0" data-fact-id="${escapeHtml(point.fact_id)}" aria-label="${escapeHtml(`${series.name}, ${point.x}, ${point.display ?? point.y}`)}"><circle class="line-hit" cx="${xAt(point.x)}" cy="${yAt(point.y)}" r="28"></circle><circle class="line-point" aria-hidden="true" style="--series-color:${escapeHtml(color)}" cx="${xAt(point.x)}" cy="${yAt(point.y)}" r="6"></circle></g>`).join("");
      return `<polyline class="line-path" data-series-index="${seriesIndex}" style="--series-color:${escapeHtml(color)}" points="${polyline}"></polyline>${marks}`;
    }).join("");
    const labelSvg = labelsToPlace.map((label) => `<text class="line-${label.kind}-label" x="${label.x}" y="${label.labelY}" text-anchor="${label.anchor}" fill="${escapeHtml(label.color)}">${escapeHtml(label.text)}</text>`).join("");
    const legend = (data.series || []).map((series, index) => { const color = series.color || SERIES_COLORS[index % SERIES_COLORS.length]; return `<span><i class="legend-mark" style="background:${escapeHtml(color)}"></i>${escapeHtml(series.name)}</span>`; }).join("");
    return `<div class="line-wrap" data-scroll-latest="true" role="region" aria-label="${escapeHtml(t("line_chart"))}" tabindex="0"><svg class="line-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeHtml(t("line_chart"))}">${horizontal}${seriesSvg}${labelSvg}${xAxis}</svg></div><div class="line-legend">${legend}</div>`;
  };

  const renderPairs = (data) => {
    const chartScale = data.scale || {};
    const renderPair = (item) => {
      const values = [Number(item.left?.value), Number(item.right?.value)].filter(Number.isFinite);
      const scale = chartScale.mode === "per-pair-actual" ? item.scale || {} : chartScale;
      const domain = Array.isArray(scale.domain) ? scale.domain.map(Number) : [Math.min(0, ...values), Math.max(1, ...values)];
      const span = domain[1] - domain[0] || 1;
      const widthFor = (value) => Math.max(0, Math.min(100, (Number(value) - domain[0]) / span * 100));
      const row = (member) => `<button class="pair-control" type="button" data-fact-id="${escapeHtml(member.fact_id)}"><span class="pair-name">${escapeHtml(member.label)}</span><span class="bar-track"><i class="bar-fill" style="width:${widthFor(member.value).toFixed(2)}%"></i></span><span class="pair-value">${displayValue(member, member.value)}</span></button>`;
      const ticks = (scale.ticks || []).map((tick) => `<span style="left:${widthFor(tick).toFixed(2)}%">${escapeHtml(tick)}</span>`).join("");
      const multiplier = item.multiplier_fact_id ? factControl(item.multiplier_fact_id, undefined, "pair-multiplier") : "";
      return `<div class="pair"><div class="pair-heading"><div class="pair-label">${escapeHtml(item.label)}</div>${multiplier}</div>${row(item.left)}${row(item.right)}<div class="pair-axis" aria-hidden="true">${ticks}</div></div>`;
    };
    return `<div class="pairs">${(data.items || []).map(renderPair).join("")}</div>`;
  };

  const renderTensionBalance = (data) => {
    const domain = data.scale?.domain || [0, 5];
    const span = Number(domain[1]) - Number(domain[0]) || 1;
    const item = (entry, side) => {
      const fact = facts.get(entry.fact_id);
      const value = Number(fact?.value);
      const strength = Math.max(0, Math.min(1, (value - Number(domain[0])) / span));
      return `<button class="balance-weight is-${side}" type="button" data-fact-id="${escapeHtml(entry.fact_id)}" style="--strength:${strength.toFixed(3)}"><span>${escapeHtml(entry.label)}</span><strong>${escapeHtml(fact?.display || "—")}</strong></button>`;
    };
    const side = (name, entries, sideName) => `<div class="balance-side is-${sideName}"><h4>${escapeHtml(name)}</h4>${(entries || []).map((entry) => item(entry, sideName)).join("")}</div>`;
    const tripwires = (data.tripwires || []).map((entry) => {
      const fact = facts.get(entry.fact_id);
      return `<button class="tripwire" type="button" data-fact-id="${escapeHtml(entry.fact_id)}"><span>${escapeHtml(entry.label)}</span><strong>${escapeHtml(fact?.display || "—")}</strong></button>`;
    }).join("");
    return `<div class="tension-balance"><div class="balance-beam" aria-hidden="true"><i></i></div><div class="balance-grid">${side(t("long_forces"), data.long, "long")}<div class="balance-center"><span>${escapeHtml(data.center_label)}</span></div>${side(t("short_forces"), data.short, "short")}</div><div class="tripwire-zone"><h4>${escapeHtml(t("tripwires"))}</h4>${tripwires}</div></div>`;
  };

  const chartRenderers = { "entity-ramp": renderEntityRamp, "destiny-flow": renderFlow, timeline: renderTimeline, "matrix-heat": renderMatrix, "value-stack": renderStack, "odds-board": renderOdds, line: renderLine, "paired-bars": renderPairs, "tension-balance": renderTensionBalance };
  const renderChart = (chart) => `<figure class="chart-plate" id="chart-${escapeHtml(chart.id)}" data-chart-type="${escapeHtml(chart.type)}"><figcaption><p class="figure-kicker">${escapeHtml(chart.id)} / ${escapeHtml(chart.type)}</p><h3 class="chart-title">${escapeHtml(chart.title)}</h3><p class="chart-subtitle">${escapeHtml(chart.subtitle)}</p></figcaption><div class="chart-plot">${chartRenderers[chart.type]?.(chart.data || {}) || ""}</div>${chart.note ? `<p class="chart-note"><strong>${escapeHtml(t("analyst_note"))}:</strong> ${escapeHtml(chart.note)}</p>` : ""}<p class="chart-source">${escapeHtml(t("sources"))} ${sourceLinks(chart.source_ids)}</p></figure>`;
  const renderSection = (section) => `<section class="report-section" id="${escapeHtml(section.id)}"><header class="section-head"><p class="section-eyebrow">${escapeHtml(section.eyebrow)}</p><h2 class="section-title">${escapeHtml(section.title)}</h2><p class="section-dek">${escapeHtml(section.dek)}</p></header>${(section.body || []).map(renderBodyBlock).join("")}${(section.charts || []).map(renderChart).join("")}${section.annotation ? `<aside class="annotation"><strong>${escapeHtml(t("analyst_annotation"))}</strong><p>${escapeHtml(section.annotation)}</p></aside>` : ""}${section.takeaways?.length ? `<div class="takeaways"><h3>${escapeHtml(t("decision_takeaways"))}</h3><ul>${section.takeaways.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul></div>` : ""}</section>`;

  const renderRail = () => `<aside class="research-rail" aria-label="${escapeHtml(t("report_dashboard"))}"><div class="rail-block"><p class="rail-label">${escapeHtml(t("key_numbers"))}</p><div class="rail-kpis">${(report.kpis || []).map((id) => { const fact = facts.get(id); return fact ? `<button class="kpi" type="button" data-fact-id="${escapeHtml(id)}"><span class="kpi-value">${escapeHtml(fact.display)}</span><span class="kpi-label">${escapeHtml(fact.label)}</span><span class="kpi-date">${escapeHtml(fact.date)}</span></button>` : ""; }).join("")}</div></div><div class="rail-block"><p class="rail-label">${escapeHtml(t("contents"))}</p><nav class="rail-nav">${(report.sections || []).map((section) => `<a href="#${escapeHtml(section.id)}" data-section-link="${escapeHtml(section.id)}">${escapeHtml(section.eyebrow)} · ${escapeHtml(section.title)}</a>`).join("")}</nav></div><div class="rail-block rail-meta"><p class="rail-label">${escapeHtml(t("research_contract"))}</p><p>${escapeHtml(t("contract_summary", { facts: report.facts?.length || 0, sources: report.sources?.length || 0, date: report.meta.as_of }))}</p><p>${escapeHtml(t("evidence_hint"))}</p></div></aside>`;

  const sourceLocator = (source) => source.locator && typeof source.locator === "object" ? Object.entries(source.locator).filter(([, value]) => value).map(([key, value]) => `${key}: ${value}`).join(" · ") : "";
  const renderSource = (source) => {
    const url = safeUrl(source.url);
    const title = url ? `<a href="${url}" target="_blank" rel="noreferrer">${escapeHtml(source.title)}</a>` : escapeHtml(source.title);
    const details = [source.publisher, source.date, source.source_type, source.classification, source.accessed_at ? `${t("accessed")}: ${source.accessed_at}` : "", sourceLocator(source)].filter(Boolean).join(" · ");
    return `<article class="source-item" id="source-${escapeHtml(source.id)}"><span class="source-id">${escapeHtml(source.id)}</span><p class="source-title">${title}</p><p class="source-meta">${escapeHtml(details)}</p>${source.note ? `<p class="source-note">${escapeHtml(source.note)}</p>` : ""}</article>`;
  };

  const renderPresetChecks = () => {
    if (!report.preset_checks || typeof report.preset_checks !== "object") return "";
    return `<h3>${escapeHtml(t("decision_framework"))}</h3><dl class="preset-checks">${Object.entries(report.preset_checks).map(([key, value]) => `<dt>${escapeHtml(key.replaceAll("_", " "))}</dt><dd>${escapeHtml(Array.isArray(value) ? value.join("; ") : value)}</dd>`).join("")}</dl>`;
  };
  const renderBackmatter = () => `<section class="backmatter" id="sources"><p class="section-eyebrow">${escapeHtml(t("methods_evidence"))}</p><h2>${escapeHtml(t("how_to_read"))}</h2>${renderPresetChecks()}<h3>${escapeHtml(t("methodology"))}</h3><ul class="method-list">${(report.methodology || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul><h3>${escapeHtml(t("disclosures"))}</h3><ul class="disclosure-list">${(report.disclosures || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul><div class="source-register" aria-label="${escapeHtml(t("source_register"))}">${(report.sources || []).map(renderSource).join("")}</div></section>`;

  app.innerHTML = `${renderDataDisclosure()}${renderCover()}<div class="report-shell" id="report-content"><div class="report-layout">${renderRail()}<main class="article-flow">${(report.sections || []).map(renderSection).join("")}${renderBackmatter()}</main></div></div>`;

  const setCover = (viewId, focus = false) => {
    const view = report.theme_atom.views.find((item) => item.id === viewId);
    if (!view) return;
    const stage = document.getElementById("cover-stage");
    stage.dataset.coverMode = view.id;
    stage.innerHTML = renderCoverVisual(view);
    document.querySelectorAll("[data-cover-view]").forEach((button) => {
      const selected = button.dataset.coverView === view.id;
      button.setAttribute("aria-selected", String(selected));
      button.tabIndex = selected ? 0 : -1;
      if (selected) stage.setAttribute("aria-labelledby", button.id);
      if (selected && focus) button.focus();
    });
  };

  const setAppInert = (inert) => {
    app.inert = inert;
    if (inert) app.setAttribute("aria-hidden", "true");
    else app.removeAttribute("aria-hidden");
  };
  const drawerFocusable = () => [...drawer.querySelectorAll('button:not([disabled]), a[href], [tabindex]:not([tabindex="-1"])')].filter((element) => !element.hidden);
  const openDrawer = (factId, trigger) => {
    const fact = facts.get(factId);
    if (!fact) return;
    returnFocus = trigger || document.activeElement;
    const sourceItems = (fact.source_ids || []).map((id) => sources.get(id)).filter(Boolean);
    const derived = (fact.derived_from || []).map((id) => facts.get(id)).filter(Boolean);
    const semanticRows = [["formula", fact.formula], ["comparison_basis", fact.comparison_basis], ["adjustment_scope", fact.adjustment_scope], ["boundary", fact.boundary], ["precision", fact.precision]];
    drawerContent.innerHTML = `<p class="drawer-kicker">${escapeHtml(t("evidence"))} / ${escapeHtml(fact.id)}</p><h2 class="drawer-title" id="drawer-title">${escapeHtml(fact.label)}</h2><p class="drawer-value">${escapeHtml(fact.display)}</p><span class="drawer-kind">${escapeHtml(fact.kind)}</span><dl class="drawer-grid"><dt>${escapeHtml(t("basis"))}</dt><dd>${escapeHtml(fact.basis)}</dd><dt>${escapeHtml(t("date"))}</dt><dd>${escapeHtml(fact.date)}</dd><dt>${escapeHtml(t("unit"))}</dt><dd>${escapeHtml(fact.unit || "—")}</dd>${derived.length ? `<dt>${escapeHtml(t("derived_from"))}</dt><dd>${derived.map((item) => `${escapeHtml(item.id)} · ${escapeHtml(item.display)}`).join("<br>")}</dd>` : ""}${semanticRows.filter(([, value]) => value).map(([key, value]) => `<dt>${escapeHtml(t(key))}</dt><dd>${escapeHtml(value)}</dd>`).join("")}</dl><div class="drawer-sources"><h3>${escapeHtml(t("sources"))}</h3>${sourceItems.map((source) => `<a href="#source-${escapeHtml(source.id)}" data-close-drawer>${escapeHtml(source.id)} · ${escapeHtml(source.title)} (${escapeHtml(source.date)})</a>`).join("")}</div>`;
    drawer.hidden = false;
    drawerScrim.hidden = false;
    setAppInert(true);
    bodyOverflowBeforeDrawer = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    drawerClose.focus();
  };
  const closeDrawer = () => {
    drawer.hidden = true;
    drawerScrim.hidden = true;
    setAppInert(false);
    document.body.style.overflow = bodyOverflowBeforeDrawer;
    if (returnFocus && typeof returnFocus.focus === "function") returnFocus.focus();
  };

  document.addEventListener("click", (event) => {
    const factTarget = event.target.closest("[data-fact-id]");
    if (factTarget) { event.preventDefault(); openDrawer(factTarget.dataset.factId, factTarget); return; }
    const coverButton = event.target.closest("[data-cover-view]");
    if (coverButton) { setCover(coverButton.dataset.coverView); return; }
    if (event.target.closest("[data-close-drawer]")) closeDrawer();
  });

  document.addEventListener("keydown", (event) => {
    const coverButton = event.target.closest?.("[data-cover-view]");
    if (coverButton && ["ArrowRight", "ArrowLeft", "ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) {
      event.preventDefault();
      const tabs = [...document.querySelectorAll("[data-cover-view]")];
      const index = tabs.indexOf(coverButton);
      const next = event.key === "Home" ? 0 : event.key === "End" ? tabs.length - 1 : (index + (["ArrowRight", "ArrowDown"].includes(event.key) ? 1 : -1) + tabs.length) % tabs.length;
      setCover(tabs[next].dataset.coverView, true);
      return;
    }
    const factTarget = event.target.closest?.("[data-fact-id]");
    if (factTarget && (event.key === "Enter" || event.key === " ")) { event.preventDefault(); openDrawer(factTarget.dataset.factId, factTarget); return; }
    if (!drawer.hidden && event.key === "Tab") {
      const focusable = drawerFocusable();
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    }
    if (event.key === "Escape" && !drawer.hidden) { event.preventDefault(); closeDrawer(); }
  });

  drawerClose.addEventListener("click", closeDrawer);
  drawerScrim.addEventListener("click", closeDrawer);

  const positionLineScroll = () => {
    if (!matchMedia("(max-width: 759px)").matches) return;
    document.querySelectorAll('[data-scroll-latest="true"]').forEach((wrap) => { wrap.scrollLeft = wrap.scrollWidth - wrap.clientWidth; });
  };
  requestAnimationFrame(positionLineScroll);
  window.addEventListener("resize", () => requestAnimationFrame(positionLineScroll), { passive: true });

  if ("IntersectionObserver" in window) {
    const links = new Map([...document.querySelectorAll("[data-section-link]")].map((link) => [link.dataset.sectionLink, link]));
    const observer = new IntersectionObserver((entries) => entries.filter((entry) => entry.isIntersecting).forEach((entry) => links.forEach((link) => link.classList.toggle("is-active", link.dataset.sectionLink === entry.target.id))), { rootMargin: "-20% 0px -65%", threshold: 0 });
    document.querySelectorAll(".report-section").forEach((section) => observer.observe(section));
  }
})();

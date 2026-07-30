# Visual Research Report

把深度报告编译成可追溯、可钻取、可离线交付的机构级研究网站。

它不是先挑图表或套网页模板，而是先建立事实与来源的数据合同，再围绕同一个“主题原子”组织封面、正文、图表和证据抽屉，最终输出多文件网站、单文件 HTML 和可选 PDF。

![Visual Research Report preview](docs/report-preview.png)

### 章节同步研究仪表盘

`editorial-dashboard` 把长报告组织成“顶部章节轨道 + 左侧结论与证据 + 右侧章节同步仪表盘”。桌面端右栏随阅读位置更新主数字、真实趋势、2×2 指标和概率路径；平板与手机自动收起右栏并保留可横向浏览的章节轨。章节首屏会在标题和一段论证后立即进入第一张证据图，避免只看到大标题和空白。

### Image 2 主题原子四态

默认封面生产路径先用 Image 2 建立一个可核验的主体锚点，再从同一锚点直接编辑出递归、爆炸图、工程蓝图与开箱冲击四态。构建器会校验主体/机位锁、输入输出哈希、画布一致性与文件预算；工程 SVG 仅作为显式降级方案。

![Image 2 four-state theme atom](plugins/visual-research-report/skills/build-visual-research-report/assets/theme-atom-image2/contact-sheet.png)

## 安装

先把本仓库添加为 Codex Git marketplace：

```bash
codex plugin marketplace add xobic/visual-research-report
codex plugin add visual-research-report@visual-research-report
```

安装后新建一个 Codex 任务，并使用 `@visual-research-report`，或直接描述“把这份深度报告做成可追溯的交互研究网站”。

`image-2` 与 `provided` 封面模式需要 Python 运行时包含 Pillow，用于真实解码、校验和压缩图片；缺失时构建会明确失败，可通过 `python3 -m pip install Pillow` 补齐。Node.js 用于 JavaScript 语法检查，Chromium/Chrome 仅在浏览器 QA 与 PDF 导出时需要。

## 核心能力

- `visual-research-report@2` 数据合同：事实、来源、日期、定位信息、证据状态和结构化披露。
- Image 2 主题原子四视图：以 `gpt-image-2` 生成 canonical identity anchor，再用四次直接编辑得到递归、爆炸图、工程蓝图与开箱冲击视图；每态保留生成来源、身份不变量与 SHA-256 连续性。
- 严格素材打包：PNG 母版校验后转为 WebP 交付，检查真实图像解码、路径 containment、尺寸/焦点、四态唯一性、总资源预算与单文件 data URI；工程 SVG 仅作为显式降级方案。
- 四套版式预设：平面 `editorial-longform`、只带 sticky 章节轨的 `editorial-scrollspy`、章节与证据右栏联动的 `editorial-dashboard`，以及传统信息轨 `institutional-rail`。
- 章节仪表盘只引用事实 ID：一个主读数、同单位趋势、2–4 个指标和 1–3 个概率路径；所有可见数字继续钻取到同一证据抽屉。
- 按数据形状路由图表：实体单位、流向图、时间墙、热力矩阵、价值栈、赔率板、张力天平、滚动历史、因果地平线，以及必要时的精确线图/柱图。
- `history-scrolly` 支持按制度阶段或产业周期切换焦点窗口，并提供 reduced-motion 与打印静态降级。
- `causal-horizon-map` 将方向、置信度、滞后、阈值、sparkline 与证据事实绑定到同一张图。
- 每个关键数字可打开证据卡片，回溯数值、依据、日期、来源和定位信息。
- Figma 是可选增强；不可用时使用本地 HTML、CSS、SVG 和浏览器导出完成交付。
- QA 覆盖离线依赖、JavaScript 语法、响应式布局、交互、控制台错误、PDF 与文件哈希清单。

## 输入合同

建议提供：

1. 报告正文或研究材料。
2. 可复用的结构化数据表。
3. 每个关键数字的来源、日期和页码/表格/段落定位。
4. 一个具体、可拆解、可辨识的行业“主题原子”。
5. 可选的参考页面、设计图或截图。

缺少真实数据时可以生成设计演示，但必须把相关事实标记为 `synthetic`，并在页面、方法论和交付清单中同时披露。

## 交付物

- `site/index.html`：多文件网站。
- `report.html`：可通过 `file://` 直接打开的单文件版本。
- `report.json`：规范化数据合同。
- `report.pdf`：可选的 A4 PDF。
- `build-manifest.json`：交付状态、文件大小和 SHA-256 哈希。
- `qa-results.json`：浏览器 QA 结果与截图索引。

## 本地验证

```bash
SKILL=plugins/visual-research-report/skills/build-visual-research-report

python3 "$SKILL/scripts/validate_report.py" \
  "$SKILL/assets/report.example.json" --strict

python3 "$SKILL/scripts/build_report.py" \
  "$SKILL/assets/report.example.json" --output /tmp/visual-report

python3 "$SKILL/scripts/qa_report.py" /tmp/visual-report
python3 "$SKILL/scripts/finalize_package.py" /tmp/visual-report
python3 "$SKILL/scripts/qa_report.py" /tmp/visual-report --require-final
```

## 仓库结构

```text
.agents/plugins/marketplace.json
plugins/visual-research-report/
  .codex-plugin/plugin.json
  skills/build-visual-research-report/
```

## License

MIT

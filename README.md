# Visual Research Report

把深度报告编译成可追溯、可钻取、可离线交付的机构级研究网站。

它不是先挑图表或套网页模板，而是先建立事实与来源的数据合同，再围绕同一个“主题原子”组织封面、正文、图表和证据抽屉，最终输出多文件网站、单文件 HTML 和可选 PDF。

![Visual Research Report preview](docs/report-preview.png)

## 安装

先把本仓库添加为 Codex Git marketplace：

```bash
codex plugin marketplace add xobic/visual-research-report
codex plugin add visual-research-report@visual-research-report
```

安装后新建一个 Codex 任务，并使用 `@visual-research-report`，或直接描述“把这份深度报告做成可追溯的交互研究网站”。

## 核心能力

- `visual-research-report@2` 数据合同：事实、来源、日期、定位信息、证据状态和结构化披露。
- 主题原子四视图：递归、爆炸图、工程蓝图与开箱冲击视图围绕同一行业对象展开。
- 两套版式预设：参考图驱动的 `editorial-longform` 与带信息轨的 `institutional-rail`。
- 按数据形状路由图表：实体单位、流向图、时间墙、热力矩阵、价值栈、赔率板、张力天平，以及必要时的精确线图/柱图。
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

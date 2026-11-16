# research-report

> **English: [README.md](README.md)** · 以下是中文

把一个**问题**变成一份可核查的报告，而不是一堆网页。

它会拆子查询、收集 URL、调用抓取引擎、**先核对哪些页真的读到了**、逐条摘录原文引用、用 `grep` 回查每一句、最后把读不到的部分列出来。

**它自己没有任何抓取代码。** 读页面这件事交给 [`accessing-blocked-sites`](https://github.com/AleHeinesen/accessing-blocked-sites)——它负责按站点选出口、过 Cloudflare、给出诚实的失败判定。**安装本技能会默认连引擎一起装。**

```
问题 → 子查询 → urls.txt → 引擎 → index.md（覆盖率）
     → corpus.md（证据） → 缺口补抓 → report.md
```

## 为什么拆成两层

调研答案的失败方式有三种，看起来很像是同一种：读得太少、把没读到的页当成读到了、说出没有出处的话。引擎解决第一种的**机械问题**，本技能解决**判断问题**：

| 层 | 归属 | 职责 |
|---|---|---|
| 执行 | `accessing-blocked-sites` | 拿到字节，或准确说明为什么拿不到 |
| 决策 | `research-report` | 读哪些、是否真读到了、这些能证明什么 |

依赖是单向的：引擎从不调用本技能，单独使用完全正常。

## 安装

需要 Python 3.10+ 和本机已装的 Chrome / Edge / Chromium。

```bash
git clone https://github.com/AleHeinesen/research-report && cd research-report
python install.py
```

会**同时**装上两个技能，并为引擎建好 Playwright 环境。引擎按以下顺序寻找：

1. `--engine-src <路径>` —— 本地引擎仓库
2. `../accessing-blocked-sites` —— 开发时的同级目录
3. 目标技能目录里已存在的引擎
4. `git clone` 指定 `--engine-url` 与 `--engine-ref`

```bash
python install.py --engine-src ~/src/accessing-blocked-sites
python install.py --no-engine     # 只装调研层，引擎需已存在
python install.py --no-venv --dry-run
```

安装器说明：已存在、但不是它装的目录不会被动过，除非加 `--force`。**任务运行时不下载任何东西**——后来引擎丢了，技能会停下并说明，而不是自己偷偷装。

装完重启 Agent。

## 用法

直接要一个需要多源回答的问题即可。触发场景：对比、尽调、综述、「读几篇告诉到底怎么回事」。

流程：

1. 定档位（`light` 1–3 页 / `standard` 10–20 / `deep` 30+ 且优先一手源）
2. 拆 3–6 个子查询，每个写明期待的源类型
3. 生成 `urls.txt`，按子查询分组
4. 调引擎，用 `--route auto` 按 URL 选出口
5. **先读 `index.md`** 再读正文，记录覆盖率
6. 摘成「断言 → 原文引用 → 来源」表
7. 跑一轮缺口补抓（`deep` 两轮）
8. 每条引用用 `grep -F` 回查
9. 写 `report.md`：结论、证据表、冲突、覆盖率、什么会改变结论

产物都在本次运行的 `out/<slug>/` 下。

## 保证

- **覆盖率永远报出来**：`fetched: N of M`，附未读清单与每个 URL 的原因。
- **没有出处的数字不写**；找不到原文的断言删除或改标 `inference`。
- **区分「没搜到」与「没读到」**；后者是覆盖问题，不是关于世界的结论。
- **被封的域名不循环重试**：`blocked-datadome` 一类直接转人工。

## 局限

- `standard` 只允许一轮补抓，是刻意的成本控制；难题可能留下真实缺口，报告会写明是哪几个。
- 引用回查是**模型执行**的，不是代码强制。技能把这一步做成机械动作（逐条 `grep -F`），但跳过它的运行产出的报告看起来完全一样。
- 引擎读不到多半是出口 IP 问题，本技能无法解决，只能如实报告。

## 许可

MIT，见 [LICENSE](LICENSE)。

# research-report

> **中文版：[README.zh-CN.md](README.zh-CN.md)** · English below

## 中文简介

把一个研究问题变成一份带出处的报告：自己拆子查询、收集 URL、调用抓取引擎，先核对哪些页真的读到了，再把每条结论回查到原文，最后列出没读到的来源。

- **安装**：`git clone` 后 `python install.py`——会连抓取引擎一起装上
- **用法**：直接向 Agent 提一个需要多源回答的问题
- **产物**：`out/<slug>/report.md`，含结论、证据表、冲突、覆盖率、未读清单
- **依赖**：自己没有抓取代码，引擎缺失时安装器会解决
- **局限**：引用回查由模型执行，不是代码强制

完整中文文档见 [README.zh-CN.md](README.zh-CN.md)。

---


An agent skill that turns a question into a checked report — not a pile of pages.

It plans sub-queries, collects a URL list, calls a fetch engine, **checks which pages were actually read**, extracts claims with verbatim quotes, verifies every quote against the saved text, and reports what it could not read.

**It ships no fetching code.** Reading is delegated to [`accessing-blocked-sites`](https://github.com/AleHeinesen/accessing-blocked-sites), which handles per-site egress selection, Cloudflare, and the honest failure verdicts this skill depends on. Installing `research-report` installs that engine by default.

```
question → sub-queries → urls.txt → engine → index.md (coverage)
        → corpus.md (evidence) → gap round → report.md
```

## Why the split

Most research answers fail in three ways that look alike: they read too few sources, they treat a blocked page as a read page, and they state things no source said. The engine solves the first failure mode's *mechanics*; this skill solves the *judgement*:

| Layer | Owner | Responsibility |
|---|---|---|
| execution | `accessing-blocked-sites` | get the bytes, or say precisely why not |
| decision | `research-report` | what to read, whether it was read, what it proves |

The dependency is one-way. The engine never calls this skill and works fine without it.

## Install

Requires Python 3.10+ and an installed Chrome, Edge or Chromium. macOS, Linux and Windows are all supported: the fetch step resolves the engine directory and the interpreter for the shell it finds — PowerShell or POSIX — instead of assuming a POSIX path.

```bash
git clone https://github.com/AleHeinesen/research-report && cd research-report
python install.py                # detects ~/.dsh, ~/.claude, ~/.cursor or ~/.agents
```

This installs **both** skills and provisions Playwright for the engine. The engine is resolved from, in order:

1. `--engine-src <path>` — a local checkout of the engine repo
2. `../accessing-blocked-sites` — a sibling checkout (development layout)
3. an engine already present in the target skills directory
4. `git clone` of `--engine-url` at `--engine-ref`

```bash
python install.py --engine-src ~/src/accessing-blocked-sites
python install.py --engine-url https://github.com/AleHeinesen/accessing-blocked-sites --engine-ref main
python install.py --no-engine     # report only; the engine must already be installed
python install.py --no-venv --dry-run
```

Installer notes: an existing skill directory not created by the installer is left alone unless you pass `--force`. Nothing is downloaded at task time — if the engine goes missing later, the skill stops and says so rather than fetching on its own.

Restart the agent afterwards so it picks up the skills.

## Use

Ask for a researched answer. The skill triggers on comparisons, due diligence, surveys, and "read several sources and tell me". It will:

1. state the question and pick a tier (`light` 1–3 pages, `standard` 10–20, `deep` 30+ with primary sources);
2. write 3–6 sub-queries, each naming the source type you expect;
3. build `urls.txt`, grouped by sub-query;
4. call the engine with `--route auto` (per-URL egress choice);
5. read `index.md` **before** any content, and record coverage;
6. extract claims with verbatim quotes into a claim → quote → source table;
7. run one gap round (two for `deep`) against what is still missing or contradictory;
8. verify each quote with `grep -F` against `corpus.md`;
9. write `report.md`: answer, evidence table, conflicts, coverage, what would change the answer.

Artifacts live in the run's own `out/<slug>/`: `urls.txt`, `run/` (engine output), `report.md`.

## Guarantees

- **Coverage is always reported** as `fetched: N of M`, with the unread list and a reason per URL.
- **No number without a quote, no quote without a URL.** Unsupported claims are deleted or relabelled `inference`.
- **"No evidence found" is distinguished from "could not read".** The second is a coverage problem, not a finding about the world.
- **Blocked domains are not retried in a loop.** A `blocked-datadome` / `blocked-perimeterx` verdict is a handoff item.

## Limits

- One gap round on `standard` is deliberate cost control; a hard question can leave real gaps, and the report says which.
- Quote verification is model-executed, not code-enforced. The skill makes the step mechanical (`grep -F` per claim), but a run that skips it produces a report that looks the same.
- The engine's failures are IP-reputation problems; this skill cannot fix them, only report them.

## Layout

```
skills/research-report/SKILL.md   the whole skill (no code)
install.py                        installs this skill + the engine
```

## License

MIT — see [LICENSE](LICENSE).

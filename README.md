# FDA AdCom Briefing Monitor

一个面向 FDA Advisory Committee briefing documents 的 MVP pipeline。默认只做监控、下载、解析、AI/规则打分和通知，不自动交易。

## Pipeline

1. **Event discovery**
   - 从 FDA Advisory Committee Calendar、Recently Updated Advisory Committee Materials、Committees and Meeting Materials 开始。
   - 递归抓取 committee 子页、年度 meeting materials 页、meeting announcement 页。
   - 只保留 briefing/background/questions 类 PDF，过滤 agenda、roster、minutes、transcript、presentation 等噪声。

2. **Document intake**
   - 下载新增 PDF。
   - 按 URL 做去重，保存到 `data/raw_pdfs/`。
   - 把每次处理记录写入 `data/state.json` 和 `data/runs/`。

3. **Text extraction**
   - 用 `pypdf` 提取全文。
   - 按标题候选切分 executive summary、efficacy、safety、questions。

4. **Analysis**
   - 有 API key 时调用 AI 模型输出结构化 JSON。
   - 没有 API key 时使用保守的关键词启发式打分，方便本地干跑。

5. **Signal generation**
   - 输出 `STRONG_NEGATIVE`、`NEGATIVE`、`MIXED`、`POSITIVE`、`STRONG_POSITIVE`。
   - 默认建议人工复核，不进入自动下单。

6. **Notification**
   - 控制台输出。
   - 可选 Telegram 通知。

## Quick Start

```bash
/home/typbing/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m venv .venv-codex
source .venv-codex/bin/activate
pip install -e ".[ai,dev]"
cp .env.example .env
```

先跑一次干跑：

```bash
fda-adcom run-once --dry-run
```

只调试页面发现和 PDF 候选，不下载、不分析：

```bash
fda-adcom discover --max-pages 80
fda-adcom discover --pages --max-pages 80
```

首次启动实时监控前，建议先把当前 FDA 站上已有材料标记为已见过，避免把历史 PDF 全部当成新事件处理：

```bash
fda-adcom bootstrap-seen --max-pages 80
```

批量历史样本入库。默认只下载并解析元数据，不调用 AI，并跳过已经入库过的 FDA briefing/background 样本：

```bash
fda-adcom backfill-history --max-pages 45 --limit 5
```

按价值筛选历史样本：

```bash
fda-adcom rank-history --limit 25 --output data/runs/history_rank_top25.json
```

确认样本和成本后，再打开 AI 分析：

```bash
fda-adcom analyze-ranked-history --limit 1 --min-score 80
```

Sponsor/ticker 映射：

```bash
fda-adcom map-tickers --limit 50 --output data/runs/history_ticker_map_top50.json
```

市场数据补全：

```bash
fda-adcom enrich-market --limit 25 --output data/runs/history_market_enriched_top25.json
```

初始化/维护 outcome 标签表：

```bash
fda-adcom init-outcomes --limit 80
```

标签表位置：

```text
data/outcome_labels.csv
```

第一版小样本回测：

```bash
fda-adcom mini-backtest --output data/runs/mini_backtest.json
```

每日检查：

```bash
fda-adcom daily-report --hours 24
```

持续监控：

```bash
fda-adcom watch
```

分析本地 PDF：

```bash
fda-adcom analyze-pdf /path/to/briefing.pdf
```

## Environment

关键配置见 `.env.example`。

如果使用 OpenAI：

```bash
AI_PROVIDER=openai
AI_MODEL=gpt-4.1
OPENAI_API_KEY=...
```

如果使用 Anthropic：

```bash
AI_PROVIDER=anthropic
AI_MODEL=claude-3-5-sonnet-latest
ANTHROPIC_API_KEY=...
```

如果使用 DeepSeek：

```bash
AI_PROVIDER=deepseek
AI_MODEL=deepseek-chat
DEEPSEEK_API_KEY=...
DEEPSEEK_BASE_URL=https://api.deepseek.com
```

Telegram 可选：

```bash
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
```

## Deployment

### 本机部署

适合最初 1-3 个月纸面跟踪：

```bash
source .venv-codex/bin/activate
fda-adcom watch
```

### systemd

把 `deploy/fda-adcom.service` 里的路径改成你的绝对路径后：

```bash
sudo cp deploy/fda-adcom.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now fda-adcom
```

### Docker

```bash
docker compose up -d --build
```

## Trading Guardrail

这个仓库故意没有默认自动下单。建议上线顺序：

1. 纸面预测 50-100 个文档或至少 3-6 个月。
2. 用小仓位手动执行。
3. 只有在回测、实时纸面预测、日志审计都稳定后，再接 broker。

不要裸空 biotech；不要把 AI 评分直接等同于审批概率；不要在模型无法引用原文证据时交易。

## Official FDA Sources

- FDA Advisory Committee Calendar: https://www.fda.gov/advisory-committees/advisory-committee-calendar
- FDA Committees and Meeting Materials: https://www.fda.gov/advisory-committees/committees-and-meeting-materials
- FDA Advisory Committee Q&A: https://www.fda.gov/advisory-committees/about-advisory-committees/common-questions-and-answers-about-fda-advisory-committee-meetings

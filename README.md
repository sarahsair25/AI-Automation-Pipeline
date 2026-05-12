# 🤖 AI Automation Pipeline

> **Production-ready Python framework** that scrapes the web, analyses content with GPT-4, generates HTML reports, and dispatches results via Email & Slack — fully automated.

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776ab?logo=python&logoColor=white)](https://python.org)
[![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4o-412991?logo=openai)](https://openai.com)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

---

## ✨ Features

| Module | What it does |
|---|---|
| 🕷️ **DataCollector** | Async-ready web scraper with retry + back-off |
| 🧠 **AIAnalyser** | GPT-powered summary, sentiment & insight extraction |
| 📄 **ReportGenerator** | Styled HTML reports saved locally |
| 📬 **Notifier** | SMTP email + Slack webhook delivery |
| 🔁 **AutomationPipeline** | One-call orchestrator: Collect → Analyse → Report → Notify |

---

## 🚀 Quick Start

```bash
# 1. Clone
git clone https://github.com/sarahsair25/ai-automation-pipeline.git
cd ai-automation-pipeline

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set environment variables
export OPENAI_API_KEY="sk-..."
export SMTP_USER="you@gmail.com"
export SMTP_PASSWORD="app-password"
export SLACK_WEBHOOK_URL="https://hooks.slack.com/..."

# 4. Run
python ai_automation.py
```

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────┐
│                  AutomationPipeline                 │
│                                                     │
│  DataCollector  →  AIAnalyser  →  ReportGenerator  │
│                                         │           │
│                                       Notifier      │
│                                    (Email / Slack)  │
└─────────────────────────────────────────────────────┘
```

### Pipeline Steps

```
1. COLLECT   – Fetch & parse web pages (BeautifulSoup + requests)
2. ANALYSE   – Send to GPT-4o for structured JSON analysis
3. REPORT    – Render HTML report with insights
4. NOTIFY    – Email report + Slack summary
```

---

## 📁 Project Structure

```
ai-automation-pipeline/
├── ai_automation.py      # Core pipeline (single-file, fully documented)
├── requirements.txt      # Minimal dependencies
├── reports/              # Auto-generated HTML reports
├── tests/
│   ├── test_collector.py
│   ├── test_analyser.py
│   └── test_notifier.py
└── README.md
```

---

## ⚙️ Configuration

All settings are driven by **environment variables** — no hard-coded secrets.

| Variable | Required | Description |
|---|---|---|
| `OPENAI_API_KEY` | ✅ | Your OpenAI API key |
| `SMTP_HOST` | ❌ | SMTP server (default: `smtp.gmail.com`) |
| `SMTP_USER` | ❌ | Sender email address |
| `SMTP_PASSWORD` | ❌ | SMTP password / app password |
| `SLACK_WEBHOOK_URL` | ❌ | Incoming webhook for notifications |

---

## 🔌 Extend It

The pipeline is **plug-and-play**. Drop in your own data source or LLM:

```python
# Custom data source
class MyCollector(DataCollector):
    def collect(self, url):
        # fetch from an API, database, RSS feed…
        return my_articles

# Custom LLM (Anthropic, Gemini, local Ollama…)
class MyAnalyser(AIAnalyser):
    def analyse(self, articles, topic):
        # call your preferred model
        return structured_result

# Plug into the pipeline
pipeline = AutomationPipeline(
    topic="My Topic",
    source_url="https://example.com",
)
pipeline.collector = MyCollector()
pipeline.analyser  = MyAnalyser()
pipeline.run()
```

---

## 🧪 Tests

```bash
pytest tests/ -v --tb=short
```

---

## 📦 Requirements

```
requests>=2.31
beautifulsoup4>=4.12
openai>=1.30
```

---

## 🤝 Contributing

PRs are welcome! Please open an issue first to discuss large changes.

1. Fork the repo
2. Create a feature branch (`git checkout -b feat/my-feature`)
3. Commit with conventional commits (`feat: add RSS support`)
4. Open a pull request

---

## 📜 License

MIT © Your Name

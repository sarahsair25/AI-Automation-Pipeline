"""
AI Automation Pipeline with Python
====================================
A production-ready framework that automates:
  1. Web scraping & data collection
  2. AI-powered content analysis (via OpenAI / local LLM)
  3. Email report generation & dispatch
  4. Slack/Webhook notifications
  5. Scheduled execution with retry logic

Author  : Your Name
License : MIT
"""

from __future__ import annotations

import json
import logging
import os
import smtplib
import time
from dataclasses import dataclass, field
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Optional

import requests
from bs4 import BeautifulSoup
from openai import OpenAI

# ──────────────────────────────────────────────
# Logging
# ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("ai_automation")


# ──────────────────────────────────────────────
# Config (reads from env; falls back to defaults)
# ──────────────────────────────────────────────
@dataclass
class Config:
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    smtp_host: str = field(default_factory=lambda: os.getenv("SMTP_HOST", "smtp.gmail.com"))
    smtp_port: int = 587
    smtp_user: str = field(default_factory=lambda: os.getenv("SMTP_USER", ""))
    smtp_password: str = field(default_factory=lambda: os.getenv("SMTP_PASSWORD", ""))
    slack_webhook_url: str = field(default_factory=lambda: os.getenv("SLACK_WEBHOOK_URL", ""))
    report_dir: Path = Path("reports")
    max_retries: int = 3
    retry_delay: float = 2.0  # seconds


CONFIG = Config()


# ──────────────────────────────────────────────
# Decorator: retry with exponential back-off
# ──────────────────────────────────────────────
def retry(max_attempts: int = 3, delay: float = 2.0, exceptions: tuple = (Exception,)):
    """Retry a function on failure with exponential back-off."""

    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapper(*args, **kwargs):
            for attempt in range(1, max_attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except exceptions as exc:
                    wait = delay * (2 ** (attempt - 1))
                    logger.warning(
                        "Attempt %d/%d failed for '%s': %s. Retrying in %.1fs…",
                        attempt, max_attempts, fn.__name__, exc, wait,
                    )
                    if attempt == max_attempts:
                        raise
                    time.sleep(wait)

        return wrapper

    return decorator


# ──────────────────────────────────────────────
# 1. Data Collector (web scraping)
# ──────────────────────────────────────────────
class DataCollector:
    """Scrape structured data from any web page."""

    DEFAULT_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; AIAutomationBot/1.0; "
            "+https://github.com/yourhandle/ai-automation)"
        )
    }

    @retry(max_attempts=3, delay=1.5, exceptions=(requests.RequestException,))
    def fetch_page(self, url: str, timeout: int = 15) -> str:
        """Return the raw HTML of *url*."""
        logger.info("Fetching %s", url)
        response = requests.get(url, headers=self.DEFAULT_HEADERS, timeout=timeout)
        response.raise_for_status()
        return response.text

    def parse_articles(self, html: str, base_url: str = "") -> list[dict[str, str]]:
        """
        Extract article-like content (title + body snippet) from HTML.
        Works on most news / blog pages via heuristic tag selection.
        """
        soup = BeautifulSoup(html, "html.parser")

        # Remove noisy elements
        for tag in soup(["script", "style", "nav", "footer", "aside"]):
            tag.decompose()

        articles: list[dict[str, str]] = []
        seen: set[str] = set()

        for heading in soup.find_all(["h1", "h2", "h3"], limit=20):
            title = heading.get_text(strip=True)
            if not title or title in seen:
                continue
            seen.add(title)

            # Grab the next sibling paragraph as the snippet
            sibling = heading.find_next_sibling("p")
            snippet = sibling.get_text(strip=True) if sibling else ""

            # Try to extract a link
            anchor = heading.find("a", href=True)
            link = anchor["href"] if anchor else ""
            if link and not link.startswith("http") and base_url:
                link = base_url.rstrip("/") + "/" + link.lstrip("/")

            articles.append({"title": title, "snippet": snippet, "url": link})

        logger.info("Parsed %d articles", len(articles))
        return articles

    def collect(self, url: str) -> list[dict[str, str]]:
        html = self.fetch_page(url)
        base = "/".join(url.split("/")[:3])
        return self.parse_articles(html, base_url=base)


# ──────────────────────────────────────────────
# 2. AI Analyser (OpenAI GPT)
# ──────────────────────────────────────────────
class AIAnalyser:
    """Use GPT to summarise and extract insights from collected articles."""

    def __init__(self, model: str = "gpt-4o-mini"):
        if not CONFIG.openai_api_key:
            raise EnvironmentError("OPENAI_API_KEY is not set.")
        self.client = OpenAI(api_key=CONFIG.openai_api_key)
        self.model = model

    @retry(max_attempts=3, delay=2.0)
    def analyse(self, articles: list[dict[str, str]], topic: str = "AI & Technology") -> dict[str, Any]:
        """
        Send article titles + snippets to GPT and receive:
          - executive_summary  : 3-sentence overview
          - key_insights       : list[str] of bullet points
          - sentiment          : "positive" | "neutral" | "negative"
          - recommended_action : short recommendation string
        """
        content_block = "\n\n".join(
            f"Title: {a['title']}\nSnippet: {a['snippet']}" for a in articles[:10]
        )

        system_prompt = (
            "You are a professional business intelligence analyst. "
            "Analyse the provided articles and return ONLY valid JSON with these keys: "
            "executive_summary (string), key_insights (list of strings, max 5), "
            "sentiment (one of: positive/neutral/negative), "
            "recommended_action (string)."
        )

        user_prompt = (
            f"Topic: {topic}\n\nArticles:\n{content_block}\n\n"
            "Return only JSON, no markdown fences."
        )

        logger.info("Sending %d articles to %s for analysis…", len(articles), self.model)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=800,
        )

        raw = response.choices[0].message.content.strip()
        return json.loads(raw)


# ──────────────────────────────────────────────
# 3. Report Generator
# ──────────────────────────────────────────────
class ReportGenerator:
    """Assemble a human-readable HTML/text report from analysis results."""

    def __init__(self, output_dir: Path = CONFIG.report_dir):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _html_report(
        self,
        topic: str,
        analysis: dict[str, Any],
        articles: list[dict[str, str]],
        timestamp: str,
    ) -> str:
        insights_html = "".join(f"<li>{i}</li>" for i in analysis.get("key_insights", []))
        articles_html = "".join(
            f'<li><a href="{a["url"]}">{a["title"]}</a></li>' for a in articles[:10]
        )
        sentiment = analysis.get("sentiment", "neutral")
        sentiment_color = {"positive": "#16a34a", "neutral": "#2563eb", "negative": "#dc2626"}.get(
            sentiment, "#2563eb"
        )

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>AI Intelligence Report – {topic}</title>
  <style>
    body {{ font-family: Georgia, serif; max-width: 760px; margin: 40px auto; color: #1e293b; }}
    h1 {{ border-bottom: 2px solid #0f172a; padding-bottom: 8px; }}
    .badge {{ display: inline-block; padding: 4px 12px; border-radius: 20px;
              background: {sentiment_color}; color: #fff; font-size: 0.85rem; }}
    ul {{ line-height: 1.8; }}
    footer {{ margin-top: 40px; font-size: 0.8rem; color: #64748b; }}
  </style>
</head>
<body>
  <h1>📊 AI Intelligence Report</h1>
  <p><strong>Topic:</strong> {topic} &nbsp;|&nbsp;
     <strong>Generated:</strong> {timestamp} &nbsp;|&nbsp;
     <span class="badge">{sentiment}</span>
  </p>

  <h2>Executive Summary</h2>
  <p>{analysis.get("executive_summary", "N/A")}</p>

  <h2>Key Insights</h2>
  <ul>{insights_html}</ul>

  <h2>Recommended Action</h2>
  <p>{analysis.get("recommended_action", "N/A")}</p>

  <h2>Source Articles ({len(articles)})</h2>
  <ul>{articles_html}</ul>

  <footer>Generated automatically by AI Automation Pipeline</footer>
</body>
</html>"""

    def save(
        self,
        topic: str,
        analysis: dict[str, Any],
        articles: list[dict[str, str]],
    ) -> Path:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        safe_topic = topic.replace(" ", "_").lower()
        filepath = self.output_dir / f"report_{safe_topic}_{timestamp}.html"

        html = self._html_report(topic, analysis, articles, timestamp)
        filepath.write_text(html, encoding="utf-8")
        logger.info("Report saved → %s", filepath)
        return filepath


# ──────────────────────────────────────────────
# 4. Notifier (Email + Slack)
# ──────────────────────────────────────────────
class Notifier:
    """Send the finished report via Email and/or Slack."""

    # ── Email ──────────────────────────────────
    @retry(max_attempts=2, delay=3.0, exceptions=(smtplib.SMTPException, OSError))
    def send_email(
        self,
        to_addresses: list[str],
        subject: str,
        body_html: str,
    ) -> bool:
        if not (CONFIG.smtp_user and CONFIG.smtp_password):
            logger.warning("SMTP credentials not set – skipping email.")
            return False

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = CONFIG.smtp_user
        msg["To"] = ", ".join(to_addresses)
        msg.attach(MIMEText(body_html, "html"))

        with smtplib.SMTP(CONFIG.smtp_host, CONFIG.smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.login(CONFIG.smtp_user, CONFIG.smtp_password)
            server.sendmail(CONFIG.smtp_user, to_addresses, msg.as_string())

        logger.info("Email sent to %s", to_addresses)
        return True

    # ── Slack ──────────────────────────────────
    @retry(max_attempts=2, delay=2.0, exceptions=(requests.RequestException,))
    def send_slack(self, message: str) -> bool:
        if not CONFIG.slack_webhook_url:
            logger.warning("SLACK_WEBHOOK_URL not set – skipping Slack notification.")
            return False

        payload = {"text": message}
        resp = requests.post(CONFIG.slack_webhook_url, json=payload, timeout=10)
        resp.raise_for_status()
        logger.info("Slack notification sent.")
        return True


# ──────────────────────────────────────────────
# 5. Pipeline Orchestrator
# ──────────────────────────────────────────────
class AutomationPipeline:
    """
    High-level orchestrator that chains:
      Collect → Analyse → Report → Notify
    """

    def __init__(
        self,
        topic: str,
        source_url: str,
        notify_emails: Optional[list[str]] = None,
        slack_message_prefix: str = "📰 New AI Report",
    ):
        self.topic = topic
        self.source_url = source_url
        self.notify_emails = notify_emails or []
        self.slack_prefix = slack_message_prefix

        self.collector = DataCollector()
        self.analyser = AIAnalyser()
        self.reporter = ReportGenerator()
        self.notifier = Notifier()

    def run(self) -> dict[str, Any]:
        logger.info("═" * 60)
        logger.info("Pipeline START  topic=%s", self.topic)
        logger.info("═" * 60)

        # Step 1 – Collect
        articles = self.collector.collect(self.source_url)
        if not articles:
            logger.error("No articles collected. Aborting.")
            return {"status": "failed", "reason": "no_articles"}

        # Step 2 – Analyse
        analysis = self.analyser.analyse(articles, topic=self.topic)
        logger.info("Analysis: %s", json.dumps(analysis, indent=2))

        # Step 3 – Report
        report_path = self.reporter.save(self.topic, analysis, articles)

        # Step 4 – Notify
        if self.notify_emails:
            report_html = report_path.read_text(encoding="utf-8")
            self.notifier.send_email(
                to_addresses=self.notify_emails,
                subject=f"[AI Report] {self.topic} – {datetime.now():%Y-%m-%d}",
                body_html=report_html,
            )

        slack_msg = (
            f"{self.slack_prefix}: *{self.topic}*\n"
            f"Sentiment: *{analysis.get('sentiment','N/A')}*\n"
            f"Summary: {analysis.get('executive_summary','')}\n"
            f"Report saved to `{report_path}`"
        )
        self.notifier.send_slack(slack_msg)

        logger.info("═" * 60)
        logger.info("Pipeline DONE")
        logger.info("═" * 60)

        return {
            "status": "success",
            "articles_collected": len(articles),
            "analysis": analysis,
            "report": str(report_path),
        }


# ──────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────
if __name__ == "__main__":
    pipeline = AutomationPipeline(
        topic="Artificial Intelligence Trends",
        source_url="https://techcrunch.com/category/artificial-intelligence/",
        notify_emails=["you@example.com"],
    )
    result = pipeline.run()
    print(json.dumps(result, indent=2))

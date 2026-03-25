# AIAgentClassSelect
AI Agent for select child class weekly update new classes.

# AI Agent for Kids Course Selection

**AIAgentClassSelect** is a Python-based AI agent that automatically searches, summarizes, and categorizes courses and activities suitable for children ages 6–8. It integrates web scraping with AI summarization (OpenAI GPT) and can run weekly using GitHub Actions.

---

## Features

- Scrapes multiple websites for kids' courses and activities
- Cleans, deduplicates, and categorizes courses (STEM, Art, Dance, etc.)
- Uses GPT API to summarize courses and generate Markdown outputs
- Tracks new and updated courses with historical comparison
- Optional email/Slack notifications with weekly updates
- Fully automated using GitHub Actions

---

## Requirements

- Python 3.11+
- Packages: `requests`, `beautifulsoup4`, `openai`
- GitHub repository for automated workflow
- OpenAI API Key
- Optional: SMTP credentials for email notifications

---

## Installation

1. Clone the repository:

```bash
git clone https://github.com/scmbuildrelease/AIAgentClassSelect.git
cd AIAgentClassSelect

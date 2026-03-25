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
```

2. Install Python dependencies:

```bash
pip install --upgrade pip
pip install requests beautifulsoup4 openai
```


3. Set environment variables (recommended via GitHub Secrets for automation):

```bash
export OPENAI_API_KEY="your_openai_api_key"
export EMAIL_USER="your_email@example.com"       # optional
export EMAIL_PASS="your_email_password"          # optional
```


4.  Usage Run the script locally:


```bash
python scrape_courses.py

```

5.  GitHub Actions Automation

The project includes a GitHub Actions workflow .github/workflows/weekly_courses.yml:

Runs weekly on a schedule (cron) or manually (workflow_dispatch)
Fetches course data, generates Markdown, and commits updates to the repository
Optional: sends email notifications for weekly updates







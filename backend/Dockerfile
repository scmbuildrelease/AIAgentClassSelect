# Build from the repository root (context "."), so the shared activity_tracker package
# (bilingual search, display language) and config/settings.json (glossary) are included.
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUTF8=1 LANG=C.UTF-8

RUN pip install --no-cache-dir "flask>=2.3" "requests>=2.31" "beautifulsoup4>=4.12"

COPY activity_tracker ./activity_tracker
COPY config/settings.json ./config/settings.json
COPY backend/app.py .

# Activity dates are evaluated in the Bay Area time zone (settings.json "timezone"). The base image's
# system tz database provides it today; fail the build if it ever goes missing instead of silently using UTC.
RUN python -c "import json, zoneinfo; zoneinfo.ZoneInfo(json.load(open('config/settings.json'))['timezone'])"

RUN mkdir -p /data

EXPOSE 8000
CMD ["python", "app.py"]

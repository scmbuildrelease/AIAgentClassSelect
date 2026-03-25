import requests
from bs4 import BeautifulSoup
import json
import openai
from datetime import datetime
import os
import smtplib
from email.mime.text import MIMEText

# ---------- CONFIG ----------
openai.api_key = os.getenv("OPENAI_API_KEY")  # Use GitHub Secrets
output_file = f"courses_{datetime.now().strftime('%Y%m%d')}.md"
history_file = "courses_history.json"

# Email notification (optional)
EMAIL_NOTIFY = False
SMTP_SERVER = "smtp.example.com"
SMTP_PORT = 587
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")
EMAIL_TO = ["your_email@example.com"]

WEBLINK_FILE = "weblink.md"  # File with website URLs

# ---------- Step 0: Read weblink.md ----------
def read_weblinks(file_path=WEBLINK_FILE):
    sites = []
    if not os.path.exists(file_path):
        print(f"⚠️ {file_path} not found!")
        return sites

    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue  # skip empty lines or comments
            if "," in line:
                url, category = line.split(",", 1)
                sites.append({"url": url.strip(), "type": category.strip()})
            else:
                sites.append({"url": line.strip(), "type": "Unknown"})
    return sites

# ---------- Step 1: Scrape courses ----------
def scrape_courses(sites):
    courses = []
    for site in sites:
        url = site["url"]
        category = site["type"]
        try:
            response = requests.get(url, timeout=10)
            if response.status_code != 200:
                print(f"⚠️ Failed to fetch {url}, status {response.status_code}")
                continue
            soup = BeautifulSoup(response.text, "html.parser")
            # NOTE: Adjust selectors to match your target website
            for item in soup.select(".course-item"):
                title_el = item.select_one(".course-title")
                age_el = item.select_one(".course-age")
                loc_el = item.select_one(".course-location")
                link_el = item.select_one("a")
                if not title_el or not age_el or not loc_el or not link_el:
                    continue
                courses.append({
                    "title": title_el.text.strip(),
                    "age": age_el.text.strip(),
                    "location": loc_el.text.strip(),
                    "link": link_el.get("href").strip(),
                    "category": category
                })
        except Exception as e:
            print(f"⚠️ Error fetching {url}: {e}")
    return courses

# ---------- Step 2: Compare with history ----------
def compare_history(new_courses):
    added, updated = [], []
    if os.path.exists(history_file):
        with open(history_file, "r", encoding="utf-8") as f:
            history = json.load(f)
    else:
        history = []

    history_titles = {c["title"]: c for c in history}
    for course in new_courses:
        if course["title"] not in history_titles:
            added.append(course)
        else:
            old = history_titles[course["title"]]
            if course != old:
                updated.append(course)

    # Save latest history
    with open(history_file, "w", encoding="utf-8") as f:
        json.dump(new_courses, f, ensure_ascii=False, indent=2)
    return added, updated

# ---------- Step 3: AI summarize ----------
def summarize_courses(courses):
    if not courses:
        return "⚠️ No courses found to summarize."

    prompt = (
        f"请将以下儿童课程信息整理成 Markdown 表格，"
        f"包含课程名、适合年龄、地点、网址、分类，并用 1-5 星评分推荐，"
        f"标注新增课程和更新课程:\n{json.dumps(courses, ensure_ascii=False)}"
    )

    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
    )
    return response['choices'][0]['message']['content']

# ---------- Step 4: Save Markdown ----------
def save_markdown(content):
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"✅ Saved {output_file}")

# ---------- Step 5: Optional email ----------
def send_email(content):
    if not EMAIL_NOTIFY:
        return
    msg = MIMEText(content, "plain", "utf-8")
    msg["Subject"] = f"每周儿童课程更新 {datetime.now().strftime('%Y-%m-%d')}"
    msg["From"] = EMAIL_USER
    msg["To"] = ", ".join(EMAIL_TO)

    server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
    server.starttls()
    server.login(EMAIL_USER, EMAIL_PASS)
    server.sendmail(EMAIL_USER, EMAIL_TO, msg.as_string())
    server.quit()
    print("📧 Email notification sent.")

# ---------- Main ----------
if __name__ == "__main__":
    sites = read_weblinks()
    if not sites:
        print("⚠️ No websites to scrape. Exiting.")
        exit(1)

    print(f"🔍 Loaded {len(sites)} sites from {WEBLINK_FILE}")
    courses = scrape_courses(sites)
    print(f"✅ Found {len(courses)} courses")

    added, updated = compare_history(courses)
    print(f"🆕 Added: {len(added)}, 🔄 Updated: {len(updated)}")

    md_content = summarize_courses(courses)
    save_markdown(md_content)
    send_email(md_content)
    print("🎉 Done!")

import requests
from bs4 import BeautifulSoup
import json
import openai
from datetime import datetime
import os
import smtplib
from email.mime.text import MIMEText

# ---------- 配置 ----------
openai.api_key = os.getenv("OPENAI_API_KEY")  # GitHub Secrets 管理
output_file = f"courses_{datetime.now().strftime('%Y%m%d')}.md"
history_file = "courses_history.json"

# 可抓取网站列表
sites = [
    {"url": "https://www.robokids.com/classes", "type": "STEM"},
    {"url": "https://www.artschool.com/classes", "type": "Art"},
    # 可继续添加更多
]

# 邮件通知配置（可选）
EMAIL_NOTIFY = False
SMTP_SERVER = "smtp.example.com"
SMTP_PORT = 587
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")
EMAIL_TO = ["your_email@example.com"]

# ---------- Step 1: 数据抓取 ----------
def scrape_courses():
    courses = []
    for site in sites:
        response = requests.get(site["url"])
        if response.status_code != 200:
            continue
        soup = BeautifulSoup(response.text, "html.parser")
        for item in soup.select(".course-item"):
            title = item.select_one(".course-title").text.strip()
            age = item.select_one(".course-age").text.strip()
            location = item.select_one(".course-location").text.strip()
            link = item.select_one("a")["href"]
            courses.append({
                "title": title,
                "age": age,
                "location": location,
                "link": link,
                "category": site["type"]
            })
    return courses

# ---------- Step 2: 历史对比 ----------
def compare_history(new_courses):
    added = []
    updated = []
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
    # 保存最新历史
    with open(history_file, "w", encoding="utf-8") as f:
        json.dump(new_courses, f, ensure_ascii=False, indent=2)
    return added, updated

# ---------- Step 3: AI 摘要生成 ----------
def summarize_courses(courses):
    course_text = json.dumps(courses, ensure_ascii=False)
    prompt = (
        f"请将以下儿童课程信息整理成 Markdown 表格，"
        f"包含课程名、适合年龄、地点、网址、分类，并用 1-5 星评分推荐，"
        f"标注新增课程和更新课程:\n{course_text}"
    )
    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
    )
    return response['choices'][0]['message']['content']

# ---------- Step 4: 输出文件 ----------
def save_markdown(content):
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"✅ 已保存 {output_file}")

# ---------- Step 5: 可选通知 ----------
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
    print("📧 已发送邮件通知")

# ---------- 主流程 ----------
if __name__ == "__main__":
    print("🔍 开始抓取课程信息...")
    raw_courses = scrape_courses()
    if not raw_courses:
        print("⚠️ 没有抓到课程信息！")
    else:
        added, updated = compare_history(raw_courses)
        print(f"✅ 抓到 {len(raw_courses)} 条课程信息")
        print(f"🆕 新增: {len(added)}, 🔄 更新: {len(updated)}")
        md_content = summarize_courses(raw_courses)
        save_markdown(md_content)
        send_email(md_content)
        print("🎉 完成！")

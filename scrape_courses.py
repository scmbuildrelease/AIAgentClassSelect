import requests
from bs4 import BeautifulSoup
import json
import openai
from datetime import datetime

# ---------- 配置 ----------
openai.api_key = "YOUR_OPENAI_API_KEY"  # 推荐用 GitHub Secrets 管理
output_file = f"courses_{datetime.now().strftime('%Y%m%d')}.md"

# 示例网站（可以扩展）
sites = [
    "https://www.robokids.com/classes",  # 假设是课程列表页
]

# ---------- Step 1: 数据抓取 ----------
def scrape_courses():
    courses = []
    for url in sites:
        response = requests.get(url)
        if response.status_code != 200:
            continue
        soup = BeautifulSoup(response.text, "html.parser")
        # 假设课程信息在 <div class="course-item">
        for item in soup.select(".course-item"):
            title = item.select_one(".course-title").text.strip()
            age = item.select_one(".course-age").text.strip()
            location = item.select_one(".course-location").text.strip()
            link = item.select_one("a")["href"]
            courses.append({
                "title": title,
                "age": age,
                "location": location,
                "link": link
            })
    return courses

# ---------- Step 2: AI 智能处理 ----------
def summarize_courses(courses):
    course_text = json.dumps(courses, ensure_ascii=False)
    prompt = (
        f"请将以下儿童课程信息整理成 Markdown 表格，"
        f"包含课程名、适合年龄、地点、网址，并用 1-5 星评分推荐：\n{course_text}"
    )
    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
    )
    return response['choices'][0]['message']['content']

# ---------- Step 3: 输出到文件 ----------
def save_markdown(content):
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"✅ 已保存 {output_file}")

# ---------- 主流程 ----------
if __name__ == "__main__":
    print("🔍 开始抓取课程信息...")
    raw_courses = scrape_courses()
    if not raw_courses:
        print("⚠️ 没有抓到课程信息！")
    else:
        print(f"✅ 抓到 {len(raw_courses)} 条课程信息，开始 AI 摘要...")
        md_content = summarize_courses(raw_courses)
        save_markdown(md_content)
        print("🎉 完成！")

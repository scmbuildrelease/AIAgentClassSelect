import requests, json, os
from parsers.generic_parser import parse_generic

WEBLINK = "weblink.md"
OUTPUT = "/data/courses_latest.json"

def read_links():
    sites = []
    with open(WEBLINK) as f:
        for line in f:
            if "," in line:
                url, cat = line.strip().split(",", 1)
                sites.append((url, cat))
    return sites

def run():
    all_courses = []

    for url, cat in read_links():
        try:
            res = requests.get(url, timeout=10)
            all_courses += parse_generic(res.text, cat, url)
        except:
            continue

    os.makedirs("/data", exist_ok=True)
    with open(OUTPUT, "w") as f:
        json.dump(all_courses, f)

if __name__ == "__main__":
    run()

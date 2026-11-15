"""Language detection and display-language selection for activity records.

Originals are never modified. `translations` only adds text next to them:
  translations = {"en": {"name": ..., "description": ..., "method": "provider" | "manual" | "machine"}}
  - provider: the provider's own page in the other language (linked duplicate)
  - manual:   written by a person in config/sources.json
  - machine:  machine translation (none are generated today; always labelled if added)
"""
import re
import unicodedata

CJK_RE = re.compile(r"[㐀-䶿一-鿿豈-﫿]")
LATIN_WORD_RE = re.compile(r"[A-Za-z]{3,}")
TRANSLATION_METHODS = {"provider", "manual", "machine"}

# Simplified/Traditional pairs for characters common in activity listings. Used to tell the
# two scripts apart and to make search script-insensitive. Deliberately small: characters
# shared by both scripts (e.g. 夏, 琴, 舞) need no entry.
_PAIRS = (
    "学學 国國 课課 乐樂 艺藝 术術 营營 编編 机機 数數 画畫 儿兒 报報 费費 时時 间間 岁歲 级級 龄齡 开開 "
    "华華 语語 写寫 读讀 练練 钢鋼 体體 动動 运運 个個 们們 这這 为為 会會 来來 对對 说說 发發 经經 现現 "
    "见見 长長 东東 车車 门門 问問 题題 员員 书書 买買 卖賣 亲親 认認 识識 让讓 请請 谢謝 应應 样樣 园園 "
    "场場 馆館 电電 话話 网網 页頁 区區 县縣 师師 设設 计計 论論 议議 证證 习習 验驗 线線 号號 单單 预預 "
    "约約 额額 满滿 选選 择擇 欢歡 资資 讯訊 联聯 络絡 处處 务務 际際 实實 观觀 赛賽 队隊 篮籃 戏戲 剧劇 "
    "绘繪 团團 围圍 阅閱 汉漢 价價 优優 适適 点點 钟鐘 礼禮 圣聖 库庫 诺諾 维維 尔爾 罗羅 奥奧 图圖 达達 "
    "湾灣 硅矽 码碼 气氣 环環 户戶 远遠 节節 届屆 补補 结結 关關 启啟 册冊 规規 则則"
)
TRAD_TO_SIMP = {}
for _pair in _PAIRS.split():
    if _pair[0] != _pair[1]:
        TRAD_TO_SIMP[_pair[1]] = _pair[0]
SIMP_ONLY = set(TRAD_TO_SIMP.values())
TRAD_ONLY = set(TRAD_TO_SIMP)


def to_simplified(text: str) -> str:
    return "".join(TRAD_TO_SIMP.get(ch, ch) for ch in text)


def detect_language(*texts: str | None) -> str | None:
    """'en', 'zh-Hans', 'zh-Hant', 'zh' (script unclear), 'mixed', or None (no letters)."""
    text = " ".join(t for t in texts if t)
    cjk = CJK_RE.findall(text)
    latin = LATIN_WORD_RE.findall(text)
    if not cjk:
        return "en" if latin else None
    if latin and len(latin) * 2 >= len(cjk) // 2:  # meaningful amounts of both scripts
        return "mixed"
    simp = sum(ch in SIMP_ONLY for ch in cjk)
    trad = sum(ch in TRAD_ONLY for ch in cjk)
    if simp > trad:
        return "zh-Hans"
    if trad > simp:
        return "zh-Hant"
    return "zh"


def lang_group(lang: str | None) -> str | None:
    """Collapse zh variants to 'zh' (translation keys are 'en' / 'zh')."""
    return "zh" if lang and lang.startswith("zh") else lang


def search_key(text: str | None) -> str:
    """Normalize for matching only: width, case, Traditional -> Simplified, whitespace."""
    text = unicodedata.normalize("NFKC", text or "").casefold()
    return re.sub(r"\s+", " ", to_simplified(text)).strip()


def display(rec: dict, preferred: str) -> dict:
    """Pick the title/description to show for a preferred language ('en' or 'zh*').

    Returns {"name", "description", "language", "kind"} where kind is
    'original', 'provider' / 'manual' / 'machine' translation, or 'original_only'
    (no text in the preferred language exists, so the original is shown).
    """
    want = lang_group(preferred) or "en"
    orig_lang = rec.get("original_language")
    original = {"name": rec.get("name"), "description": rec.get("description"), "language": orig_lang}
    if orig_lang == "mixed" or lang_group(orig_lang) == want or orig_lang is None:
        return {**original, "kind": "original"}
    tr = (rec.get("translations") or {}).get(want)
    if tr and tr.get("name"):
        return {"name": tr["name"], "description": tr.get("description"), "language": tr.get("language", want),
                "kind": tr.get("method", "machine")}
    return {**original, "kind": "original_only"}

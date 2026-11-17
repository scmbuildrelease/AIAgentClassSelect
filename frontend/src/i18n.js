// UI text only. Activity titles, descriptions, ages, dates and prices come from the API exactly as published.
export const LANGS = { en: "English", "zh-Hans": "简体中文", "zh-Hant": "繁體中文" };

export const UI = {
  en: {
    title: "Kids Activities",
    tabs: { discover: "Discover", assistant: "AI Assistant", saved: "Saved", settings: "Settings" },
    search: "Search activities (e.g. robotics, 机器人, 夏令营)", searchButton: "Search",
    filters: "Filters", anyAge: "Any age", age: "Age", ageN: n => `Age ${n}`, anyCity: "Any city", city: "City",
    anyCategory: "All categories", category: "Category", from: "From", to: "To", clear: "Clear filters",
    results: n => `${n} ${n === 1 ? "activity" : "activities"}`, showMore: "Show more",
    loading: "Loading…", none: "No matching activities.", error: "Could not load activities",
    retry: "Try again", notPublished: "Not published", ages: "Ages", dates: "Dates", price: "Price",
    where: "Where", organizer: "Organizer", source: "Official page", original: "Original text",
    save: "Save", saved: "Saved", unsave: "Remove from saved",
    kind: { provider: "From the provider's own page", manual: "Translation (human)",
            machine: "Machine translation", original_only: "Only available in the original language" },
    more: n => `+${n} more`,
    // AI Assistant
    askPlaceholder: "Ask, e.g. Robotics for an 8 year old in San Jose", send: "Send",
    thinking: "Asking the local model…", you: "You", aiAnswer: "AI-generated summary",
    aiNote: model => `Written by the local model${model ? ` (${model})` : ""}; check details on the official pages.`,
    fromTools: "Activities found by the assistant's searches", tools: "Searches the assistant ran",
    noToolsRan: "No search was run.",
    toolNames: { search_activities: "Keyword search", filter_by_age: "Age filter", filter_by_date: "Date filter",
                 get_activity_details: "Activity details", "(skipped)": "Skipped calls" },
    noTools: "The model answered without looking up activities; this answer is not based on the activity data.",
    stopped: "The model reached the step limit before finishing.", aiError: "AI assistant error",
    chatIntro: "Ask in English or Chinese. Answers come from a local AI model on this computer; " +
               "each question is answered on its own.",
    clearChat: "Clear conversation",
    // Saved
    savedEmpty: "No saved activities yet. Tap Save on any activity.",
    savedNote: "Saved in this browser only (not shared with other devices).",
    noLongerListed: "No longer listed or already past; showing what you saved.",
    savedOn: d => `Saved ${d}`,
    // Settings
    preferences: "Preferences", language: "Language", childAge: "Child's age", preferredCity: "Preferred city",
    categories: "Favorite categories", prefsNote: "Used as the default Discover filters. Stored in this browser.",
    status: "Status", refresh: "Refresh", backend: "Backend", data: "Activity data", aiAgent: "AI Assistant",
    ollama: "Ollama (local model)", ok: "Connected", unavailable: "Unavailable", off: "Turned off", notChecked: "Not checked",
    checking: "Checking…", activitiesN: (n, d) => `${n} current activities${d ? `, last checked ${d}` : ""}`,
    privacy: "Privacy", privacyNote: "Saved activities and preferences stay in this browser. " +
             "AI questions are answered by Ollama on the computer running this app.",
    clearSaved: "Clear saved activities",
    confirmClear: n => `Remove all ${n} saved activities from this browser? This cannot be undone.`,
  },
  "zh-Hans": {
    title: "儿童活动",
    tabs: { discover: "发现", assistant: "AI 助手", saved: "收藏", settings: "设置" },
    search: "搜索活动（如：机器人、编程、summer camp）", searchButton: "搜索",
    filters: "筛选", anyAge: "不限年龄", age: "年龄", ageN: n => `${n} 岁`, anyCity: "不限城市", city: "城市",
    anyCategory: "全部类别", category: "类别", from: "从", to: "到", clear: "清除筛选",
    results: n => `${n} 个活动`, showMore: "显示更多",
    loading: "加载中…", none: "没有符合条件的活动。", error: "无法加载活动", retry: "重试",
    notPublished: "未公布", ages: "年龄", dates: "日期", price: "费用", where: "地点", organizer: "主办方",
    source: "官方页面", original: "原文", save: "收藏", saved: "已收藏", unsave: "取消收藏",
    kind: { provider: "来自机构的中文/英文页面", manual: "人工翻译", machine: "机器翻译", original_only: "仅有原文" },
    more: n => `另有 ${n} 场`,
    askPlaceholder: "提问，如：圣何塞 8 岁孩子的机器人课", send: "发送",
    thinking: "正在询问本地模型…", you: "你", aiAnswer: "AI 生成的摘要",
    aiNote: model => `由本地模型${model ? `（${model}）` : ""}生成，请以官方页面为准。`,
    fromTools: "助手搜索到的活动", tools: "助手执行的搜索", noToolsRan: "没有执行搜索。",
    toolNames: { search_activities: "关键词搜索", filter_by_age: "年龄筛选", filter_by_date: "日期筛选",
                 get_activity_details: "活动详情", "(skipped)": "跳过的调用" },
    noTools: "模型没有查询活动数据就作答，此回答并非基于活动数据。",
    stopped: "模型在完成前达到了步骤上限。", aiError: "AI 助手出错",
    chatIntro: "可用中文或英文提问。回答由本机上的本地 AI 模型生成；每个问题单独回答。",
    clearChat: "清空对话",
    savedEmpty: "还没有收藏的活动。在任意活动上点“收藏”。",
    savedNote: "仅保存在本浏览器中（不会同步到其他设备）。",
    noLongerListed: "已不在列表中或已结束；显示收藏时的信息。",
    savedOn: d => `收藏于 ${d}`,
    preferences: "偏好", language: "语言", childAge: "孩子年龄", preferredCity: "常用城市",
    categories: "喜欢的类别", prefsNote: "作为“发现”页的默认筛选，保存在本浏览器中。",
    status: "状态", refresh: "刷新", backend: "后端", data: "活动数据", aiAgent: "AI 助手",
    ollama: "Ollama（本地模型）", ok: "已连接", unavailable: "不可用", off: "已关闭", notChecked: "未检查", checking: "检查中…",
    activitiesN: (n, d) => `当前 ${n} 个活动${d ? `，最近检查 ${d}` : ""}`,
    privacy: "隐私", privacyNote: "收藏和偏好只保存在本浏览器中。AI 问题由运行本应用的电脑上的 Ollama 回答。",
    clearSaved: "清空收藏",
    confirmClear: n => `从此浏览器删除全部 ${n} 个收藏？此操作无法撤销。`,
  },
  "zh-Hant": {
    title: "兒童活動",
    tabs: { discover: "探索", assistant: "AI 助手", saved: "收藏", settings: "設定" },
    search: "搜尋活動（如：機器人、程式設計、summer camp）", searchButton: "搜尋",
    filters: "篩選", anyAge: "不限年齡", age: "年齡", ageN: n => `${n} 歲`, anyCity: "不限城市", city: "城市",
    anyCategory: "全部類別", category: "類別", from: "從", to: "到", clear: "清除篩選",
    results: n => `${n} 個活動`, showMore: "顯示更多",
    loading: "載入中…", none: "沒有符合條件的活動。", error: "無法載入活動", retry: "重試",
    notPublished: "未公布", ages: "年齡", dates: "日期", price: "費用", where: "地點", organizer: "主辦方",
    source: "官方頁面", original: "原文", save: "收藏", saved: "已收藏", unsave: "取消收藏",
    kind: { provider: "來自機構的中文/英文頁面", manual: "人工翻譯", machine: "機器翻譯", original_only: "僅有原文" },
    more: n => `另有 ${n} 場`,
    askPlaceholder: "提問，如：聖荷西 8 歲孩子的機器人課", send: "傳送",
    thinking: "正在詢問本地模型…", you: "你", aiAnswer: "AI 生成的摘要",
    aiNote: model => `由本地模型${model ? `（${model}）` : ""}生成，請以官方頁面為準。`,
    fromTools: "助手搜尋到的活動", tools: "助手執行的搜尋", noToolsRan: "沒有執行搜尋。",
    toolNames: { search_activities: "關鍵字搜尋", filter_by_age: "年齡篩選", filter_by_date: "日期篩選",
                 get_activity_details: "活動詳情", "(skipped)": "略過的呼叫" },
    noTools: "模型沒有查詢活動資料就作答，此回答並非基於活動資料。",
    stopped: "模型在完成前達到了步驟上限。", aiError: "AI 助手出錯",
    chatIntro: "可用中文或英文提問。回答由本機上的本地 AI 模型產生；每個問題單獨回答。",
    clearChat: "清除對話",
    savedEmpty: "還沒有收藏的活動。在任一活動上點「收藏」。",
    savedNote: "僅儲存在本瀏覽器中（不會同步到其他裝置）。",
    noLongerListed: "已不在列表中或已結束；顯示收藏時的資訊。",
    savedOn: d => `收藏於 ${d}`,
    preferences: "偏好", language: "語言", childAge: "孩子年齡", preferredCity: "常用城市",
    categories: "喜歡的類別", prefsNote: "作為「探索」頁的預設篩選，儲存在本瀏覽器中。",
    status: "狀態", refresh: "重新整理", backend: "後端", data: "活動資料", aiAgent: "AI 助手",
    ollama: "Ollama（本地模型）", ok: "已連線", unavailable: "無法使用", off: "已關閉", notChecked: "未檢查", checking: "檢查中…",
    activitiesN: (n, d) => `目前 ${n} 個活動${d ? `，最近檢查 ${d}` : ""}`,
    privacy: "隱私", privacyNote: "收藏和偏好只儲存在本瀏覽器中。AI 問題由執行本應用的電腦上的 Ollama 回答。",
    clearSaved: "清除收藏",
    confirmClear: n => `從此瀏覽器刪除全部 ${n} 個收藏？此操作無法復原。`,
  },
};

// Category names; the keys and English labels come from config/settings.json via GET /options.
export const CATEGORY_ZH = {
  stem: ["数学·科学·编程", "數學·科學·程式"], writing_reading: ["阅读写作", "閱讀寫作"], arts: ["美术手工", "美術手工"],
  music: ["音乐", "音樂"], dance_performing: ["舞蹈表演", "舞蹈表演"], sports: ["运动", "運動"],
  social: ["社交活动", "社交活動"], outdoor: ["户外自然", "戶外自然"], camps: ["夏令营/冬令营", "夏令營/冬令營"],
  language: ["中文/语言", "中文/語言"], after_school: ["课后班", "課後班"], family_events: ["家庭社区活动", "家庭社區活動"],
};

export function categoryLabel(key, info, lang) {
  if (lang === "zh-Hans" && CATEGORY_ZH[key]) return CATEGORY_ZH[key][0];
  if (lang === "zh-Hant" && CATEGORY_ZH[key]) return CATEGORY_ZH[key][1];
  return (info && (info.short || info.label)) || key;
}

export function initialLang(saved) {
  if (saved && UI[saved]) return saved;
  const nav = ((typeof navigator !== "undefined" && navigator.language) || "en").toLowerCase();
  if (nav.startsWith("zh")) return /tw|hk|mo|hant/.test(nav) ? "zh-Hant" : "zh-Hans";
  return "en";
}

import React, { useState } from "react";

// AI Assistant panel: sends a question to POST /agent/chat (local Ollama model with tool calling).
// Activity cards and links come from the tool results in the response, never from the model's text.
const TEXT = {
  en: {
    heading: "AI Assistant (local model)", placeholder: "e.g. Robotics for an 8 year old in San Jose",
    send: "Ask", thinking: "Asking the local model…", tools: "Tools the model used", none: "No tool was used.",
    noActivities: "No matching activities in the tool results.", source: "Official page",
    ages: "Ages", dates: "Dates", price: "Price", notPublished: "Not published",
    noTools: "The model answered without looking up activities; this answer is not based on the activity data.",
    stopped: "The model reached the step limit before finishing.", error: "AI assistant error",
  },
  "zh-Hans": {
    heading: "AI 助手（本地模型）", placeholder: "如：圣何塞 8 岁孩子的机器人课", send: "提问",
    thinking: "正在询问本地模型…", tools: "模型调用的工具", none: "没有调用工具。",
    noActivities: "工具结果中没有符合条件的活动。", source: "官方页面",
    ages: "年龄", dates: "日期", price: "费用", notPublished: "未公布",
    noTools: "模型没有查询活动数据就作答，此回答并非基于活动数据。",
    stopped: "模型在完成前达到了步骤上限。", error: "AI 助手出错",
  },
  "zh-Hant": {
    heading: "AI 助手（本地模型）", placeholder: "如：聖荷西 8 歲孩子的機器人課", send: "提問",
    thinking: "正在詢問本地模型…", tools: "模型呼叫的工具", none: "沒有呼叫工具。",
    noActivities: "工具結果中沒有符合條件的活動。", source: "官方頁面",
    ages: "年齡", dates: "日期", price: "費用", notPublished: "未公布",
    noTools: "模型沒有查詢活動資料就作答，此回答並非基於活動資料。",
    stopped: "模型在完成前達到了步驟上限。", error: "AI 助手出錯",
  },
};

const box = { border: "1px solid #ccc", borderRadius: 6, padding: 12, marginBottom: 20 };

function Assistant({ lang }) {
  const t = TEXT[lang] || TEXT.en;
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);

  const ask = e => {
    e.preventDefault();
    if (!message.trim() || loading) return;
    setLoading(true);
    setResult(null);
    fetch("/agent/chat", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, lang }),
    })
      .then(res => res.json())
      .then(setResult)
      .catch(err => setResult({ agent_status: "error", error: String(err), activities: [], tools_used: [] }))
      .finally(() => setLoading(false));
  };

  const field = value => value || <em>{t.notPublished}</em>;

  return (
    <section style={box}>
      <h2 style={{ fontSize: 18, marginTop: 0 }}>{t.heading}</h2>
      <form onSubmit={ask} style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <input value={message} onChange={e => setMessage(e.target.value)} placeholder={t.placeholder}
               maxLength={500} style={{ flex: "1 1 240px", padding: 8, fontSize: 16 }} />
        <button type="submit" disabled={loading || !message.trim()} style={{ padding: "8px 16px", fontSize: 16 }}>
          {t.send}
        </button>
      </form>
      {loading && <p>{t.thinking}</p>}
      {result && result.error && (
        <p role="alert" style={{ color: "#b00020" }}>
          {t.error} ({result.agent_status}{result.model ? `, ${result.model}` : ""}): {result.error}
        </p>
      )}
      {result && result.agent_status === "no_tools_used" && <p style={{ color: "#8a5a00" }}>{t.noTools}</p>}
      {result && result.agent_status === "max_iterations" && <p style={{ color: "#8a5a00" }}>{t.stopped}</p>}
      {result && result.answer && (
        <div style={{ whiteSpace: "pre-wrap", margin: "12px 0" }}>{result.answer}</div>
      )}
      {result && !result.error && (
        <>
          {(result.activities || []).length === 0 && <p>{t.noActivities}</p>}
          {(result.activities || []).map(c => {
            const shown = c.display || { name: c.title };
            return (
              <div key={c.id} style={{ borderTop: "1px solid #eee", padding: "8px 0", overflowWrap: "anywhere" }}>
                <a href={c.link} target="_blank" rel="noopener noreferrer" lang={shown.language || undefined}>
                  <strong>{shown.name}</strong>
                </a>
                <div style={{ fontSize: 14 }}>
                  {c.provider} · {t.ages}: {field(c.age_text)} · {t.dates}: {field(c.start_date)}
                  {c.end_date && c.end_date !== c.start_date ? ` – ${c.end_date}` : ""} · {t.price}: {field(c.price)}
                  {" · "}<a href={c.link} target="_blank" rel="noopener noreferrer">{t.source}</a>
                </div>
              </div>
            );
          })}
          <details style={{ fontSize: 14, marginTop: 8 }}>
            <summary>{t.tools} ({(result.tools_used || []).length}{result.model ? ` · ${result.model}` : ""})</summary>
            {(result.tools_used || []).length === 0 ? <p>{t.none}</p> : (
              <ol>
                {result.tools_used.map((s, i) => (
                  <li key={i} style={{ color: s.ok ? undefined : "#b00020" }}>
                    <code>{s.tool}({JSON.stringify(s.arguments || {})})</code>
                    {s.ok ? ` → ${s.result_count}` : ` → ${s.error}`}
                    {s.ignored_arguments ? ` (ignored: ${s.ignored_arguments.join(", ")})` : ""}
                  </li>
                ))}
              </ol>
            )}
          </details>
        </>
      )}
    </section>
  );
}

export default Assistant;

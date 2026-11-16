import React from "react";

// AI Assistant result panel for the single search box in App.js: the local model's answer, warnings and
// the real tool trace. Activity cards are rendered by App.js from the tool results, never from model text.
const TEXT = {
  en: {
    heading: "AI Assistant (local model)", thinking: "Asking the local model…", tools: "Tools the model used",
    none: "No tool was used.",
    noTools: "The model answered without looking up activities; this answer is not based on the activity data.",
    stopped: "The model reached the step limit before finishing.", error: "AI assistant error",
    fallback: "AI assistant unavailable, so these are keyword search results",
    cards: "Activities below come from the tool results.",
  },
  "zh-Hans": {
    heading: "AI 助手（本地模型）", thinking: "正在询问本地模型…", tools: "模型调用的工具", none: "没有调用工具。",
    noTools: "模型没有查询活动数据就作答，此回答并非基于活动数据。",
    stopped: "模型在完成前达到了步骤上限。", error: "AI 助手出错",
    fallback: "AI 助手不可用，以下为关键词搜索结果", cards: "下方活动来自工具查询结果。",
  },
  "zh-Hant": {
    heading: "AI 助手（本地模型）", thinking: "正在詢問本地模型…", tools: "模型呼叫的工具", none: "沒有呼叫工具。",
    noTools: "模型沒有查詢活動資料就作答，此回答並非基於活動資料。",
    stopped: "模型在完成前達到了步驟上限。", error: "AI 助手出錯",
    fallback: "AI 助手無法使用，以下為關鍵字搜尋結果", cards: "下方活動來自工具查詢結果。",
  },
};

const box = { border: "1px solid #ccc", borderRadius: 6, padding: 12, marginBottom: 16 };

function Assistant({ lang, result, loading }) {
  const t = TEXT[lang] || TEXT.en;
  if (!loading && !result) return null;
  const detail = result && `${result.agent_status}${result.model ? `, ${result.model}` : ""}`;

  return (
    <section style={box} aria-live="polite">
      <h2 style={{ fontSize: 18, marginTop: 0 }}>{t.heading}</h2>
      {loading && <p>{t.thinking}</p>}
      {result && result.fallback && (
        <p role="alert" style={{ color: "#8a5a00" }}>{t.fallback} ({detail}): {result.error}</p>
      )}
      {result && !result.fallback && result.error && (
        <p role="alert" style={{ color: "#b00020" }}>{t.error} ({detail}): {result.error}</p>
      )}
      {result && result.agent_status === "no_tools_used" && <p style={{ color: "#8a5a00" }}>{t.noTools}</p>}
      {result && result.agent_status === "max_iterations" && <p style={{ color: "#8a5a00" }}>{t.stopped}</p>}
      {result && result.answer && <div style={{ whiteSpace: "pre-wrap", margin: "12px 0" }}>{result.answer}</div>}
      {result && !result.fallback && !result.error && (
        <>
          <p style={{ fontSize: 14, color: "#555" }}>{t.cards}</p>
          <details style={{ fontSize: 14 }}>
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

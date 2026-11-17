import React, { useEffect, useRef, useState } from "react";
import ActivityCard from "./ActivityCard";

// Chat with the existing AI Agent (POST /agent/chat, local Ollama model with tool calling).
// The model's text is labelled as an AI-generated summary; activity cards come from the tool results.
// The agent answers each question on its own; the conversation shown here is kept only while the page is open.
// The model writes light Markdown. Render only **bold** and [text](http(s) link) as React elements (never as
// HTML); everything else stays plain text. Links were already limited by the backend to URLs in the activity data.
const INLINE_RE = /\*\*(.+?)\*\*|\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g;

export function renderAnswer(text) {
  const out = [];
  let last = 0;
  let m;
  INLINE_RE.lastIndex = 0;
  while ((m = INLINE_RE.exec(text)) !== null) {
    if (m.index > last) out.push(text.slice(last, m.index));
    out.push(m[1] !== undefined
      ? <strong key={m.index}>{m[1]}</strong>
      : <a key={m.index} href={m[3]} target="_blank" rel="noopener noreferrer">{m[2]}</a>);
    last = INLINE_RE.lastIndex;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

function Trace({ result, t }) {
  const steps = result.tools_used || [];
  return (
    <details className="trace">
      <summary>{t.tools} ({steps.length}{result.model ? ` · ${result.model}` : ""})</summary>
      {steps.length === 0 ? <p>{t.noToolsRan}</p> : (
        <ol>
          {steps.map((s, i) => (
            <li key={i} className={s.ok ? "" : "bad"}>
              {t.toolNames[s.tool] || s.tool} <code>{JSON.stringify(s.arguments || {})}</code>
              {s.ok ? ` → ${s.result_count}` : ` → ${s.error}`}
              {s.ignored_arguments ? ` (ignored: ${s.ignored_arguments.join(", ")})` : ""}
            </li>
          ))}
        </ol>
      )}
    </details>
  );
}

function AssistantMessage({ result, t, savedIds, onToggleSave }) {
  const failed = !!result.error;
  return (
    <div className="msg ai">
      {failed && <div className="banner error" role="alert">{t.aiError} ({result.agent_status}): {result.error}</div>}
      {result.agent_status === "no_tools_used" && <div className="banner warn">{t.noTools}</div>}
      {result.agent_status === "max_iterations" && <div className="banner warn">{t.stopped}</div>}
      {result.answer && (
        <div className="bubble">
          <div className="label">{t.aiAnswer}</div>
          <div className="answer">{renderAnswer(result.answer)}</div>
          <div className="label small">{t.aiNote(result.model)}</div>
        </div>
      )}
      {!failed && (result.activities || []).length > 0 && (
        <>
          <div className="label">{t.fromTools}</div>
          <div className="cards">
            {result.activities.map(c => (
              <ActivityCard key={c.id} c={c} t={t} saved={savedIds.has(c.id)} onToggleSave={onToggleSave} />
            ))}
          </div>
        </>
      )}
      {!failed && <Trace result={result} t={t} />}
    </div>
  );
}

function Assistant({ lang, t, messages, setMessages, savedIds, onToggleSave }) {
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const end = useRef(null);

  useEffect(() => {
    if (end.current && end.current.scrollIntoView) end.current.scrollIntoView({ block: "end" });
  }, [messages, loading]);

  const send = e => {
    e.preventDefault();
    const message = text.trim();
    if (!message || loading) return;
    setText("");
    setLoading(true);
    setMessages(m => [...m, { role: "user", text: message }]);
    fetch("/agent/chat", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, lang }),
    })
      .then(res => res.json())
      .catch(err => ({ agent_status: "error", error: String(err), activities: [], tools_used: [] }))
      .then(result => setMessages(m => [...m, { role: "assistant", result }]))
      .finally(() => setLoading(false));
  };

  return (
    <section className="chat" aria-labelledby="assistant-title">
      <h2 id="assistant-title" className="visually-hidden">{t.tabs.assistant}</h2>
      <p className="hint">{t.chatIntro}</p>
      <div className="messages" aria-live="polite">
        {messages.map((m, i) => m.role === "user"
          ? <div key={i} className="msg user"><div className="bubble"><span className="visually-hidden">{t.you}: </span>{m.text}</div></div>
          : <AssistantMessage key={i} result={m.result} t={t} savedIds={savedIds} onToggleSave={onToggleSave} />)}
        {loading && <p className="status">{t.thinking}</p>}
        <div ref={end} />
      </div>
      {messages.length > 0 && !loading && (
        <button type="button" className="link-button" onClick={() => setMessages([])}>{t.clearChat}</button>
      )}
      <form className="composer" onSubmit={send}>
        <input value={text} onChange={e => setText(e.target.value)} placeholder={t.askPlaceholder}
               aria-label={t.askPlaceholder} enterKeyHint="send" autoComplete="off" maxLength={500} />
        <button type="submit" className="primary" disabled={loading || !text.trim()}>{t.send}</button>
      </form>
    </section>
  );
}

export default Assistant;

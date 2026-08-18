"use client";

export function AnswerPanel({ answer, streaming, busy }: { answer: string; streaming: boolean; busy: boolean }) {
  const placeholder = busy
    ? "Waiting for generated response…"
    : "Ask a question to see the answer here.";
  return (
    <section className="card" style={{ marginTop: 16 }}>
      <h2>Answer {streaming ? <span className="badge">streaming</span> : null}</h2>
      <div className="answer">{answer || <span style={{ opacity: 0.5 }}>{placeholder}</span>}</div>
    </section>
  );
}

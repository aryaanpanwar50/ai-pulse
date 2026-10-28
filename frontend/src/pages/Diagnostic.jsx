import React, { useEffect, useState } from "react";
import { api } from "../api.js";

export default function Diagnostic({ onDone }) {
  const [questions, setQuestions] = useState([]);
  const [answers, setAnswers] = useState({});
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api("/diagnostic/questions")
      .then(setQuestions)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  async function submit() {
    setSubmitting(true);
    setError("");
    const payload = Object.entries(answers).map(([question_id, answer]) => ({ question_id, answer }));
    try {
      await api("/diagnostic/submit", { method: "POST", body: JSON.stringify({ answers: payload }) });
      onDone();
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  const complete = questions.length > 0 && questions.every((q) => answers[q.id]?.trim());
  if (loading) return <p>Loading diagnostic questions…</p>;
  if (error && questions.length === 0) return <p className="error">{error}</p>;

  return (
    <div className="card">
      <h2>Your AI diagnostic</h2>
      {error && <p className="error">{error}</p>}
      {questions.map((q) => (
        <div key={q.id}>
          <p><b>{q.text}</b></p>
          {q.type === "mcq" ? (
            <select
              value={answers[q.id] || ""}
              onChange={(e) => setAnswers({ ...answers, [q.id]: e.target.value })}
            >
              <option value="" disabled>Choose…</option>
              {q.options.map((option) => <option key={option}>{option}</option>)}
            </select>
          ) : (
            <textarea
              rows={4}
              value={answers[q.id] || ""}
              onChange={(e) => setAnswers({ ...answers, [q.id]: e.target.value })}
            />
          )}
        </div>
      ))}
      <button onClick={submit} disabled={!complete || submitting}>
        {submitting ? "Submitting…" : "Submit diagnostic"}
      </button>
    </div>
  );
}

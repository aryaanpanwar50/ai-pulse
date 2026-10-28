import React, { useEffect, useState } from "react";
import { api } from "../api.js";

export default function Report({ onBack, onDeleted }) {
  const [report, setReport] = useState(null);
  const [error, setError] = useState("");
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    let active = true;
    api("/reports/me")
      .then((data) => { if (active) setReport(data); })
      .catch((err) => { if (active) setError(err.message); });
    return () => { active = false; };
  }, []);

  async function deleteResponse() {
    const confirmed = window.confirm(
      `Delete your diagnostic response and report for ${report.organization}? You can submit a new response afterward.`
    );
    if (!confirmed) return;

    setDeleting(true);
    setError("");
    try {
      await api("/diagnostic/me", { method: "DELETE" });
      onDeleted();
    } catch (err) {
      setError(err.message);
      setDeleting(false);
    }
  }

  if (error && !report) return <p className="error">{error}</p>;
  if (!report) return <p>Loading your report…</p>;

  return (
    <div className="card">
      <h2>{report.name}: {report.level}</h2>
      <p>Organization: {report.organization}</p>
      <p>Average score: {report.average_score ?? "Not assessed"}</p>
      <h3>Risks</h3>
      {report.risks.length ? <ul>{report.risks.map((risk) => <li key={risk}>{risk}</li>)}</ul> : <p>No risks identified.</p>}
      <h3>Personalized guidance</h3>
      {report.feedback ? (
        <>
          <p>{report.feedback.replace(/\s*\u2014\s*/g, ", ")}</p>
          <h3>Next steps</h3>
          <ul>{report.next_steps.map((step) => <li key={step}>{step.replace(/\s*\u2014\s*/g, ", ")}</li>)}</ul>
        </>
      ) : (
        <p>Personalized guidance is unavailable for this submission. Your score and risks are still available.</p>
      )}
      {error && <p className="error">{error}</p>}
      <div className="actions">
        <button onClick={onBack} disabled={deleting}>Back</button>
        <button className="danger" onClick={deleteResponse} disabled={deleting}>
          {deleting ? "Deleting…" : "Delete this response"}
        </button>
      </div>
    </div>
  );
}

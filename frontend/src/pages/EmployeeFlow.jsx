import React, { useEffect, useState } from "react";
import { api } from "../api.js";
import Diagnostic from "./Diagnostic.jsx";

export default function EmployeeFlow({ onViewReport }) {
  const [status, setStatus] = useState(null);
  const [error, setError] = useState("");
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    let active = true;
    setStatus(null);
    setError("");
    api("/diagnostic/me")
      .then((data) => { if (active) setStatus(data); })
      .catch((err) => { if (active) setError(err.message); });
    return () => { active = false; };
  }, [refresh]);

  if (error) {
    return (
      <div className="card">
        <p className="error">{error}</p>
        <button onClick={() => setRefresh((value) => value + 1)}>Try again</button>
      </div>
    );
  }
  if (!status) return <p>Checking your submission…</p>;

  if (!status.submitted) {
    return <Diagnostic onDone={() => setRefresh((value) => value + 1)} />;
  }

  return (
    <div className="card">
      <h2>Response submitted</h2>
      <p>Your diagnostic for this organization has been submitted.</p>
      {status.submitted_at && <p><small>Submitted {new Date(status.submitted_at).toLocaleString()}</small></p>}
      <button onClick={onViewReport}>View report</button>
    </div>
  );
}

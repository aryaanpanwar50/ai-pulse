import React, { useEffect, useState } from "react";
import { api } from "../api.js";

function formatScore(score) {
  if (score === null || score === undefined) return "—";
  return Number.isInteger(score) ? String(score) : score.toFixed(2);
}

function formatRisk(flag) {
  return flag
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

export default function Dashboard({ org }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function loadDashboard() {
      setLoading(true);
      setError("");
      try {
        const result = await api(`/dashboard?org_id=${org.org_id}`);
        if (!cancelled) setData(result);
      } catch (err) {
        if (!cancelled) setError(err.message || "Could not load the dashboard.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    loadDashboard();
    return () => { cancelled = true; };
  }, [org.org_id]);

  if (loading) {
    return <section className="card dashboard-card" aria-live="polite">Loading dashboard…</section>;
  }

  if (error) {
    return (
      <section className="card dashboard-card" role="alert">
        <h2>Dashboard unavailable</h2>
        <p className="error">{error}</p>
      </section>
    );
  }

  return (
    <section className="card dashboard-card">
      <header className="dashboard-header">
        <div>
          <p className="dashboard-eyebrow">Leadership dashboard</p>
          <h2>{data.organization}</h2>
        </div>
        <span className="dashboard-department-count">
          {data.departments.length} departments
        </span>
      </header>

      <h3>Department overview</h3>
      <div className="dashboard-table-wrap">
        <table className="dashboard-table">
          <thead>
            <tr>
              <th scope="col">Department</th>
              <th scope="col">Employees</th>
              <th scope="col">Responded</th>
              <th scope="col">Average score</th>
              <th scope="col">Level</th>
            </tr>
          </thead>
          <tbody>
            {data.departments.map((department) => (
              <tr key={department.department}>
                <th scope="row">{department.department}</th>
                <td>{department.employees}</td>
                <td>{department.responded}</td>
                <td>{formatScore(department.average_score)}</td>
                <td>{department.level}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <section className="dashboard-risks" aria-labelledby="dashboard-risks-title">
        <h3 id="dashboard-risks-title">Top risks</h3>
        {data.top_risks.length === 0 ? (
          <p className="dashboard-empty">No reported risks.</p>
        ) : (
          <ul className="dashboard-risk-list">
            {data.top_risks.map(([flag, count]) => (
              <li key={flag}>
                <span>{formatRisk(flag)}</span>
                <span className="dashboard-risk-count">{count}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </section>
  );
}

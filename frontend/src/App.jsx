import React, { useState } from "react";
import Login from "./pages/Login.jsx";
import OrgPicker from "./pages/OrgPicker.jsx";
import Diagnostic from "./pages/Diagnostic.jsx";
import EmployeeFlow from "./pages/EmployeeFlow.jsx";
import Report from "./pages/Report.jsx";
import Dashboard from "./pages/Dashboard.jsx";

export default function App() {
  const [step, setStep] = useState("login");
  const [session, setSession] = useState(null);
  const [org, setOrg] = useState(null);

  return (
    <div className="wrap">
      <h1>AI Pulse</h1>
      {step === "login" && (
        <Login onDone={(s) => { setSession(s); setStep("org"); }} />
      )}
      {step === "org" && (
        <OrgPicker
          orgs={session.organizations}
          onPick={(o) => { setOrg(o); setStep(o.role === "admin" ? "dashboard" : "employee"); }}
        />
      )}
      {step === "employee" && <EmployeeFlow onViewReport={() => setStep("report")} />}
      {step === "report" && (
        <Report onBack={() => setStep("employee")} onDeleted={() => setStep("employee")} />
      )}
      {step === "dashboard" && <Dashboard org={org} />}
    </div>
  );
}

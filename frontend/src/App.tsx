import { useState } from "react";
import Dashboard from "./components/Dashboard";
import GateView from "./components/GateView";
import KnowledgeMap from "./components/KnowledgeMap";
import NudgeBell from "./components/NudgeBell";
import Settings from "./components/Settings";
import StudyView from "./components/StudyView";
import "./App.css";

type Tab = "study" | "dashboard" | "map" | "settings";

/** The desktop gate loads the same bundle with ?gate=1 — study only, no navigation. */
const GATE_MODE = new URLSearchParams(window.location.search).get("gate") === "1";

export default function App() {
  if (GATE_MODE) return <GateView />;
  return <FullApp />;
}

function FullApp() {
  const [tab, setTab] = useState<Tab>("study");
  const [studyScope, setStudyScope] = useState("global");
  const tabs: [Tab, string][] = [
    ["study", "Study"],
    ["dashboard", "Dashboard"],
    ["map", "Knowledge Map"],
    ["settings", "⚙"],
  ];

  const study = (scope: string) => {
    setStudyScope(scope);
    setTab("study");
  };

  return (
    <div className="app">
      <header className="app-header">
        <span className="app-title">StudyEngine</span>
        <nav className="app-nav">
          {tabs.map(([key, label]) => (
            <button
              key={key}
              className={tab === key ? "nav-btn active" : "nav-btn"}
              onClick={() => setTab(key)}
            >
              {label}
            </button>
          ))}
        </nav>
        <div className="app-spacer" />
        <NudgeBell />
      </header>
      <main className="app-main">
        {tab === "study" && <StudyView key={studyScope} initialScope={studyScope} />}
        {tab === "dashboard" && <Dashboard onStudy={study} />}
        {tab === "map" && <KnowledgeMap onStudy={study} />}
        {tab === "settings" && <Settings />}
      </main>
    </div>
  );
}

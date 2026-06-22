import { useState } from "react";
import Dashboard from "./components/Dashboard";
import KnowledgeMap from "./components/KnowledgeMap";
import StudyView from "./components/StudyView";
import "./App.css";

type Tab = "study" | "dashboard" | "map";

export default function App() {
  const [tab, setTab] = useState<Tab>("study");
  const tabs: [Tab, string][] = [
    ["study", "Study"],
    ["dashboard", "Dashboard"],
    ["map", "Knowledge Map"],
  ];

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
      </header>
      <main className="app-main">
        {tab === "study" && <StudyView />}
        {tab === "dashboard" && <Dashboard />}
        {tab === "map" && <KnowledgeMap />}
      </main>
    </div>
  );
}

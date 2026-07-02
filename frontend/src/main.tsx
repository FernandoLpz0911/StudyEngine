import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import { initTheme } from "./themes";
import "./index.css";

initTheme();

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);

// PWA shell: production only, so Vite dev reloads aren't fought by the cache.
if ("serviceWorker" in navigator && import.meta.env.PROD) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch(() => {});
  });
}

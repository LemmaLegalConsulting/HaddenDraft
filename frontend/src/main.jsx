import React from "react";
import { createRoot } from "react-dom/client";

import { App } from "./App.jsx";
import { API_BASE } from "./api/client.js";
import { clearStaleCsrfCookie } from "./api/csrf.js";
import "./styles/bootstrap-bux.scss";
import "./styles/app.css";
import "./styles/bux.css";
import "./styles/bux-component-theme.css";

// Before anything reads a CSRF token: a browser that used this site when the
// API was served from this same host is holding a stale cookie that shadows the
// real one and turns every write into a 403.
clearStaleCsrfCookie({ apiBase: API_BASE, pageOrigin: window.location.origin });

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);

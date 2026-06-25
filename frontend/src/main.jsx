import React from "react";
import { createRoot } from "react-dom/client";

import { App } from "./App.jsx";
import "./styles/app.css";
import "./styles/bux.css";

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);

import React, { useState } from "react";
import { Upload } from "lucide-react";

import { api } from "../api/client.js";

export function TemplateBuilder({ onCreated }) {
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState("Example Motion Template");
  const [jurisdiction, setJurisdiction] = useState("");
  const [exampleText, setExampleText] = useState("Caption\n\nFacts\n\nArgument\n\nPrayer for Relief\n\nSignature");

  async function createTemplate() {
    const response = await api.createTemplateFromExample({ title, jurisdiction, exampleText });
    onCreated(response.template);
    setOpen(false);
  }

  return (
    <section className="panel">
      <div className="button-row panel-actions">
        <button className="secondary" onClick={() => setOpen((value) => !value)}>
          <Upload size={16} /> {open ? "Close" : "Open"}
        </button>
      </div>
      {open && (
        <div className="template-builder">
          <label className="field">
            <span>Template title</span>
            <input value={title} onChange={(event) => setTitle(event.target.value)} />
          </label>
          <label className="field">
            <span>Jurisdiction</span>
            <input value={jurisdiction} onChange={(event) => setJurisdiction(event.target.value)} />
          </label>
          <label className="field">
            <span>Example text</span>
            <textarea value={exampleText} onChange={(event) => setExampleText(event.target.value)} />
          </label>
          <button className="primary" onClick={createTemplate}>Create template</button>
        </div>
      )}
    </section>
  );
}

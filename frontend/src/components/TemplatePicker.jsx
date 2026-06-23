import React from "react";

export function TemplatePicker({ templates, selectedTemplateId, selectedBlockKeys, onTemplateChange, onBlockChange }) {
  const selectedTemplate = templates.find((template) => template.id === Number(selectedTemplateId));

  function toggleBlock(key) {
    if (selectedBlockKeys.includes(key)) {
      onBlockChange(selectedBlockKeys.filter((item) => item !== key));
    } else {
      onBlockChange([...selectedBlockKeys, key]);
    }
  }

  return (
    <div className="template-picker">
      <label className="field">
        <span>Document template</span>
        <select value={selectedTemplateId || ""} onChange={(event) => onTemplateChange(event.target.value)}>
          {templates.map((template) => (
            <option key={template.id} value={template.id}>{template.title} · {template.jurisdiction || "Any jurisdiction"}</option>
          ))}
        </select>
      </label>

      <div className="block-list">
        {selectedTemplate?.blocks?.map((block) => (
          <label key={block.key} className={`block-row ${block.required ? "required" : ""}`}>
            <input
              type="checkbox"
              checked={selectedBlockKeys.includes(block.key)}
              disabled={block.required}
              onChange={() => toggleBlock(block.key)}
            />
            <span>
              <strong>{block.label}</strong>
              <em>{block.required ? "Required" : "Optional"} · {block.aiFillMode.replaceAll("_", " ")}</em>
            </span>
          </label>
        ))}
      </div>
    </div>
  );
}

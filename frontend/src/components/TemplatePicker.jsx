import React from "react";

function fieldLabel(path) {
  return path.replace(/^fields\./, "").replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function TemplatePicker({
  templates,
  selectedTemplateId,
  selectedBlockKeys,
  templateData,
  onTemplateChange,
  onBlockChange,
  onTemplateDataChange,
}) {
  const selectedTemplate = templates.find((template) => template.id === Number(selectedTemplateId));
  const templateFields = selectedTemplate?.metadata?.fields || [];

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

      {templateFields.length > 0 && (
        <div className="template-field-list">
          <h4>Template details</h4>
          {templateFields.map((path) => {
            const key = path.replace(/^fields\./, "");
            return (
              <label className="field" key={path}>
                <span>{fieldLabel(path)}</span>
                <input
                  value={templateData?.[key] || ""}
                  onChange={(event) => onTemplateDataChange({ ...templateData, [key]: event.target.value })}
                />
              </label>
            );
          })}
        </div>
      )}

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

import React from "react";

export function FactReview({ facts, selectedFactIds, onChange }) {
  function toggle(id) {
    if (selectedFactIds.includes(id)) {
      onChange(selectedFactIds.filter((factId) => factId !== id));
    } else {
      onChange([...selectedFactIds, id]);
    }
  }

  return (
    <div className="panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Facts</p>
          <h3>Candidate facts</h3>
        </div>
      </div>
      <div className="check-list">
        {facts.map((fact) => (
          <label key={fact.id} className="check-row">
            <input type="checkbox" checked={selectedFactIds.includes(fact.id)} onChange={() => toggle(fact.id)} />
            <span>
              <strong>{fact.title}</strong>
              <em>{fact.text}</em>
              <small>{fact.source} · {fact.confidence}</small>
            </span>
          </label>
        ))}
      </div>
    </div>
  );
}

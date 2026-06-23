import React from "react";
import { Check } from "lucide-react";

export function WorkflowStepper({ steps, activeStep, onSelect }) {
  const activeIndex = Math.max(0, steps.findIndex((step) => step.id === activeStep));
  return (
    <div className="stepper">
      <p className="stepper-title">Workflow</p>
      {steps.map((step, index) => (
        <button
          key={step.id}
          className={`step ${index === activeIndex ? "active" : ""} ${index < activeIndex ? "done" : ""}`}
          onClick={() => onSelect?.(step.id)}
          type="button"
        >
          <div className="step-index">{index < activeIndex ? <Check size={13} /> : index + 1}</div>
          <div>
            <strong>{step.label}</strong>
          </div>
        </button>
      ))}
    </div>
  );
}

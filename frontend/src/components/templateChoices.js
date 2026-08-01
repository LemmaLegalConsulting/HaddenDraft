// Shared option model for the template <select> controls.
//
// The controls are React-controlled with an empty string for "nothing chosen".
// Without an option carrying that value the browser falls back to displaying
// option[0] while state stays empty, so choosing the first template fires no
// change event and the step cannot be completed.

export const TEMPLATE_PLACEHOLDER_VALUE = "";
export const TEMPLATE_PLACEHOLDER_LABEL = "Choose a template…";

export function templateChoices(templates, { excludeShells = false } = {}) {
  const usable = (templates || []).filter(
    (template) => template && (!excludeShells || template.kind !== "shell"),
  );
  return [
    { value: TEMPLATE_PLACEHOLDER_VALUE, label: TEMPLATE_PLACEHOLDER_LABEL, placeholder: true },
    ...usable.map((template) => ({
      value: String(template.id),
      label: template.title,
      jurisdiction: template.jurisdiction || "",
      placeholder: false,
    })),
  ];
}

export function isTemplateChosen(selectedTemplateId) {
  return String(selectedTemplateId ?? "") !== TEMPLATE_PLACEHOLDER_VALUE;
}

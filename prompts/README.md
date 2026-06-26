# Prompt Catalog

Runtime prompt defaults live in this directory. There is exactly one `*.yaml` or `*.yml` file per prompt. Files are loaded on demand, so prompt edits are picked up without an application restart and each prompt can be benchmarked or versioned independently.

Each file uses this schema:

`namespace.prompt_name.yaml` becomes the prompt key `namespace.prompt_name`. Its contents use this schema:

```yaml
system prompt: |
  System message, with optional {named_placeholders}.
user prompt: |
  User message, with the same placeholder convention.
settings:
  default model: gpt-5.4-mini
  default reasoning level: low
```

`system prompt`, `user prompt`, `settings.default model`, and `settings.default reasoning level` are all required strings. The model and reasoning-level defaults are sent with each LLM request. Prompt keys (derived from filenames) must be unique across the directory. Placeholders use Python's simple `{name}` syntax; only named fields are allowed. The application fails clearly if a required value is not supplied, rather than sending a partial prompt.

The default directory is `prompts/` at the repository root. Set `PROMPT_CATALOG_DIR` to point to another directory for an experiment or benchmark run. This makes it possible to run a complete prompt variant set without changing application code.

File prompts are the source of truth. Django admin also exposes **Prompt overrides**: an enabled row with the same key replaces the file version and its model/reasoning defaults at runtime. Disable or delete that row to restore the file-backed default. Store benchmark variants in YAML rather than database overrides so they remain reviewable and reproducible.

import React, { useMemo, useState } from "react";
import { $createParagraphNode, $createTextNode, $getRoot, FORMAT_TEXT_COMMAND } from "lexical";
import { Bold, ExternalLink, Italic, MoreVertical, Plus, Save, Sparkles, Underline, X } from "lucide-react";
import { LexicalComposer } from "@lexical/react/LexicalComposer";
import { ContentEditable } from "@lexical/react/LexicalContentEditable";
import { LexicalErrorBoundary } from "@lexical/react/LexicalErrorBoundary";
import { HistoryPlugin } from "@lexical/react/LexicalHistoryPlugin";
import { OnChangePlugin } from "@lexical/react/LexicalOnChangePlugin";
import { RichTextPlugin } from "@lexical/react/LexicalRichTextPlugin";
import { useLexicalComposerContext } from "@lexical/react/LexicalComposerContext";

function cleanBody(body = "") {
  return body.replace(/<br\s*\/?>/gi, "\n");
}

function loadPlainText(body) {
  return () => {
    const root = $getRoot();
    root.clear();
    const paragraphs = cleanBody(body).split(/\n{2,}|\n/).filter(Boolean);
    (paragraphs.length ? paragraphs : [""]).forEach((paragraphText) => {
      const paragraph = $createParagraphNode();
      paragraph.append($createTextNode(paragraphText));
      root.append(paragraph);
    });
  };
}

function BlockToolbar() {
  const [editor] = useLexicalComposerContext();
  return (
    <div className="block-toolbar" aria-label="Formatting">
      {[
        ["bold", Bold, "Bold"],
        ["italic", Italic, "Italic"],
        ["underline", Underline, "Underline"],
      ].map(([format, Icon, label]) => (
        <button
          className="icon-button secondary"
          key={format}
          title={label}
          type="button"
          onClick={() => editor.dispatchCommand(FORMAT_TEXT_COMMAND, format)}
        >
          <Icon size={15} />
        </button>
      ))}
    </div>
  );
}

function citationLabel(source) {
  if (!source) return "";
  if (typeof source === "string") return source;
  return source.citation || source.title || source.sourceLabel || source.source || "";
}

function sourcePreview(source) {
  if (!source || typeof source === "string") return { label: source || "", snippet: "", url: "" };
  return {
    label: citationLabel(source),
    title: source.title || citationLabel(source),
    snippet: source.snippet || source.sourceExcerpt || source.metadata?.snippet || "",
    url: source.url || "",
    sourceLabel: source.sourceLabel || source.source || "",
  };
}

function supportMap(block) {
  const map = new Map();
  (block.sources || []).forEach((source) => {
    const preview = sourcePreview(source);
    if (preview.label) map.set(preview.label, preview);
  });
  return map;
}

function supportingReasons(block) {
  const map = supportMap(block);
  const lines = cleanBody(block.body).split(/\n+/).map((line) => line.trim()).filter(Boolean);
  const citedLines = lines.flatMap((line) => {
    const citations = [...line.matchAll(/\[([^\]]+)\]/g)].map((match) => match[1]);
    if (!citations.length) return [];
    return [{
      reason: line.replace(/\s*\[[^\]]+\]/g, "").replace(/^\d+\.\s*/, ""),
      citations: citations.map((citation) => map.get(citation) || { label: citation, title: citation, snippet: "", url: "" }),
    }];
  });
  if (citedLines.length) return citedLines;
  return [...map.values()].map((preview) => ({ reason: "Block support", citations: [preview] }));
}

function plainTextFromSections(sections) {
  return sections.map((section) => `${section.label.toUpperCase()}\n${cleanBody(section.body || "")}`).join("\n\n");
}

function sectionsFromDraft(draft) {
  if (draft?.sections?.length) return draft.sections.map((section) => ({ ...section, body: cleanBody(section.body) }));
  if (!draft?.plainText) return [];
  return draft.plainText.split(/\n{2,}/).map((body, index) => ({
    key: `block-${index + 1}`,
    label: `Block ${index + 1}`,
    body: cleanBody(body),
    sources: [],
    origin: "template",
    format: { style: "plain", headingNumbering: "none" },
  }));
}

function nextFormat(section, patch) {
  return { ...(section.format || { style: "plain", headingNumbering: "none" }), ...patch };
}

function newBlockKey() {
  if (globalThis.crypto?.randomUUID) return `custom-${globalThis.crypto.randomUUID()}`;
  return `custom-${Date.now()}`;
}

function DraftBlock({ block, blockState, disabled, onBlockChange, onFormatChange, onOpenRefine, onPreviewCitation }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const format = block.format || {};
  const initialConfig = useMemo(() => ({
    namespace: `DraftBlock-${block.key}`,
    editorState: blockState ? JSON.stringify(blockState) : loadPlainText(block.body || ""),
    theme: {
      paragraph: "editor-paragraph",
      text: {
        bold: "editor-text-bold",
        italic: "editor-text-italic",
        underline: "editor-text-underline",
      },
    },
    onError(error) {
      throw error;
    },
  }), [block.body, block.key, blockState]);

  const reasons = supportingReasons(block);
  const className = [
    "draft-block",
    format.style === "numbered" ? "numbered-block" : "",
    format.headingNumbering === "roman" ? "roman-heading-block" : "",
    format.restartNumbering ? "restart-numbering" : "",
  ].filter(Boolean).join(" ");

  return (
    <section className={className}>
      <div className="draft-block-header">
        <h4>{block.label}</h4>
        <div className="block-header-actions">
          {(block.origin === "ai" || block.aiFillMode === "constrained_generation") && (
            <span className="ai-badge" title="AI-generated"><Sparkles size={13} /> AI</span>
          )}
          <button className="icon-button secondary" title="Actions" type="button" onClick={() => setMenuOpen((value) => !value)}>
            <MoreVertical size={16} />
          </button>
          {menuOpen && (
            <div className="block-menu">
              <button type="button" onClick={() => { setMenuOpen(false); onOpenRefine(block); }}>Refine with AI</button>
              <button type="button" onClick={() => onFormatChange(block.key, nextFormat(block, { style: format.style === "numbered" ? "plain" : "numbered" }))}>
                {format.style === "numbered" ? "Use plain paragraphs" : "Number paragraphs"}
              </button>
              <button type="button" onClick={() => onFormatChange(block.key, nextFormat(block, { restartNumbering: !format.restartNumbering, style: "numbered" }))}>
                {format.restartNumbering ? "Continue numbering" : "Restart numbering here"}
              </button>
              <button type="button" onClick={() => onFormatChange(block.key, nextFormat(block, { headingNumbering: format.headingNumbering === "roman" ? "none" : "roman" }))}>
                {format.headingNumbering === "roman" ? "Remove roman heading" : "Roman heading"}
              </button>
            </div>
          )}
        </div>
      </div>

      <LexicalComposer initialConfig={initialConfig}>
        <BlockToolbar />
        <div className="block-editor-shell">
          <RichTextPlugin
            contentEditable={<ContentEditable className="block-editor-input" />}
            placeholder={<div className="block-editor-placeholder">Start this section...</div>}
            ErrorBoundary={LexicalErrorBoundary}
          />
        </div>
        <HistoryPlugin />
        <OnChangePlugin
          onChange={(editorState) => {
            editorState.read(() => {
              onBlockChange(block.key, cleanBody($getRoot().getTextContent()), editorState.toJSON());
            });
          }}
        />
      </LexicalComposer>

      {reasons.length > 0 && (
        <div className="reason-support-list">
          {reasons.map((item, index) => (
            <div className="reason-support" key={`${item.reason}-${index}`}>
              <span>{item.reason}</span>
              <div className="citation-list">
                {item.citations.map((citation) => (
                  <button
                    className="citation-chip"
                    key={citation.label}
                    type="button"
                    onClick={() => onPreviewCitation(citation)}
                  >
                    {citation.label}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function RefineModal({ block, disabled, onClose, onSubmit }) {
  const [instruction, setInstruction] = useState("");
  if (!block) return null;
  return (
    <div className="modal-backdrop" role="presentation">
      <div className="editor-modal" role="dialog" aria-modal="true" aria-label="Refine section">
        <div className="modal-heading">
          <h4>Refine {block.label}</h4>
          <button className="icon-button secondary" type="button" onClick={onClose} title="Close"><X size={16} /></button>
        </div>
        <textarea
          value={instruction}
          onChange={(event) => setInstruction(event.target.value)}
          placeholder="Example: Make this more concise and focus on the pending rental assistance application."
        />
        <div className="button-row step-actions">
          <button className="secondary" type="button" onClick={onClose}>Cancel</button>
          <button className="primary" disabled={disabled} type="button" onClick={() => onSubmit(block.key, instruction)}>
            <Sparkles size={16} /> Refine
          </button>
        </div>
      </div>
    </div>
  );
}

function CitationPreview({ citation, onClose }) {
  if (!citation) return null;
  return (
    <aside className="citation-preview" aria-label="Citation preview">
      <div className="modal-heading">
        <div>
          <span className="block-kicker">{citation.sourceLabel || "Support"}</span>
          <h4>{citation.title || citation.label}</h4>
        </div>
        <button className="icon-button secondary" type="button" onClick={onClose} title="Close"><X size={16} /></button>
      </div>
      <p>{citation.snippet || "No preview text is available for this citation yet."}</p>
      {citation.url && (
        <a className="secondary link-button" href={citation.url} target="_blank" rel="noreferrer">
          <ExternalLink size={16} /> Open source
        </a>
      )}
    </aside>
  );
}

export function DraftEditor({ draft, busy, onChange, onPersist, onRegenerateBlock }) {
  const sections = sectionsFromDraft(draft);
  const blockStates = draft?.editorState?.blocks || {};
  const [refineBlock, setRefineBlock] = useState(null);
  const [citationPreview, setCitationPreview] = useState(null);

  function updateSections(nextSections, nextBlockStates = blockStates) {
    onChange(nextSections, plainTextFromSections(nextSections), {
      format: "lexical_blocks",
      blocks: nextBlockStates,
    });
  }

  function handleBlockChange(blockKey, body, editorState) {
    const nextSections = sections.map((section) => (
      section.key === blockKey ? { ...section, body: cleanBody(body) } : section
    ));
    updateSections(nextSections, { ...blockStates, [blockKey]: editorState });
  }

  function handleFormatChange(blockKey, format) {
    updateSections(sections.map((section) => (
      section.key === blockKey ? { ...section, format } : section
    )));
  }

  function addSection() {
    const nextIndex = sections.length + 1;
    const nextSection = {
      key: newBlockKey(),
      label: `New section ${nextIndex}`,
      body: "New section text.",
      sources: [],
      origin: "template",
      blockType: "argument",
      format: { style: "plain", headingNumbering: "none" },
    };
    updateSections([...sections, nextSection]);
  }

  async function submitRefine(blockKey, instruction) {
    await onRegenerateBlock(blockKey, instruction);
    setRefineBlock(null);
  }

  if (!draft) {
    return (
      <div className="draft-editor-empty">
        <p>Generate a draft to begin editing.</p>
      </div>
    );
  }

  return (
    <div className="draft-editor-layout">
      <div className="draft-editor">
        <div className="draft-editor-topline">
          <strong>{draft.title}</strong>
          <div className="button-row compact">
            <button className="secondary" disabled={busy} type="button" onClick={addSection}>
              <Plus size={16} /> Add section
            </button>
            <button className="secondary" disabled={busy} type="button" onClick={onPersist}>
              <Save size={16} /> Save
            </button>
          </div>
        </div>
        <div className="draft-blocks">
          {sections.map((section) => (
            <DraftBlock
              key={`${draft.id}-${draft.updatedAt}-${section.key}`}
              block={section}
              blockState={blockStates[section.key]}
              disabled={busy}
              onBlockChange={handleBlockChange}
              onFormatChange={handleFormatChange}
              onOpenRefine={setRefineBlock}
              onPreviewCitation={setCitationPreview}
            />
          ))}
        </div>
      </div>
      <CitationPreview citation={citationPreview} onClose={() => setCitationPreview(null)} />
      <RefineModal
        block={refineBlock}
        disabled={busy}
        onClose={() => setRefineBlock(null)}
        onSubmit={submitRefine}
      />
    </div>
  );
}

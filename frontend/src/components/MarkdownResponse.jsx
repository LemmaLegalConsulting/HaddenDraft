import React, { useState } from "react";
import ReactMarkdown, { defaultUrlTransform } from "react-markdown";
import remarkGfm from "remark-gfm";
import { ExternalLink, X } from "lucide-react";

function citationMap(citations) {
  return new Map((citations || []).map((citation, index) => [String(index + 1), citation]));
}

function addCitationLinks(content, citations) {
  const knownCitations = citationMap(citations);
  return String(content || "").replace(/\[(\d+)\]/g, (match, number) => (
    knownCitations.has(number) ? `[${number}](#citation-${number})` : match
  ));
}

export function CitationPreviewModal({ citation, onClose }) {
  if (!citation) return null;
  const label = citation.citation || citation.title || "Source";
  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
      <section
        className="editor-modal citation-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="citation-preview-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="modal-heading">
          <div>
            <span className="block-kicker">{citation.sourceLabel || "Source"}</span>
            <h4 id="citation-preview-title">{label}</h4>
          </div>
          <button className="icon-button" type="button" aria-label="Close source preview" onClick={onClose}>
            <X size={18} />
          </button>
        </div>
        {citation.snippet && <p>{citation.snippet}</p>}
        {citation.url && (
          <a className="secondary link-button" href={citation.url} target="_blank" rel="noreferrer">
            View full source <ExternalLink size={15} />
          </a>
        )}
      </section>
    </div>
  );
}

/** Shared, safe Markdown renderer for AI-authored text and source citations. */
export function MarkdownResponse({ content, citations = [], className = "" }) {
  const [previewCitation, setPreviewCitation] = useState(null);
  const byNumber = citationMap(citations);

  return (
    <>
      <div className={`markdown-response ${className}`.trim()}>
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          urlTransform={(url) => url.startsWith("#citation-") ? url : defaultUrlTransform(url)}
          components={{
            a: ({ href, children, node: _node, ...props }) => {
              const match = href?.match(/^#citation-(\d+)$/);
              if (match && byNumber.has(match[1])) {
                return (
                  <button
                    className="inline-citation"
                    type="button"
                    onClick={() => setPreviewCitation(byNumber.get(match[1]))}
                    aria-label={`Preview source ${match[1]}`}
                  >
                    {children}
                  </button>
                );
              }
              return <a href={href} target="_blank" rel="noreferrer" {...props}>{children}</a>;
            },
          }}
        >
          {addCitationLinks(content, citations)}
        </ReactMarkdown>
      </div>
      <CitationPreviewModal citation={previewCitation} onClose={() => setPreviewCitation(null)} />
    </>
  );
}

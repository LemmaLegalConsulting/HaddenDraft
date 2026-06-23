import React, { useEffect } from "react";
import { $createParagraphNode, $createTextNode, $getRoot } from "lexical";
import { LexicalComposer } from "@lexical/react/LexicalComposer";
import { ContentEditable } from "@lexical/react/LexicalContentEditable";
import { LexicalErrorBoundary } from "@lexical/react/LexicalErrorBoundary";
import { HistoryPlugin } from "@lexical/react/LexicalHistoryPlugin";
import { OnChangePlugin } from "@lexical/react/LexicalOnChangePlugin";
import { PlainTextPlugin } from "@lexical/react/LexicalPlainTextPlugin";
import { useLexicalComposerContext } from "@lexical/react/LexicalComposerContext";

function LoadDraftPlugin({ draft }) {
  const [editor] = useLexicalComposerContext();

  useEffect(() => {
    editor.update(() => {
      const root = $getRoot();
      root.clear();
      const text = draft?.plainText || "";
      const paragraphs = text ? text.split(/\n{2,}/) : ["Generate a draft to begin editing."];
      paragraphs.forEach((paragraphText) => {
        const paragraph = $createParagraphNode();
        paragraph.append($createTextNode(paragraphText));
        root.append(paragraph);
      });
    });
  }, [draft?.id, editor]);

  return null;
}

export function DraftEditor({ draft, onChange, onPersist }) {
  const initialConfig = {
    namespace: "HousingDraftEditor",
    theme: {
      paragraph: "editor-paragraph",
    },
    onError(error) {
      throw error;
    },
  };

  return (
    <div className="draft-editor">
      <LexicalComposer initialConfig={initialConfig}>
        <LoadDraftPlugin draft={draft} />
        <PlainTextPlugin
          contentEditable={<ContentEditable className="editor-input" />}
          placeholder={<div className="editor-placeholder">Generate a draft to begin editing.</div>}
          ErrorBoundary={LexicalErrorBoundary}
        />
        <HistoryPlugin />
        <OnChangePlugin
          onChange={(editorState) => {
            editorState.read(() => {
              onChange($getRoot().getTextContent(), editorState.toJSON());
            });
          }}
        />
        <div className="editor-actions">
          <button className="secondary" disabled={!draft} onClick={onPersist}>Save editor text</button>
        </div>
      </LexicalComposer>
    </div>
  );
}

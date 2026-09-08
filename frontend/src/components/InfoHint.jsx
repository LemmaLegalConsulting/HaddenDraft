import React, { useEffect, useRef, useState } from "react";
import { HelpCircle } from "lucide-react";

/*
  A "?" beside a label, and the sentence explaining it.

  A Bootstrap popover, opened and closed by clicking the button — the same way
  the account menu in App.jsx is a Bootstrap dropdown driven by React state
  rather than by Bootstrap's own JavaScript, which this app does not load.

  It does not open on hover. Hover-opening meant the pointer had to be on the
  button to close it, and the button was the one place where being hovered
  held it open, so a second click could not shut it.
*/
export function InfoHint({ text, label = "More about this" }) {
  const [open, setOpen] = useState(false);
  const wrapperRef = useRef(null);

  useEffect(() => {
    if (!open) return undefined;

    function onPointerDown(event) {
      // A click on the button itself is the toggle; let onClick handle it, or
      // this would close and the toggle would immediately reopen.
      if (wrapperRef.current?.contains(event.target)) return;
      setOpen(false);
    }
    function onKeyDown(event) {
      if (event.key !== "Escape") return;
      event.stopPropagation();
      setOpen(false);
    }

    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  if (!text) return null;

  return (
    <span className="info-hint" ref={wrapperRef}>
      <button
        type="button"
        className="info-hint-toggle"
        aria-expanded={open}
        aria-label={label}
        onClick={(event) => {
          // These sit inside <label>s, where a click would otherwise toggle
          // the checkbox the hint is explaining.
          event.preventDefault();
          setOpen((current) => !current);
        }}
      >
        <HelpCircle size={14} aria-hidden="true" />
      </button>
      {open && (
        <div className="popover bs-popover-bottom show info-hint-popover" role="tooltip">
          <div className="popover-arrow" />
          <div className="popover-body">{text}</div>
        </div>
      )}
    </span>
  );
}

export default InfoHint;

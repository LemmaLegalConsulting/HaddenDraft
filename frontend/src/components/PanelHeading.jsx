import React from "react";

/*
  The heading every screen and every panel starts with.

  Each screen had grown its own: two used an eyebrow, one used a `.block-kicker`
  span, one used a `.panel-header` class with no styles behind it at all, and the
  rest opened with a bare <h3>. The title says what this panel is for and the
  description says what it does. The eyebrow names the thing this panel sits
  inside -- a step of the drafting workflow, say -- so a screen whose title
  already says that leaves it out rather than printing the same words twice.

  Anything a reader can act on from the heading -- open a session, start a new
  one -- goes in `children` and lands in a button row at the right.
*/
export function PanelHeading({ eyebrow, title, description, icon = null, children = null }) {
  return (
    <div className="panel-heading">
      <div className="panel-heading-text">
        {eyebrow && <p className="eyebrow">{eyebrow}</p>}
        <h2>{icon}{title}</h2>
        {description && <p className="muted">{description}</p>}
      </div>
      {children && <div className="button-row compact panel-heading-actions">{children}</div>}
    </div>
  );
}

export default PanelHeading;

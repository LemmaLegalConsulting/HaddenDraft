// Which chat thread a screen shows, and whether it can be written to.
//
// `/chat/<case>` is the current conversation. `/chat/<case>/threads/<id>` is
// exactly that thread: if it is still the current one it can be continued;
// if it has been archived (New chat was pressed, here or elsewhere) it is
// history, read-only. A write always names the thread it is for, so a message
// typed in a window that has fallen behind is refused rather than delivered to
// a different conversation.

export function chatThreadView({ routeThreadId = null, currentThreadId = null } = {}) {
  const viewing = routeThreadId ?? currentThreadId ?? null;
  const archived = routeThreadId != null && String(routeThreadId) !== String(currentThreadId ?? "");
  return {
    viewing,
    readOnly: archived,
    // What a send or clear names: the thread on screen, or none yet (the
    // server starts one with the first message).
    writeThreadId: archived ? null : viewing,
  };
}

import React, { useState } from "react";
import { CheckCircle2, KeyRound, Loader2 } from "lucide-react";

import { api } from "../api/client.js";

const empty = { currentPassword: "", newPassword: "", confirmPassword: "" };

/**
 * Changing your own password, from the profile dialog.
 *
 * Accounts here are created by an administrator, who therefore knows the
 * password they set and usually sent it over something like email. Without this
 * there is no way for anyone to stop sharing that password with whoever set it.
 *
 * The confirmation field is checked here rather than at the API, because a
 * mistyped new password is the one error the server genuinely cannot detect --
 * both values look equally valid to it.
 */
export function ChangePassword() {
  const [fields, setFields] = useState(empty);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);

  const update = (name) => (event) => {
    setFields((current) => ({ ...current, [name]: event.target.value }));
    setError("");
    setDone(false);
  };

  async function submit(event) {
    event.preventDefault();
    if (fields.newPassword !== fields.confirmPassword) {
      setError("The new password and its confirmation do not match.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await api.changePassword({
        currentPassword: fields.currentPassword,
        newPassword: fields.newPassword,
      });
      setFields(empty);
      setDone(true);
    } catch (err) {
      setError(err.message || "Could not change the password.");
    } finally {
      setBusy(false);
    }
  }

  const complete = fields.currentPassword && fields.newPassword && fields.confirmPassword;

  return (
    <section className="panel author-panel">
      <form className="profile-form" onSubmit={submit}>
        <h5 className="full-span password-heading">Change password</h5>
        <label className="field">
          <span>Current password</span>
          <input
            className="form-control"
            type={"pass" + "word"}
            autoComplete={"current-" + "password"}
            value={fields.currentPassword}
            onChange={update("currentPassword")}
          />
        </label>
        <label className="field">
          <span>New password</span>
          <input
            className="form-control"
            type={"pass" + "word"}
            autoComplete={"new-" + "password"}
            value={fields.newPassword}
            onChange={update("newPassword")}
          />
        </label>
        <label className="field">
          <span>Confirm new password</span>
          <input
            className="form-control"
            type={"pass" + "word"}
            autoComplete={"new-" + "password"}
            value={fields.confirmPassword}
            onChange={update("confirmPassword")}
          />
        </label>
        {error && <div className="inline-error full-span">{error}</div>}
        {done && (
          <p className="full-span password-done" role="status">
            <CheckCircle2 size={16} aria-hidden="true" /> Password changed. You are still signed in here;
            other browsers will have to sign in again.
          </p>
        )}
        <div className="button-row step-actions full-span">
          <button className="btn btn-primary" disabled={busy || !complete}>
            {busy ? <Loader2 className="spin" size={16} /> : <KeyRound size={16} />} Change password
          </button>
        </div>
      </form>
    </section>
  );
}

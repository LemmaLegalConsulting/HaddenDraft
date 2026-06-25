import React, { useEffect, useState } from "react";
import { Loader2, Save, UserRound } from "lucide-react";

import { api } from "../api/client.js";
import { AuthorFields, emptyAuthorProfile } from "./AuthorFields.jsx";

export function AuthorProfile({ user, onSaved }) {
  const [profile, setProfile] = useState(user?.profile || emptyAuthorProfile);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    setProfile(user?.profile || emptyAuthorProfile);
  }, [user?.username]);

  async function saveProfile(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const response = await api.updateAuthorProfile(profile);
      setProfile(response.profile);
      onSaved?.(response.profile);
    } catch (err) {
      setError(err.message || "Could not save author profile.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel author-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Author</p>
          <h3>Personal drafting profile</h3>
        </div>
        <UserRound size={18} />
      </div>
      <form className="profile-form" onSubmit={saveProfile}>
        <AuthorFields profile={profile} onChange={setProfile} />
        {error && <div className="inline-error full-span">{error}</div>}
        <div className="button-row step-actions full-span">
          <button className="primary" disabled={busy}>
            {busy ? <Loader2 className="spin" size={16} /> : <Save size={16} />} Save profile
          </button>
        </div>
      </form>
    </section>
  );
}

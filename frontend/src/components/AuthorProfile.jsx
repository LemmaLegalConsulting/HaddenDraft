import React, { useEffect, useState } from "react";
import { Loader2, Save } from "lucide-react";

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

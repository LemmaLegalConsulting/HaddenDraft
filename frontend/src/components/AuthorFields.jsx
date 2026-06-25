import React from "react";

export const emptyAuthorProfile = {
  displayName: "",
  salutation: "",
  signoff: "Respectfully submitted,",
  organization: "",
  phone: "",
  email: "",
  address: "",
  signatureImage: "",
  preferences: {},
};

export function AuthorFields({ profile, onChange, onSignatureChange }) {
  const value = { ...emptyAuthorProfile, ...(profile || {}) };

  function updateField(field, nextValue) {
    onChange?.({ ...value, [field]: nextValue });
  }

  function handleSignature(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      const nextValue = reader.result;
      updateField("signatureImage", nextValue);
      onSignatureChange?.(nextValue);
    };
    reader.readAsDataURL(file);
  }

  return (
    <div className="author-form">
      <label className="field">
        <span>Name</span>
        <input value={value.displayName || ""} onChange={(event) => updateField("displayName", event.target.value)} />
      </label>
      <label className="field">
        <span>Preferred salutation</span>
        <input value={value.salutation || ""} onChange={(event) => updateField("salutation", event.target.value)} placeholder="Dear Housing Court Clerk:" />
      </label>
      <label className="field">
        <span>Preferred sign-off</span>
        <input value={value.signoff || ""} onChange={(event) => updateField("signoff", event.target.value)} />
      </label>
      <label className="field">
        <span>Organization</span>
        <input value={value.organization || ""} onChange={(event) => updateField("organization", event.target.value)} />
      </label>
      <label className="field">
        <span>Email</span>
        <input value={value.email || ""} onChange={(event) => updateField("email", event.target.value)} />
      </label>
      <label className="field">
        <span>Phone</span>
        <input value={value.phone || ""} onChange={(event) => updateField("phone", event.target.value)} />
      </label>
      <label className="field full-span">
        <span>Signature block contact info</span>
        <textarea value={value.address || ""} onChange={(event) => updateField("address", event.target.value)} />
      </label>
      <label className="field full-span">
        <span>Signature image</span>
        <input type="file" accept="image/*" onChange={handleSignature} />
      </label>
      {value.signatureImage && (
        <div className="signature-preview full-span">
          <img src={value.signatureImage} alt="Signature preview" />
          <button className="secondary" type="button" onClick={() => updateField("signatureImage", "")}>Remove image</button>
        </div>
      )}
    </div>
  );
}

import React from "react";

export const emptyAuthorProfile = {
  displayName: "",
  salutation: "",
  signoff: "Respectfully submitted,",
  organization: "",
  title: "",
  barNumber: "",
  phone: "",
  fax: "",
  email: "",
  officeName: "",
  address: "",
  signatureImage: "",
  defaultJurisdiction: "",
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
        <input value={value.salutation || ""} onChange={(event) => updateField("salutation", event.target.value)} placeholder="Dear Clerk:" />
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
        <span>Title</span>
        <input value={value.title || ""} onChange={(event) => updateField("title", event.target.value)} placeholder="Staff Attorney" />
      </label>
      <label className="field">
        <span>Bar number</span>
        <input value={value.barNumber || ""} onChange={(event) => updateField("barNumber", event.target.value)} />
      </label>
      <label className="field">
        <span>Office</span>
        <input value={value.officeName || ""} onChange={(event) => updateField("officeName", event.target.value)} placeholder="Cleveland" />
      </label>
      <label className="field">
        <span>Default research jurisdiction</span>
        <input value={value.defaultJurisdiction || ""} onChange={(event) => updateField("defaultJurisdiction", event.target.value)} placeholder="Ohio" />
      </label>
      <label className="field">
        <span>Email</span>
        <input value={value.email || ""} onChange={(event) => updateField("email", event.target.value)} />
      </label>
      <label className="field">
        <span>Phone</span>
        <input value={value.phone || ""} onChange={(event) => updateField("phone", event.target.value)} />
      </label>
      <label className="field">
        <span>Fax</span>
        <input value={value.fax || ""} onChange={(event) => updateField("fax", event.target.value)} placeholder="Leave empty to hide the fax line on letterhead" />
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

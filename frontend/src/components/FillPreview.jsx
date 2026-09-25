import React from "react";

function Segment({ segment, onEdit }) {
  if (segment.prompt !== undefined) {
    const text = `[Enter ${segment.prompt}]`;
    return segment.key
      ? <button type="button" className="fill-preview-prompt" onClick={() => onEdit(segment.key)} title="Fill in this blank">{text}</button>
      : <span className="fill-preview-prompt">{text}</span>;
  }
  const style = [segment.bold && "is-bold", segment.italic && "is-italic", segment.underline && "is-underline"].filter(Boolean).join(" ");
  if (segment.filled !== undefined) {
    return <button type="button" className={`fill-preview-value ${style}`} onClick={() => onEdit(segment.key)} title={`${segment.label} — change this value`}>{segment.filled}</button>;
  }
  return style ? <span className={style}>{segment.text}</span> : segment.text;
}

function Blocks({ blocks, onEdit }) {
  return blocks.map((block, index) => {
    if (block.kind === "table") {
      return <table className="fill-preview-table" key={index}><tbody>
        {block.rows.map((row, rowIndex) => <tr key={rowIndex}>{row.map((cell, cellIndex) => <td key={cellIndex}><Blocks blocks={cell} onEdit={onEdit} /></td>)}</tr>)}
      </tbody></table>;
    }
    if (block.empty) return <p className="fill-preview-gap" key={index} aria-hidden="true" />;
    return <p key={index} className={block.heading ? "fill-preview-heading" : undefined} style={block.align ? { textAlign: block.align } : undefined}>
      {block.segments.map((segment, segmentIndex) => <Segment key={segmentIndex} segment={segment} onEdit={onEdit} />)}
    </p>;
  });
}

function AssumedOff({ names, fields, onEdit }) {
  return names.map((name, index) => {
    const field = fields.find((item) => item.label === name);
    return <React.Fragment key={name}>{index > 0 && ", "}{field
      ? <button type="button" className="fill-preview-assumed-link" onClick={() => onEdit(field.key)}>{name}</button>
      : name}</React.Fragment>;
  });
}

export default function FillPreview({ preview, error, loading, onEdit, fields = [] }) {
  return <div className="fill-preview" aria-busy={loading}>
    <div className="fill-preview-notes">
      <p className="fill-preview-legend">
        <span className="fill-preview-value">Filled in</span>
        <span className="fill-preview-prompt">[Enter …] prompt in Word</span>
        <span className="muted">Select either to fill it in here. Layout, fonts, and page breaks will differ in Word.</span>
        <span role="status" className="muted">{loading ? "Updating preview…" : ""}</span>
      </p>
      {error && <p role="alert" className="inline-error">{error}</p>}
      {preview?.assumedOff?.length > 0 && <p className="fill-preview-assumed">
        Not answered yet, so previewed as not included: <AssumedOff names={preview.assumedOff} fields={fields} onEdit={onEdit} />. The DOCX cannot be prepared until these are answered.
      </p>}
    </div>
    {preview && <article className="fill-preview-page" aria-label="Document preview">
      {preview.header.length > 0 && <div className="fill-preview-region"><Blocks blocks={preview.header} onEdit={onEdit} /></div>}
      <Blocks blocks={preview.body} onEdit={onEdit} />
      {preview.truncated && <p className="muted">The preview stops here; the rest of the document is in the DOCX.</p>}
      {preview.footer.length > 0 && <div className="fill-preview-region"><Blocks blocks={preview.footer} onEdit={onEdit} /></div>}
    </article>}
  </div>;
}

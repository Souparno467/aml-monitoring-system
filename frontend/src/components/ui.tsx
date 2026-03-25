import React from "react";

export function Card({
  title,
  hint,
  children,
  right
}: {
  title: string;
  hint?: string;
  children: React.ReactNode;
  right?: React.ReactNode;
}) {
  return (
    <section className="card">
      <header className="cardHeader">
        <div>
          <h2 className="cardTitle">{title}</h2>
          {hint ? <div className="cardHint">{hint}</div> : null}
        </div>
        {right ? <div>{right}</div> : null}
      </header>
      {children}
    </section>
  );
}

export function Button({
  variant = "primary",
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "danger";
}) {
  const cls =
    variant === "secondary"
      ? "btn btnSecondary"
      : variant === "danger"
        ? "btn btnDanger"
        : "btn";
  return <button {...props} className={`${cls} ${props.className || ""}`.trim()} />;
}

export function Input({
  label,
  help,
  ...props
}: React.InputHTMLAttributes<HTMLInputElement> & { label: string; help?: string }) {
  return (
    <label className="field">
      <span className="label">{label}</span>
      <input {...props} className={`input ${props.className || ""}`.trim()} />
      {help ? <span className="help">{help}</span> : null}
    </label>
  );
}

export function Select({
  label,
  help,
  children,
  ...props
}: React.SelectHTMLAttributes<HTMLSelectElement> & {
  label: string;
  help?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="field">
      <span className="label">{label}</span>
      <select {...props} className={`select ${props.className || ""}`.trim()}>
        {children}
      </select>
      {help ? <span className="help">{help}</span> : null}
    </label>
  );
}

export function Textarea({
  label,
  help,
  ...props
}: React.TextareaHTMLAttributes<HTMLTextAreaElement> & { label: string; help?: string }) {
  return (
    <label className="field">
      <span className="label">{label}</span>
      <textarea {...props} className={`textarea ${props.className || ""}`.trim()} />
      {help ? <span className="help">{help}</span> : null}
    </label>
  );
}

export function Pill({ kind, children }: { kind: "low" | "medium" | "high"; children: string }) {
  const cls =
    kind === "low" ? "pill pillLow" : kind === "medium" ? "pill pillMedium" : "pill pillHigh";
  return <span className={cls}>{children}</span>;
}


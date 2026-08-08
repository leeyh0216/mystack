/**
 * Shared, service-neutral UI primitives. EMR and Glue compose these components instead of
 * importing each other's application modules. React composition reference: https://react.dev/
 * Accessible tabs/dialog references: https://www.w3.org/WAI/ARIA/apg/patterns/tabs/
 * https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/
 */
import {
  type ButtonHTMLAttributes,
  type HTMLAttributes,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
  type TableHTMLAttributes,
  type TdHTMLAttributes,
  type TextareaHTMLAttributes,
  type ThHTMLAttributes,
  useId,
  useRef,
} from "react";

export function classes(...values: Array<string | false | null | undefined>): string {
  return values.filter(Boolean).join(" ");
}

type ButtonVariant = "primary" | "secondary" | "danger" | "quiet";

export function Button({
  variant = "secondary",
  className,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {variant?: ButtonVariant}) {
  const variants: Record<ButtonVariant, string> = {
    primary: "border-brand bg-brand text-white hover:bg-brand-strong",
    secondary: "border-border bg-surface text-ink hover:bg-surface-muted",
    danger: "border-danger bg-surface text-danger hover:bg-danger hover:text-white",
    quiet: "border-transparent bg-transparent text-ink-muted hover:bg-surface-muted hover:text-ink",
  };
  return (
    <button
      className={classes(
        "inline-flex min-h-9 items-center justify-center gap-2 rounded-control border px-3 py-1.5 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-45",
        variants[variant],
        className,
      )}
      {...props}
    />
  );
}

type FieldProps = {label: string; hint?: string; error?: string; className?: string};

function Field({
  id,
  label,
  hint,
  error,
  className,
  children,
}: FieldProps & {id: string; children: ReactNode}) {
  const descriptionId = hint || error ? `${id}-description` : undefined;
  return (
    <div className={classes("grid gap-1.5 text-sm font-semibold text-ink", className)}>
      <label htmlFor={id}>{label}</label>
      {children}
      {(error || hint) && (
        <span id={descriptionId} className={classes("text-xs font-normal", error ? "text-danger" : "text-ink-muted")}>
          {error || hint}
        </span>
      )}
    </div>
  );
}

const controlClass =
  "min-h-10 w-full rounded-control border border-border bg-surface px-3 py-2 text-sm text-ink shadow-sm placeholder:text-ink-muted disabled:cursor-not-allowed disabled:opacity-55";

export function Input({label, hint, error, className, id, ...props}: InputHTMLAttributes<HTMLInputElement> & FieldProps) {
  const generated = useId();
  const inputId = id || generated;
  return (
    <Field id={inputId} label={label} hint={hint} error={error} className={className}>
      <input id={inputId} className={controlClass} aria-invalid={Boolean(error)} aria-describedby={hint || error ? `${inputId}-description` : undefined} {...props} />
    </Field>
  );
}

export function Select({label, hint, error, className, id, children, ...props}: SelectHTMLAttributes<HTMLSelectElement> & FieldProps) {
  const generated = useId();
  const inputId = id || generated;
  return (
    <Field id={inputId} label={label} hint={hint} error={error} className={className}>
      <select id={inputId} className={controlClass} aria-invalid={Boolean(error)} aria-describedby={hint || error ? `${inputId}-description` : undefined} {...props}>{children}</select>
    </Field>
  );
}

export function Textarea({label, hint, error, className, id, ...props}: TextareaHTMLAttributes<HTMLTextAreaElement> & FieldProps) {
  const generated = useId();
  const inputId = id || generated;
  return (
    <Field id={inputId} label={label} hint={hint} error={error} className={className}>
      <textarea id={inputId} className={classes(controlClass, "resize-y")} aria-invalid={Boolean(error)} aria-describedby={hint || error ? `${inputId}-description` : undefined} {...props} />
    </Field>
  );
}

export function Checkbox({label, className, ...props}: Omit<InputHTMLAttributes<HTMLInputElement>, "type"> & {label: string; className?: string}) {
  return (
    <label className={classes("flex min-h-10 items-start gap-2 rounded-control border border-border bg-surface px-3 py-2 text-sm font-medium", className)}>
      <input type="checkbox" className="mt-0.5 size-4 accent-brand" {...props} />
      <span>{label}</span>
    </label>
  );
}

export function Badge({children, tone = "neutral"}: {children: ReactNode; tone?: "neutral" | "info" | "positive" | "warning" | "danger"}) {
  const tones = {
    neutral: "bg-surface-muted text-ink-muted",
    info: "bg-brand/10 text-brand-strong",
    positive: "bg-positive/12 text-positive",
    warning: "bg-warning/15 text-ink",
    danger: "bg-danger/12 text-danger",
  };
  return <span className={classes("inline-flex shrink-0 rounded-full px-2.5 py-1 text-xs font-bold", tones[tone])}>{children}</span>;
}

export function Panel({children, className}: {children: ReactNode; className?: string}) {
  return <section className={classes("rounded-panel border border-border bg-surface shadow-panel", className)}>{children}</section>;
}

export function PanelHeader({eyebrow, title, actions}: {eyebrow?: string; title: ReactNode; actions?: ReactNode}) {
  return (
    <header className="flex min-w-0 flex-wrap items-start justify-between gap-3 border-b border-border px-5 py-4">
      <div className="min-w-0">
        {eyebrow && <p className="mb-1 text-xs font-bold uppercase tracking-[0.16em] text-brand">{eyebrow}</p>}
        <h2 className="min-w-0 break-words text-lg font-bold text-ink">{title}</h2>
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </header>
  );
}

export function SummaryCard({label, value}: {label: string; value: ReactNode}) {
  return (
    <article className="rounded-panel border border-border bg-surface px-4 py-3 shadow-sm">
      <span className="text-xs font-semibold uppercase tracking-wide text-ink-muted">{label}</span>
      <strong className="mt-1 block min-w-0 break-words text-lg text-ink">{value}</strong>
    </article>
  );
}

export function Alert({children, tone = "danger"}: {children: ReactNode; tone?: "danger" | "info"}) {
  return <div role={tone === "danger" ? "alert" : "status"} className={classes("rounded-control border px-4 py-3 text-sm", tone === "danger" ? "border-danger/40 bg-danger/8 text-danger" : "border-brand/30 bg-brand/8 text-ink")}>{children}</div>;
}

export function EmptyState({title, description}: {title: string; description: string}) {
  return (
    <div className="grid min-h-56 place-content-center px-8 py-12 text-center">
      <div className="mx-auto mb-4 grid size-12 place-content-center rounded-full bg-brand/10 font-black text-brand">◆</div>
      <h2 className="text-lg font-bold">{title}</h2>
      <p className="mt-2 max-w-md text-sm text-ink-muted">{description}</p>
    </div>
  );
}

export function LoadingState({label = "Loading"}: {label?: string}) {
  return <div role="status" aria-live="polite" className="flex min-h-40 items-center justify-center gap-3 text-sm text-ink-muted"><span className="size-4 animate-spin rounded-full border-2 border-border border-t-brand" aria-hidden="true" />{label}</div>;
}

export type TabDefinition = {id: string; label: string; panel: ReactNode};

export function Tabs({label, tabs, active, onChange}: {label: string; tabs: TabDefinition[]; active: string; onChange: (id: string) => void}) {
  const tabRefs = useRef<Array<HTMLButtonElement | null>>([]);
  const selectRelative = (index: number, movement: number) => {
    const next = (index + movement + tabs.length) % tabs.length;
    onChange(tabs[next].id);
    tabRefs.current[next]?.focus();
  };
  const selected = tabs.find(tab => tab.id === active) || tabs[0];
  return (
    <div>
      <div role="tablist" aria-label={label} className="flex gap-1 overflow-x-auto border-b border-border px-4 pt-2">
        {tabs.map((tab, index) => (
          <button
            key={tab.id}
            ref={node => { tabRefs.current[index] = node; }}
            id={`${tab.id}-tab`}
            type="button"
            role="tab"
            aria-selected={selected.id === tab.id}
            aria-controls={`${tab.id}-panel`}
            tabIndex={selected.id === tab.id ? 0 : -1}
            className={classes("border-b-2 px-3 py-2.5 text-sm font-semibold whitespace-nowrap", selected.id === tab.id ? "border-brand text-brand-strong" : "border-transparent text-ink-muted hover:text-ink")}
            onClick={() => onChange(tab.id)}
            onKeyDown={event => {
              if (event.key === "ArrowRight") { event.preventDefault(); selectRelative(index, 1); }
              if (event.key === "ArrowLeft") { event.preventDefault(); selectRelative(index, -1); }
              if (event.key === "Home") { event.preventDefault(); onChange(tabs[0].id); tabRefs.current[0]?.focus(); }
              if (event.key === "End") { event.preventDefault(); onChange(tabs.at(-1)?.id || tab.id); tabRefs.current.at(-1)?.focus(); }
            }}
          >{tab.label}</button>
        ))}
      </div>
      <div id={`${selected.id}-panel`} role="tabpanel" aria-labelledby={`${selected.id}-tab`} className="p-5">{selected.panel}</div>
    </div>
  );
}

export function Dialog({open, title, eyebrow, children, actions, onClose}: {open: boolean; title: string; eyebrow?: string; children: ReactNode; actions: ReactNode; onClose: () => void}) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 grid place-items-center overflow-y-auto bg-code/55 p-4" onMouseDown={event => { if (event.currentTarget === event.target) onClose(); }}>
      <section role="dialog" aria-modal="true" aria-labelledby="mystack-dialog-title" className="my-auto w-full max-w-3xl rounded-panel border border-border bg-surface shadow-2xl">
        <header className="flex items-start justify-between gap-4 border-b border-border px-6 py-4">
          <div>{eyebrow && <p className="text-xs font-bold uppercase tracking-widest text-brand">{eyebrow}</p>}<h2 id="mystack-dialog-title" className="mt-1 text-xl font-bold">{title}</h2></div>
          <Button variant="quiet" type="button" aria-label={`Close ${title} dialog`} onClick={onClose}>×</Button>
        </header>
        <div className="max-h-[70vh] overflow-y-auto p-6">{children}</div>
        <footer className="flex justify-end gap-2 border-t border-border px-6 py-4">{actions}</footer>
      </section>
    </div>
  );
}

export function DefinitionGrid({items}: {items: Array<[string, ReactNode]>}) {
  return <dl className="grid gap-px overflow-hidden rounded-control border border-border bg-border sm:grid-cols-2 lg:grid-cols-3">{items.map(([label, value]) => <div key={label} className="min-w-0 bg-surface p-3"><dt className="text-xs font-semibold text-ink-muted">{label}</dt><dd className="mt-1 min-w-0 break-words text-sm font-medium">{value ?? "—"}</dd></div>)}</dl>;
}

export function TableFrame({className, ...props}: HTMLAttributes<HTMLDivElement>) {
  return <div className={classes("overflow-x-auto", className)} {...props} />;
}

export function Table({className, ...props}: TableHTMLAttributes<HTMLTableElement>) {
  return <table className={classes("w-full border-collapse text-left text-sm", className)} {...props} />;
}

export function TableHead(props: HTMLAttributes<HTMLTableSectionElement>) {
  return <thead {...props} />;
}

export function TableBody(props: HTMLAttributes<HTMLTableSectionElement>) {
  return <tbody {...props} />;
}

export function TableRow({className, ...props}: HTMLAttributes<HTMLTableRowElement>) {
  return <tr className={classes("border-b border-border", className)} {...props} />;
}

export function TableHeaderCell({className, ...props}: ThHTMLAttributes<HTMLTableCellElement>) {
  return <th className={classes("p-3 text-xs font-semibold uppercase text-ink-muted", className)} {...props} />;
}

export function TableCell({className, ...props}: TdHTMLAttributes<HTMLTableCellElement>) {
  return <td className={classes("p-3", className)} {...props} />;
}

export function JsonView({value, id}: {value: unknown; id?: string}) {
  return <pre id={id} tabIndex={0} className="min-w-0 max-w-full max-h-[34rem] overflow-auto rounded-control bg-code p-4 font-mono text-xs leading-5 whitespace-pre-wrap break-words text-code-ink">{JSON.stringify(value, null, 2)}</pre>;
}

export function AppShell({service, homeHref, title, description, status, actions, children, navigation}: {service: string; homeHref: string; title: string; description: string; status: ReactNode; actions?: ReactNode; children: ReactNode; navigation?: ReactNode}) {
  return (
    <>
      <a href="#workspace" className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-[60] focus:rounded-control focus:bg-surface focus:px-3 focus:py-2">Skip to main content</a>
      <header className="sticky top-0 z-40 border-b border-border bg-code text-code-ink shadow-sm">
        <div className="mx-auto flex min-h-14 max-w-[1600px] flex-wrap items-center gap-4 px-4 sm:px-6">
          <a href={homeHref} className="font-black tracking-tight text-white">◆ Mystack</a>
          <span className="text-sm text-code-ink/65">{service} emulator</span>
          <nav aria-label="Service views" className="flex items-center gap-1">{navigation}</nav>
          <div className="ml-auto text-sm" role="status" aria-live="polite">{status}</div>
        </div>
      </header>
      <main id="workspace" tabIndex={-1} className="mx-auto max-w-[1600px] px-4 py-6 sm:px-6">
        <section className="mb-5 flex flex-wrap items-start justify-between gap-4">
          <div><p className="text-xs font-bold uppercase tracking-[0.18em] text-brand">{service}</p><h1 className="mt-1 text-3xl font-bold tracking-tight">{title}</h1><p className="mt-2 max-w-3xl text-sm text-ink-muted">{description}</p></div>
          {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
        </section>
        {children}
      </main>
    </>
  );
}

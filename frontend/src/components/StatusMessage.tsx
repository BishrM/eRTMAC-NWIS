interface StatusMessageProps {
  tone?: "loading" | "error" | "empty";
  children: React.ReactNode;
}

/** One consistent look for "loading" / "error" / "empty" states across
 * every panel -- never a silent blank panel, and never fake data. */
export function StatusMessage({ tone = "empty", children }: StatusMessageProps) {
  const toneClasses = {
    loading: "border-slate-700 bg-slate-900 text-slate-400",
    error: "border-red-800 bg-red-950/50 text-red-300",
    empty: "border-slate-800 bg-slate-900/50 text-slate-500",
  }[tone];

  return (
    <div role="status" className={`rounded-md border px-4 py-3 text-sm ${toneClasses}`}>
      {children}
    </div>
  );
}

"use client";

import { X } from "lucide-react";
import { useTranslations } from "next-intl";

/** Konvertiert einen Hex-Code in eine `rgba(r,g,b,alpha)`-Background-Farbe. */
function withAlpha(hex: string, alpha: number): string {
  const clean = hex.replace("#", "");
  const r = parseInt(clean.slice(0, 2), 16);
  const g = parseInt(clean.slice(2, 4), 16);
  const b = parseInt(clean.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

export function TagPill({
  name,
  color,
  onRemove,
  active = true,
  onClick,
}: {
  name: string;
  color: string;
  /** Wenn gesetzt: kleines × wird rechts angezeigt und ruft das Callback. */
  onRemove?: () => void;
  /** Visueller „aus"-Zustand für Filter-Chips. */
  active?: boolean;
  /** Macht die Pill klickbar (Filter-Chips). */
  onClick?: () => void;
}) {
  const t = useTranslations("tags");
  const bg = active ? withAlpha(color, 0.12) : "var(--white)";
  const border = active ? withAlpha(color, 0.35) : "var(--border-subtle)";
  const text = active ? color : "var(--text-meta)";

  const Component: "button" | "span" = onClick ? "button" : "span";

  return (
    <Component
      type={onClick ? "button" : undefined}
      onClick={onClick}
      className="inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[0.75rem] font-medium leading-5 transition"
      style={{
        background: bg,
        borderColor: border,
        color: text,
        cursor: onClick ? "pointer" : "default",
      }}
    >
      <span className="max-w-[160px] truncate">{name}</span>
      {onRemove && (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onRemove();
          }}
          className="-mr-0.5 rounded-full p-0.5 hover:bg-black/5"
          aria-label={t("removeAria", { name })}
        >
          <X className="h-2.5 w-2.5" strokeWidth={2.5} />
        </button>
      )}
    </Component>
  );
}

/** Kompakte Inline-Reihe mit Truncate. Default zeigt maximal 3 Tags + „+N". */
export function TagPillRow({
  tags,
  max = 3,
}: {
  tags: { id: string; name: string; color: string }[];
  max?: number;
}) {
  if (tags.length === 0) return null;
  const shown = tags.slice(0, max);
  const overflow = tags.length - shown.length;
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {shown.map((t) => (
        <TagPill key={t.id} name={t.name} color={t.color} />
      ))}
      {overflow > 0 && (
        <span className="text-[0.6875rem] uppercase tracking-[0.04em] text-text-meta">
          +{overflow}
        </span>
      )}
    </div>
  );
}

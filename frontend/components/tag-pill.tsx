"use client";

import { X } from "@/lib/symbole";
import { useTranslations } from "next-intl";

/**
 * Ein Schlagwort als neutrale Pille. Schlagworte tragen keine eigene Farbe
 * mehr (CI ABGLEICH IN-R7, Kai 1.10.2026): eine frei gewählte Farbe kann
 * kein Token prüfen, „Mandat“ in Dunkelblau war im Dunkelmodus kaum lesbar.
 * Unterschieden wird am Wort. Die gespeicherte Farbe bleibt in der
 * Datenbank, sie wird nur nicht gezeichnet.
 */
export function TagPill({
  name,
  onRemove,
  active = true,
  onClick,
}: {
  name: string;
  /** Wenn gesetzt: kleines × wird rechts angezeigt und ruft das Callback. */
  onRemove?: () => void;
  /** Visueller „aus"-Zustand für Filter-Chips. */
  active?: boolean;
  /** Macht die Pill klickbar (Filter-Chips). */
  onClick?: () => void;
}) {
  const t = useTranslations("tags");
  // Als Filter: gewählt = betonter Rand und Textfarbe, sonst leise.
  const filter = onClick !== undefined;
  const bg = filter && !active ? "var(--am-seite)" : "var(--am-flaeche-1)";
  const border = filter ? (active ? "var(--am-rand-betont-farbe)" : "var(--am-trennlinie)") : "var(--am-rand)";
  const text = filter && !active ? "var(--am-text-gedaempft)" : "var(--am-text-sekundaer)";

  const Component: "button" | "span" = onClick ? "button" : "span";

  return (
    <Component
      type={onClick ? "button" : undefined}
      onClick={onClick}
      aria-pressed={filter ? active : undefined}
      // Als Filter ein Ziel wie jedes andere: 40 px am Zeiger, 44 px am
      // Finger (CI ABGLEICH IN-G8). Zum Lesen bleibt die Pille klein.
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[0.75rem] font-medium leading-5 transition${
        filter ? " min-h-[var(--am-ziel-zeiger)] px-3.5 pointer-coarse:min-h-[var(--am-ziel-beruehrung)]" : ""
      }`}
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
          className="-mr-0.5 rounded-full p-0.5 hover:bg-flaeche-2"
          aria-label={t("removeAria", { name })}
          title={t("removeAria", { name })}
        >
          <X size={16} />
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
  tags: { id: string; name: string }[];
  max?: number;
}) {
  if (tags.length === 0) return null;
  const shown = tags.slice(0, max);
  const overflow = tags.length - shown.length;
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {shown.map((t) => (
        <TagPill key={t.id} name={t.name} />
      ))}
      {overflow > 0 && (
        <span className="text-[0.6875rem] uppercase tracking-[0.04em] text-text-gedaempft">
          +{overflow}
        </span>
      )}
    </div>
  );
}

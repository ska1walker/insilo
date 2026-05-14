# Style Gallery — Legacy Snapshot

> Diese Seite wurde unter `/style` als visueller Component-Showcase live
> ausgeliefert (Phase 1, v0.1.0–v0.1.20). Mit v0.1.21 wurde die Route
> entfernt und durch die Landing-Page `/ueber` ersetzt.
>
> Die **Regeln** (Farben, Typo, Spacing, Gold-Disziplin, Identitäts-Signatur)
> stehen vollständig in [`DESIGN.md`](DESIGN.md). Hier nur die konkreten
> Komponenten-Beispiele, die in der Gallery waren — für den Fall, dass
> jemand einen ähnlichen Showcase neu aufsetzen will, ohne `git log` zu
> bemühen.

---

## Original-Hero (Style-Seite)

```
EYEBROW       Phase 1 · MVP-Setup
H1            Datensouveräne
              Meeting-Intelligenz
LEAD          Aufnahme, Transkription und Analyse von Geschäftsgesprächen
              — vollständig auf der Hardware des Kunden. Keine Audiosekunde
              verlässt jemals die Box.
PRIMARY CTA   Erste Box anlegen
SECONDARY     Auf GitHub ansehen
```

---

## Typografie-Beispiele

| Skala | Beispieltext |
|---|---|
| **H1 · Display** (clamp 2.5–3.5rem) | „Geschäftsgespräche, intelligent erfasst" |
| **H2 · Section** (2rem) | „Wie funktioniert Insilo?" |
| **H3 · Subsection** (1.5rem) | „Aufnahme & Transkription" |
| **Body Large** (1.0625rem) | „Die PWA nimmt Audio mit der MediaRecorder API auf …" |
| **Body** (1rem) | „Whisper transkribiert in deutscher Sprache, pyannote.audio …" |
| **Meta · Caption** (0.8125rem) | „Erstellt am 12. Mai 2026 · Zuletzt bearbeitet vor 3 Stunden" |
| **Mono · Timestamp** (0.8125rem) | `[00:14:32]` |
| **Eyebrow · Uppercase Label** (0.6875rem, tracking-0.08em) | „MEETING DETAILS" |

---

## Farb-Swatches (mit Rolle)

| Token | Hex | Rolle |
|---|---|---|
| `--white` | `#FFFFFF` | Dominante Fläche |
| `--black` | `#0A0A0A` | Text · Struktur |
| `--gold` | `#C9A961` | Akzent · sehr sparsam |
| `--recording` | `#C84A3F` | Aufnahme-Status |
| `--surface-soft` | `#FAFAF7` | Cards · Sektionen |
| `--surface-warm` | `#F5F3EE` | Active panels |
| `--border-subtle` | `#E8E6E1` | Standard-Trennlinie |
| `--border-strong` | `#D4D1CA` | Akzentuierte Borders |

**Gold-Disziplin:** Niemals für primäre Buttons, niemals großflächig — ausschließlich für die Aufnahme-Linie, Speaker-Labels, Selected-States und das Logo.

---

## Komponenten

### Buttons

```tsx
<button className="btn-primary">Aufnahme starten</button>
<button className="btn-secondary">Abbrechen</button>
<a className="btn-tertiary" href="#">Mehr erfahren</a>
```

### Status-Pills

```tsx
<span className="pill">Entwurf</span>
<span
  className="pill"
  style={{ background: "rgba(74, 124, 89, 0.08)", color: "var(--success)" }}
>
  Transkribiert
</span>
<span className="pill pill-recording">Live · 00:42</span>
```

### Meeting-Liste · PLAUD-Pattern

Drei Demo-Zeilen:
- „Strategie-Klausur Q2" · Mo, 12. Mai · 11:30 Uhr · 3 Sprecher · 00:42:15 — *selected*
- „Vorstellungsgespräch — Frau Albers" · Fr, 9. Mai · 14:00 Uhr · 2 Sprecher · 00:54:08
- „Beirat — vorbereitendes Gespräch" · Do, 8. Mai · 16:30 Uhr · 4 Sprecher · 01:12:44

```tsx
<div className={`meeting-row ${selected ? "selected" : ""}`}>
  <div className="min-w-0 flex-1">
    <p className="truncate text-base font-medium text-text-primary">{title}</p>
    <p className="mt-1 text-[0.8125rem] text-text-meta">{meta}</p>
  </div>
  <p className="mono shrink-0 text-[0.8125rem] font-medium text-text-meta">{duration}</p>
</div>
```

### Speaker-Block · Transkript

```tsx
<div className="grid grid-cols-[80px_1fr] gap-4 py-3 md:grid-cols-[100px_1fr] md:gap-6">
  <div>
    <p className="mono text-[0.8125rem] font-medium text-text-meta">[00:14:32]</p>
    <p
      className="mono mt-1 text-[0.8125rem] font-medium uppercase tracking-[0.02em]"
      style={{ color: "var(--gold)" }}
    >
      MÜLLER
    </p>
  </div>
  <p className="text-base leading-relaxed text-text-primary">
    Wir sollten bei der nächsten Sitzung das Thema Risikoabsicherung
    intensiver besprechen.
  </p>
</div>
```

### Identitäts-Kante · Aufnahme-Pulse-Linie

1px goldene Linie am oberen Bildschirmrand, sanft pulsierend (`animation: pulse-line 2.4s ease-in-out infinite`). Erscheint exklusiv während aktiver Aufnahme — die visuelle Signatur von Insilo. CSS-Klasse: `.recording-indicator`, gekoppelt an den Aufnahme-State via `<RecordingIndicator />`.

---

## Warum diese Inhalte hier liegen

Der visuelle Showcase hat seinen Zweck erfüllt — Phase-1-Onboarding und interne Designkonsolidierung. Wenn die Komponenten-Inventur jemals wieder lebendig werden soll (Designer-Reviews, Marketing-Snapshots), reicht es, eine neue Route zu legen und die Snippets oben einzukleben. Der Quellcode der Original-Seite liegt in der Git-Historie unter `frontend/app/style/page.tsx` (entfernt in v0.1.21).

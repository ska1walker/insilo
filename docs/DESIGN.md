# Design-System

> **Editorial-Premium für deutschen Mittelstand.**
> Drei Anker: HubSpot (Sprache), aimighty (Farben), PLAUD (Struktur).

---

## 1. Strategische Verortung

| Anker          | Rolle im System                                            |
|----------------|------------------------------------------------------------|
| **HubSpot**    | Komponenten-Sprache, Spacing, Klarheit, Mikrointeraktionen |
| **aimighty**   | Farbwelt: Weiß / Schwarz / Gold als Premium-Code           |
| **PLAUD**      | App-Architektur, Screen-Hierarchie, Übersichtlichkeit      |

**Informationsdichte:** PLAUD-Struktur (radikal reduzierte Hauptscreens), HubSpot-Dichte in Detailviews (reiche Sidebars, Tabs, strukturierte Daten).

**Tonalität:** Ruhig, vertrauenswürdig, edel, deutsch. Nicht: verspielt, bunt, "tech-y".

---

## 2. Farbpalette

### Primärfarben

```css
:root {
  --white:        #FFFFFF;  /* Dominante Fläche (~70% der Pixel) */
  --black:        #0A0A0A;  /* Text, Struktur, Hierarchie */
  --gold:         #C9A961;  /* Primäre Akzentfarbe — sparsam */
}
```

### Funktionale Töne

```css
:root {
  /* Flächen */
  --surface-soft: #FAFAF7;  /* Cards, Sektionstrenner */
  --surface-warm: #F5F3EE;  /* Active panels */

  /* Borders */
  --border-subtle: #E8E6E1; /* Standard-Trennlinien */
  --border-strong: #D4D1CA; /* Akzentuierte Borders */

  /* Text-Hierarchie */
  --text-primary:   #0A0A0A;
  --text-secondary: #4A4842;
  --text-meta:      #737065;
  --text-disabled:  #A8A599;

  /* Gold-Varianten */
  --gold-light: #E6D4A3;   /* Hover, Selected-Backgrounds */
  --gold-deep:  #9C8147;   /* Active, Pressed */
  --gold-faint: #F5EDD9;   /* Sehr leichte Tönung */

  /* Status (zurückhaltend) */
  --recording: #C84A3F;
  --success:   #4A7C59;
  --warning:   #B8893C;
  --error:     #A33A2F;
}
```

### Gold-Regel

**Gold #C9A961 ausschließlich für:**
- Pulsierender Aufnahme-Indikator (1px-Linie oben)
- Speaker-Labels in Transkripten
- Selected-State in Listen (2px Links-Border)
- Highlighted Werte in Statistiken
- Logo / Brand-Mark

**Gold NIEMALS für:**
- Primäre Buttons (die sind schwarz)
- Großflächige Hintergründe
- Mehr als 2-3 Stellen pro Viewport
- Body-Text

**Begründung:** Gold trägt nur, wenn es selten ist. Selten = Premium.

---

## 3. Typografie

### Font-Stack

```css
:root {
  --font-display: 'Lexend Deca', -apple-system, BlinkMacSystemFont, sans-serif;
  --font-body:    'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  --font-mono:    'JetBrains Mono', 'Menlo', monospace;
}
```

**Einbindung (in Production: self-hosten, kein Google-Fonts-CDN aus Datenschutzgründen):**

```html
<!-- Development -->
<link href="https://fonts.googleapis.com/css2?family=Lexend+Deca:wght@300;400;500;600&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">

<!-- Production: self-hosted aus /public/fonts/ -->
```

### Type-Skala

| Element          | Font         | Weight | Size                         | Line | Tracking | Farbe          |
|------------------|--------------|--------|------------------------------|------|----------|----------------|
| H1 / Display     | Lexend Deca  | 500    | clamp(2.5rem, 5vw, 3.5rem)   | 1.1  | -0.02em  | text-primary   |
| H2 / Section     | Lexend Deca  | 500    | 2rem                         | 1.2  | -0.015em | text-primary   |
| H3 / Subsection  | Lexend Deca  | 500    | 1.5rem                       | 1.3  | -0.01em  | text-primary   |
| H4 / Card-Title  | Lexend Deca  | 500    | 1.125rem                     | 1.4  | 0        | text-primary   |
| Body Large       | Inter        | 400    | 1.0625rem                    | 1.6  | 0        | text-primary   |
| Body             | Inter        | 400    | 1rem                         | 1.6  | 0        | text-primary   |
| Body Small       | Inter        | 400    | 0.875rem                     | 1.5  | 0        | text-secondary |
| Meta / Caption   | Inter        | 500    | 0.8125rem                    | 1.4  | 0.01em   | text-meta      |
| Label / Eyebrow  | Inter        | 600    | 0.6875rem                    | 1.2  | 0.08em   | text-meta      |
| Mono Timestamp   | JetBrains    | 500    | 0.8125rem                    | 1.2  | 0        | text-meta      |
| Mono Speaker     | JetBrains    | 500    | 0.8125rem                    | 1.4  | 0.02em   | gold           |

**Detail-Regeln:**
- Labels UPPERCASE: `MEETING DETAILS`, `ZUSAMMENFASSUNG`
- Speaker-Labels UPPERCASE: `MÜLLER`, `SCHMIDT`
- Timestamps mit eckigen Klammern: `[00:14:32]`
- `text-wrap: balance` für alle Headlines
- `text-wrap: pretty` für Body-Absätze

---

## 4. Spacing & Layout

### 8px-Grid

```css
:root {
  --space-1:   0.25rem;  /*  4px */
  --space-2:   0.5rem;   /*  8px */
  --space-3:   0.75rem;  /* 12px */
  --space-4:   1rem;     /* 16px */
  --space-6:   1.5rem;   /* 24px */
  --space-8:   2rem;     /* 32px */
  --space-12:  3rem;     /* 48px */
  --space-16:  4rem;     /* 64px */
  --space-24:  6rem;     /* 96px */
  --space-32:  8rem;     /* 128px */
}
```

### Container

- Mobile: 100%, 24px Outer-Padding
- Tablet (≥768px): 100%, 48px Outer-Padding
- Desktop (≥1024px): max 1280px zentriert, 64px Outer-Padding
- Reading-Width (lange Texte): max 720px

### Border-Radius

```css
:root {
  --radius-sm:   4px;   /* Inputs, Pills */
  --radius-md:   6px;   /* Buttons */
  --radius-lg:   8px;   /* Cards */
  --radius-xl:  12px;   /* Modals */
  --radius-full: 9999px; /* Avatars, Badges */
}
```

**Niemals super-rund.** Dezent.

### Schatten

```css
:root {
  --shadow-xs:   0 1px 2px  rgba(10, 10, 10, 0.04);
  --shadow-sm:   0 2px 4px  rgba(10, 10, 10, 0.05);
  --shadow-md:   0 4px 12px rgba(10, 10, 10, 0.06);
  --shadow-lg:   0 8px 24px rgba(10, 10, 10, 0.08);
  --shadow-gold: 0 4px 16px rgba(201, 169, 97, 0.15); /* nur Recording-Button */
}
```

Schatten sind so subtil, dass sie fast unsichtbar wirken — sie tragen das Premium-Gefühl ohne aufdringlich zu sein.

---

## 5. Komponenten

### Buttons

**Primary** (Standard-Aktion)
```css
.btn-primary {
  background: var(--black);
  color: var(--white);
  padding: 12px 24px;
  border-radius: var(--radius-md);
  font: 500 0.9375rem var(--font-body);
  transition: background 150ms ease;
}
.btn-primary:hover { background: #1F1F1F; }
.btn-primary:active { background: #2A2A2A; }
.btn-primary:disabled { background: var(--text-disabled); cursor: not-allowed; }
```

**Secondary**
```css
.btn-secondary {
  background: var(--white);
  color: var(--text-primary);
  border: 1px solid var(--border-strong);
  padding: 12px 24px;
  border-radius: var(--radius-md);
  font: 500 0.9375rem var(--font-body);
}
.btn-secondary:hover {
  background: var(--surface-soft);
  border-color: var(--text-secondary);
}
```

**Tertiary** (Text-Link)
```css
.btn-tertiary {
  background: transparent;
  color: var(--text-primary);
  padding: 8px 12px;
  font: 500 0.9375rem var(--font-body);
  text-decoration: none;
}
.btn-tertiary:hover { text-decoration: underline; text-decoration-thickness: 1px; text-underline-offset: 4px; }
```

**Recording-Button** (Spezialfall, einziges Gold-Element)
```css
.btn-record {
  background: var(--white);
  color: var(--text-primary);
  border: 2px solid var(--gold);
  width: 96px;
  height: 96px;
  border-radius: var(--radius-full);
  box-shadow: var(--shadow-gold);
  font: 600 0.875rem var(--font-mono);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.btn-record.recording {
  background: var(--gold);
  color: var(--white);
  animation: pulse-gold 2s ease-in-out infinite;
}
@keyframes pulse-gold {
  0%, 100% { box-shadow: 0 0 0 0 rgba(201, 169, 97, 0.4); }
  50% { box-shadow: 0 0 0 16px rgba(201, 169, 97, 0); }
}
```

### Inputs

```css
.input {
  background: var(--white);
  color: var(--text-primary);
  border: 1px solid var(--border-strong);
  padding: 10px 14px;
  border-radius: var(--radius-sm);
  font: 400 0.9375rem var(--font-body);
  transition: border-color 150ms ease;
}
.input:focus {
  outline: none;
  border-color: var(--black);
  /* KEIN farbiger Glow — clean focus */
}
.input::placeholder { color: var(--text-disabled); }
```

### Meeting-Liste (PLAUD-Style)

```
Liste = flache vertikale Sequenz, KEINE Cards.
Pro Eintrag: dünne Bottom-Border (border-subtle).
Padding: 16px vertikal, 24px horizontal.
Layout:
  ┌──────────────────────────────────────────────┐
  │ Titel                              [00:42:15]│
  │ Mo, 12. Mai · 11:30 Uhr · 3 Sprecher          │
  └──────────────────────────────────────────────┘

Titel:    Inter 500, 1rem, text-primary
Meta:     Inter 400, 0.8125rem, text-meta
Dauer:    JetBrains Mono 500, 0.8125rem, text-meta
Hover:    background: var(--surface-soft)
Selected: 2px gold left-border + background: var(--gold-faint)
```

### Card

```css
.card {
  background: var(--white);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
  padding: var(--space-6);
  box-shadow: var(--shadow-xs);
}
.card-header {
  border-bottom: 1px solid var(--border-subtle);
  padding-bottom: var(--space-4);
  margin-bottom: var(--space-4);
}
```

**Card-Verwendung:** Nur in Detailviews und Settings. Auf Listen-Screens: keine Cards (PLAUD-Pattern).

### Tabs

```css
.tabs {
  display: flex;
  border-bottom: 1px solid var(--border-subtle);
  gap: 0;
}
.tab {
  padding: 12px 20px;
  font: 500 0.9375rem var(--font-body);
  color: var(--text-meta);
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
  transition: all 150ms ease;
}
.tab:hover { color: var(--text-primary); }
.tab[aria-selected="true"] {
  color: var(--text-primary);
  border-bottom-color: var(--black); /* schwarz, nicht gold */
}
```

### Speaker-Block (im Transkript)

```
[00:14:32]   MÜLLER
             Wir sollten bei der nächsten Sitzung das Thema
             Risikoabsicherung intensiver besprechen.

[00:14:48]   SCHMIDT
             Einverstanden. Ich bringe den aktuellen Stand mit.

Timestamp:   JetBrains Mono 500, 0.8125rem, text-meta
Speaker:     JetBrains Mono 500, 0.8125rem, gold, UPPERCASE
Text:        Inter 400, 1rem, text-primary, line-height 1.6
Indent:      Text um 80px eingerückt, damit Speaker links steht
```

### Status-Pills (sparsam einsetzen)

```css
.pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: var(--radius-full);
  font: 500 0.75rem var(--font-body);
  background: var(--surface-soft);
  color: var(--text-secondary);
}
.pill-recording {
  background: rgba(200, 74, 63, 0.08);
  color: var(--recording);
}
.pill-recording::before {
  content: '';
  width: 6px; height: 6px;
  border-radius: var(--radius-full);
  background: var(--recording);
  animation: blink 1s ease-in-out infinite;
}
```

---

## 6. Die Identitäts-Kante: Gold-Linie

**DAS visuelle Signature-Element des Produkts.**

Wenn eine Aufnahme läuft, erscheint am oberen Bildschirmrand der PWA (oder unter dem Tab in einer Detail-View) eine 1px hohe goldene Linie, die sanft pulsiert.

```css
.recording-indicator {
  position: fixed;
  top: 0; left: 0; right: 0;
  height: 1px;
  background: var(--gold);
  animation: pulse-line 2.4s ease-in-out infinite;
  z-index: 1000;
  pointer-events: none;
}
@keyframes pulse-line {
  0%, 100% { opacity: 0.4; }
  50% { opacity: 1; }
}
```

Subtil, sofort lesbar, edel — der Premium-Moment der App.

---

## 7. Bewegung & Mikrointeraktion

**Philosophie:** Animationen sind funktional, nie dekorativ.

```css
:root {
  --ease-out: cubic-bezier(0.16, 1, 0.3, 1);
  --ease-in-out: cubic-bezier(0.4, 0, 0.2, 1);
  --duration-fast: 150ms;
  --duration-medium: 250ms;
  --duration-slow: 400ms;
}
```

**Wo Animation eingesetzt wird:**
- Hover-States: 150ms ease
- Page-Transitions: 250ms ease-out (Slide-Fade)
- Modal-Erscheinen: 250ms ease-out (Scale + Fade)
- Recording-Pulse: 2-2.4s ease-in-out
- Skeleton-Loader bei Datenladen

**Wo NICHT:**
- Keine Parallax-Effekte
- Keine Scroll-getriggerten Reveals
- Keine "AI-Sparkles" oder Glitter-Animationen
- Keine Bouncing-Buttons
- Keine Page-Load-Choreographien

---

## 8. Icons

**Lucide React** als einzige Icon-Library.

**Verwendung:**
- 18-20px für UI-Icons in Buttons/Toolbars
- 24px für Navigationsicons
- 32px für Empty-States
- 1.5px stroke-width (Lucide-Default)
- Farbe: `currentColor` (erbt vom Parent)

**Welche Icons:**
- Funktional, nicht dekorativ
- Niemals neben jedem Listen-Eintrag
- Niemals mehrere Icons direkt nebeneinander (außer in Toolbars)

---

## 9. Anti-Patterns

❌ Lila-Farben oder lila Gradients
❌ Glassmorphism / Frosted-Glass-Effekte
❌ Neumorphism (problematisch für Accessibility)
❌ Tech-Blau als Primary-Farbe
❌ Fette Marketing-Headlines ("Revolutioniere Deine Meetings!")
❌ Emojis in der UI
❌ Card-in-Card-Verschachtelungen
❌ Bouncing-Animations
❌ Hero-Sections mit animierten Mesh-Gradients
❌ Status-Pills für jede Kleinigkeit
❌ "AI-Sparkles" / animierte Glitter-Effekte
❌ Custom-Cursors
❌ Skewed/Diagonale Layouts
❌ Tab-Bars mit Icons UND Text bei wenig Platz

---

## 10. Mobile-First-Regeln

Da die PWA primär auf Smartphones läuft:

- **Touch-Targets:** mindestens 44×44px
- **Bottom-Navigation** statt Sidebar bei <768px
- **Safe-Areas** beachten: `padding-bottom: env(safe-area-inset-bottom)`
- **Keine Hover-Only-Interaktionen** — alles muss per Tap erreichbar sein
- **Pull-to-Refresh** für Listen
- **Swipe-Gesten** für Meeting-Aktionen (Archivieren, Löschen)

---

## 11. Tailwind-Konfiguration

```typescript
// tailwind.config.ts
import type { Config } from "tailwindcss";

export default {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        white: "#FFFFFF",
        black: "#0A0A0A",
        gold: {
          DEFAULT: "#C9A961",
          light: "#E6D4A3",
          deep: "#9C8147",
          faint: "#F5EDD9",
        },
        surface: {
          soft: "#FAFAF7",
          warm: "#F5F3EE",
        },
        border: {
          subtle: "#E8E6E1",
          strong: "#D4D1CA",
        },
        text: {
          primary: "#0A0A0A",
          secondary: "#4A4842",
          meta: "#737065",
          disabled: "#A8A599",
        },
        recording: "#C84A3F",
      },
      fontFamily: {
        display: ["Lexend Deca", "sans-serif"],
        body: ["Inter", "sans-serif"],
        mono: ["JetBrains Mono", "monospace"],
      },
      boxShadow: {
        xs: "0 1px 2px rgba(10, 10, 10, 0.04)",
        sm: "0 2px 4px rgba(10, 10, 10, 0.05)",
        md: "0 4px 12px rgba(10, 10, 10, 0.06)",
        lg: "0 8px 24px rgba(10, 10, 10, 0.08)",
        gold: "0 4px 16px rgba(201, 169, 97, 0.15)",
      },
    },
  },
} satisfies Config;
```

---

## 12. Aktivierte Claude-Code-Skills

```yaml
skills:
  - frontend-design       # Anthropic offiziell
  - UI/UX Pro Max         # nextlevelbuilder Community-Skill
```

**Wichtige Anweisung an Claude Code:**

Folge dem Designsystem strikt. Nicht von dem in `frontend-design` empfohlenen "distinctiven Fonts" abweichen — Lexend Deca + Inter sind hier eine bewusste, kontextspezifische Entscheidung (HubSpot-Referenz, deutsche B2B-Lesbarkeit, Vertrauen). Erfinde keine eigenen Farben oder Schriften. Nutze ausschließlich die Tokens aus diesem Dokument.

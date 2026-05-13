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
  --surface-soft: #FAFAF7;
  --surface-warm: #F5F3EE;

  /* Borders */
  --border-subtle: #E8E6E1;
  --border-strong: #D4D1CA;

  /* Text-Hierarchie */
  --text-primary:   #0A0A0A;
  --text-secondary: #4A4842;
  --text-meta:      #737065;
  --text-disabled:  #A8A599;

  /* Gold-Varianten */
  --gold-light: #E6D4A3;
  --gold-deep:  #9C8147;
  --gold-faint: #F5EDD9;

  /* Status */
  --recording: #C84A3F;
  --success:   #4A7C59;
  --warning:   #B8893C;
  --error:     #A33A2F;
}
```

### Gold-Regel

**Gold ausschließlich für:**
- Pulsierenden Aufnahme-Indikator (1px-Linie oben)
- Speaker-Labels in Transkripten
- Selected-State in Listen (2px Links-Border)
- Highlighted Werte in Statistiken
- Logo

**Gold NIEMALS für:**
- Primäre Buttons (die sind schwarz)
- Großflächige Hintergründe
- Mehr als 2-3 Stellen pro Viewport
- Body-Text

**Begründung:** Gold trägt nur, wenn es selten ist. Selten = Premium.

---

## 3. Typografie

```css
:root {
  --font-display: 'Lexend Deca', sans-serif;
  --font-body:    'Inter', sans-serif;
  --font-mono:    'JetBrains Mono', monospace;
}
```

**In Production: self-hosted, kein Google-Fonts-CDN** (DSGVO).

### Type-Skala

| Element          | Font         | Weight | Size                         | Line | Tracking |
|------------------|--------------|--------|------------------------------|------|----------|
| H1 / Display     | Lexend Deca  | 500    | clamp(2.5rem, 5vw, 3.5rem)   | 1.1  | -0.02em  |
| H2 / Section     | Lexend Deca  | 500    | 2rem                         | 1.2  | -0.015em |
| H3 / Subsection  | Lexend Deca  | 500    | 1.5rem                       | 1.3  | -0.01em  |
| H4 / Card-Title  | Lexend Deca  | 500    | 1.125rem                     | 1.4  | 0        |
| Body Large       | Inter        | 400    | 1.0625rem                    | 1.6  | 0        |
| Body             | Inter        | 400    | 1rem                         | 1.6  | 0        |
| Body Small       | Inter        | 400    | 0.875rem                     | 1.5  | 0        |
| Meta / Caption   | Inter        | 500    | 0.8125rem                    | 1.4  | 0.01em   |
| Label / Eyebrow  | Inter        | 600    | 0.6875rem                    | 1.2  | 0.08em   |
| Mono Timestamp   | JetBrains    | 500    | 0.8125rem                    | 1.2  | 0        |
| Mono Speaker     | JetBrains    | 500    | 0.8125rem                    | 1.4  | 0.02em   |

**Detail-Regeln:**
- Labels UPPERCASE: `MEETING DETAILS`, `ZUSAMMENFASSUNG`
- Speaker UPPERCASE: `MÜLLER`, `SCHMIDT`
- Timestamps: `[00:14:32]`
- `text-wrap: balance` für Headlines
- `text-wrap: pretty` für Body

---

## 4. Spacing & Layout

### 8px-Grid

```css
:root {
  --space-1:   0.25rem;
  --space-2:   0.5rem;
  --space-3:   0.75rem;
  --space-4:   1rem;
  --space-6:   1.5rem;
  --space-8:   2rem;
  --space-12:  3rem;
  --space-16:  4rem;
  --space-24:  6rem;
  --space-32:  8rem;
}
```

### Container

- Mobile: 100%, 24px Outer-Padding
- Tablet (≥768px): 100%, 48px Outer-Padding
- Desktop (≥1024px): max 1280px, 64px Padding
- Reading-Width (Transkripte): max 720px

### Border-Radius

```css
:root {
  --radius-sm:   4px;
  --radius-md:   6px;
  --radius-lg:   8px;
  --radius-xl:  12px;
  --radius-full: 9999px;
}
```

**Niemals super-rund.**

### Schatten

```css
:root {
  --shadow-xs:   0 1px 2px  rgba(10, 10, 10, 0.04);
  --shadow-sm:   0 2px 4px  rgba(10, 10, 10, 0.05);
  --shadow-md:   0 4px 12px rgba(10, 10, 10, 0.06);
  --shadow-lg:   0 8px 24px rgba(10, 10, 10, 0.08);
  --shadow-gold: 0 4px 16px rgba(201, 169, 97, 0.15);
}
```

---

## 5. Komponenten

### Buttons

**Primary** (Standard-Aktion — schwarz, nicht gold)
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
```

**Secondary**
```css
.btn-secondary {
  background: var(--white);
  color: var(--text-primary);
  border: 1px solid var(--border-strong);
  padding: 12px 24px;
  border-radius: var(--radius-md);
}
```

**Recording-Button** (einziges Gold-Element)
```css
.btn-record {
  background: var(--white);
  border: 2px solid var(--gold);
  width: 96px;
  height: 96px;
  border-radius: var(--radius-full);
  box-shadow: var(--shadow-gold);
}
.btn-record.recording {
  background: var(--gold);
  color: var(--white);
  animation: pulse-gold 2s ease-in-out infinite;
}
```

### Meeting-Liste (PLAUD-Style)

```
Flache vertikale Sequenz, KEINE Cards.
Pro Eintrag: dünne Bottom-Border (border-subtle).
Padding: 16px vertikal, 24px horizontal.

  ┌──────────────────────────────────────────────┐
  │ Titel                              [00:42:15]│
  │ Mo, 12. Mai · 11:30 Uhr · 3 Sprecher          │
  └──────────────────────────────────────────────┘

Hover:    background: surface-soft
Selected: 2px gold left-border + background: gold-faint
```

### Card (nur in Detailviews)

```css
.card {
  background: var(--white);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
  padding: var(--space-6);
  box-shadow: var(--shadow-xs);
}
```

### Speaker-Block (im Transkript)

```
[00:14:32]   MÜLLER
             Wir sollten bei der nächsten Sitzung das Thema
             Risikoabsicherung intensiver besprechen.

Timestamp:   JetBrains Mono 500, 0.8125rem, text-meta
Speaker:     JetBrains Mono 500, 0.8125rem, GOLD, UPPERCASE
Text:        Inter 400, 1rem, text-primary
Indent:      Text 80px eingerückt
```

---

## 6. Die Identitäts-Kante: Gold-Linie

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

## 7. Bewegung

```css
:root {
  --ease-out: cubic-bezier(0.16, 1, 0.3, 1);
  --duration-fast: 150ms;
  --duration-medium: 250ms;
}
```

**Wo Animation:**
- Hover-States, Page-Transitions, Modal-Erscheinen, Skeleton-Loader
- Recording-Pulse

**Wo NICHT:**
- Keine Parallax, keine Scroll-Reveals, keine AI-Sparkles, keine Bouncing-Buttons

---

## 8. Anti-Patterns

❌ Lila, Tech-Blau, Gradients
❌ Glassmorphism, Neumorphism
❌ Fette Marketing-Headlines
❌ Emojis in der UI
❌ Card-in-Card
❌ Animierte Mesh-Gradients
❌ Status-Pills für jede Kleinigkeit
❌ AI-Sparkles, Glitter-Effekte

---

## 9. Mobile-First-Regeln

- Touch-Targets ≥ 44×44px
- Bottom-Navigation bei <768px
- `padding-bottom: env(safe-area-inset-bottom)`
- Keine Hover-Only-Interaktionen
- Pull-to-Refresh für Listen
- Swipe-Gesten für Meeting-Aktionen

---

## 10. Tailwind-Konfiguration

Siehe `frontend/tailwind.config.ts` — Tokens werden dort 1:1 abgebildet.

---

## 11. Aktivierte Claude-Code-Skills

```yaml
skills:
  - frontend-design       # Anthropic offiziell
  - UI/UX Pro Max         # Community-Skill
```

**Wichtig:** Folge dem Designsystem strikt. Lexend + Inter sind bewusste, kontextspezifische Wahl (HubSpot-Referenz, B2B-Lesbarkeit, Vertrauen). Nicht von `frontend-design`-Default abweichen.

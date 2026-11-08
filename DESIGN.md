---
name: OneMoreTime
description: Nordic daylight listening desk — personal music on Yandex Disk
colors:
  linen-field: "#e7edf2"
  linen-elev: "#f7f9fb"
  wash-cool: "#dfe8ef"
  wash-mist: "#eef3f7"
  slate-ink: "#182433"
  slate-muted: "#5a6b7c"
  teal-signal: "#0f7f78"
  teal-deep: "#0c6c66"
  teal-ink: "#f4fffd"
  teal-soft: "rgba(15, 127, 120, 0.12)"
  line: "rgba(24, 36, 51, 0.12)"
  line-strong: "rgba(24, 36, 51, 0.22)"
  danger: "#b42318"
typography:
  display:
    fontFamily: "Syne, \"Avenir Next\", sans-serif"
    fontSize: "clamp(2.35rem, 5.5vw, 3.6rem)"
    fontWeight: 800
    lineHeight: 0.95
    letterSpacing: "-0.035em"
  headline:
    fontFamily: "Syne, \"Avenir Next\", sans-serif"
    fontSize: "clamp(1.65rem, 3vw, 2.15rem)"
    fontWeight: 700
    letterSpacing: "-0.03em"
  title:
    fontFamily: "Syne, \"Avenir Next\", sans-serif"
    fontSize: "1.2rem"
    fontWeight: 700
    letterSpacing: "-0.02em"
  body:
    fontFamily: "Figtree, \"Segoe UI\", sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.45
  label:
    fontFamily: "Figtree, \"Segoe UI\", sans-serif"
    fontSize: "0.85rem"
    fontWeight: 500
rounded:
  control: "0.45rem"
spacing:
  space: "1.25rem"
  shell-pad-x: "clamp(1rem, 3vw, 2rem)"
  main-max: "1120px"
  player-h: "5.75rem"
components:
  button-primary:
    backgroundColor: "{colors.teal-signal}"
    textColor: "{colors.teal-ink}"
    rounded: "{rounded.control}"
    padding: "0.55rem 0.95rem"
    typography: "{typography.body}"
  button-primary-hover:
    backgroundColor: "{colors.teal-deep}"
    textColor: "{colors.teal-ink}"
    rounded: "{rounded.control}"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.slate-ink}"
    rounded: "{rounded.control}"
    padding: "0.55rem 0.95rem"
  input-field:
    backgroundColor: "{colors.linen-elev}"
    textColor: "{colors.slate-ink}"
    rounded: "{rounded.control}"
    padding: "0.65rem 0.8rem"
  nav-underline:
    backgroundColor: "transparent"
    textColor: "{colors.slate-muted}"
    padding: "0.4rem 0.55rem"
  nav-underline-active:
    backgroundColor: "transparent"
    textColor: "{colors.slate-ink}"
  tree-play:
    backgroundColor: "{colors.linen-elev}"
    textColor: "{colors.teal-signal}"
    rounded: "{rounded.control}"
    width: "1.85rem"
    height: "1.85rem"
  player-play:
    backgroundColor: "{colors.teal-signal}"
    textColor: "{colors.teal-ink}"
    rounded: "{rounded.control}"
    width: "2.85rem"
    height: "2.85rem"
---

# Design System: OneMoreTime

## Overview

**Creative North Star: "Nordic daylight listening desk"**

Light, linen-cool field with slate ink and a single teal signal. The shell reads as a calm desk for listening — brand is oversized and primary; chrome stays quiet so playback stays first. Atmosphere is soft wash + paper grain, never neon glow or dark-mode default.

Density is medium-loose: generous shell padding, underline navigation, nested library tree, sticky bottom player. Motion is purposeful and sparse (brand rise, view enter, player slide-up, subtle track hover).

**Key Characteristics:**
- Light `color-scheme`; teal accent on ~small fraction of UI
- Display Syne for brand / section / genre; Figtree for body and controls
- Underline nav and view-mode toggles (no pill clusters)
- Soft tonal panels + hairline borders; almost no drop shadows
- Fixed bottom player; library as expandable tree with inline play

**Visual rejections (shipped):** dark neon default, purple/indigo AI cliché gradients, glow effects, rounded-full pills, multi-layer shadows, emoji decoration.

## Colors

Cool linen neutrals with one teal accent and slate ink. Source of truth: `:root` in `static/css/app.css`.

### Primary
- **Teal Signal** (`#0f7f78`): primary buttons, active view-mode, play control fill, favorites on, accent hover fills, seek accent-color.
- **Teal Deep** (`#0c6c66`): primary button hover.
- **Teal Ink** (`#f4fffd`): text/icon on teal fills.
- **Teal Soft** (`rgba(15, 127, 120, 0.12)`): hover washes on tracks, tree rows, ghost button hover.

### Neutral
- **Linen Field** (`#e7edf2`): page background.
- **Linen Elev** (`#f7f9fb`): elevated panels, inputs, player base, tree-play resting fill.
- **Wash Cool / Mist** (`#dfe8ef`, `#eef3f7`): atmosphere gradient stops (not interactive chrome).
- **Slate Ink** (`#182433`): primary text and brand.
- **Slate Muted** (`#5a6b7c`): secondary text, nav idle, track numbers.
- **Line / Line Strong** (`rgba(24, 36, 51, 0.12|0.22)`): dividers and control borders.
- **Danger** (`#b42318`): error emphasis (rare).

### Named Rules
**The One Signal Rule.** Teal is the only accent; use it for action and “now,” not decoration.

**The Light Desk Rule.** Stay in light linen/slate; do not flip the product to a dark neon skin.

## Typography

**Display Font:** Syne (fallback Avenir Next, sans-serif) — weights 600–800 via Google Fonts  
**Body Font:** Figtree (fallback Segoe UI, sans-serif) — weights 400–700  

**Character:** Syne carries the brand and section hierarchy with tight tracking; Figtree keeps reading and controls calm and legible.

### Hierarchy
- **Display / Brand** (800, `clamp(2.35rem, 5.5vw, 3.6rem)`, lh 0.95): `.brand` — hero product name in the shell.
- **Headline** (700, `clamp(1.65rem, 3vw, 2.15rem)`): `.section-head h1`.
- **Title / Genre** (700, ~1.2rem): `.tree-genre` labels.
- **Body** (400, inherit ~1rem, lh 1.45): default UI copy; max useful width ~40rem on section intros.
- **Label** (500–600, ~0.85–0.95rem): nav, view-mode, muted meta, track-sub.

### Named Rules
**The Brand-First Type Rule.** No page headline should overpower the `OneMoreTime` brand block in the first shell.

## Layout

Shell header is a three-column grid (brand | nav | auth) with `clamp` horizontal padding; collapses to a single column under 900px. Main content centers at `max-width: 1120px`. Body reserves bottom space for the sticky player (`--player-h: 5.75rem` + padding).

Library is a nested `<details>` tree (genre → artist → album → track, or shorter modes). Tracks are a four-column grid: number | meta | favorite | extra. Player is a four-column sticky footer; stacks to one column under 820px.

Spacing rhythm uses `--space` (1.25rem) and small gaps (0.2–0.75rem) rather than a large card grid.

### Named Rules
**The Phone-Equals-Desktop Rule.** Same composition on narrow screens — stack shell and player; do not hide listening chrome.

## Elevation & Depth

Depth is tonal and atmospheric, not shadowed. Surfaces sit on linen elev / soft color-mix translucency; atmosphere wash + SVG grain sit behind content (`z-index: 0`). Borders carry structure. Focus uses a teal ring (`0 0 0 3px rgba(15, 127, 120, 0.35)`), not a glow bloom.

### Shadow Vocabulary
- **None at rest.** No ambient drop-shadow system on panels or cards.
- **Focus ring only** (`box-shadow: var(--focus)`): keyboard focus on interactive controls.

### Named Rules
**The Flat Desk Rule.** Prefer border + tonal fill over multi-layer shadows.

## Shapes

Single control radius `--radius: 0.45rem` (~7px) on buttons, inputs, tree rows, panels, player controls. Navigation and view-mode use square underline tabs (`border-radius: 0`). No pill/`rounded-full` chips. Tree children indent with a left hairline.

### Named Rules
**The Soft Square Rule.** Slightly rounded rectangles for controls; underlines for wayfinding — not capsules.

## Components

### Buttons
- **Shape:** soft square (`0.45rem`)
- **Primary (`.btn`):** teal fill, teal-ink text, weight 600; hover lifts 1px and deepens teal
- **Ghost (`.btn-ghost`):** transparent + strong line border; hover teal-soft wash
- **Focus:** shared teal focus ring

### View-mode / Nav “chips”
Not pills — underline toggles (`.nav-btn`, `.view-mode-btn`). Idle muted; active ink/teal with 2px teal underline.

### Cards / Containers
- **Panels (`.panel`, banners):** linen-elev, 1px line border, `0.45rem` radius, ~1rem padding — used for import/job detail, not as a hero card grid
- **No marketing card deck** in the listening shell

### Inputs / Fields
- Linen-elev fill, strong line border, same radius, comfortable padding
- File pickers use dashed border labels
- Focus: teal ring

### Navigation
- Top underline nav in the shell; legal as text link
- Auth cluster: label + primary/ghost actions (login / switch / logout)

### Library tree (signature)
- Nested disclosure rows with ▸/▾ marker, play square, label, count
- Genre labels use display type; albums quieter/muted
- Hover wash teal-soft; tree-play flips to teal fill on hover
- Left spine border on nested children

### Track row
- Hover: teal-soft + 2px translateX
- Playing: teal-soft + soft teal border mix
- Unavailable: reduced opacity
- Favorite heart toggles muted → teal

### Player (signature)
- Fixed bottom bar, elevated linen mix, top strong line
- Grid: now-playing | controls | seek | rate
- Play is larger teal square; other controls bordered linen squares; pressed state fills teal
- Entrance: `player-up` slide from below

### Atmosphere (signature)
- Fixed full-bleed wash (teal + cool blue radials over linen gradient) + soft fractal grain at 0.45 opacity
- Non-interactive; content shells sit above

## Do's and Don'ts

### Do:
- **Do** keep `OneMoreTime` as the oversized Syne brand signal in the shell.
- **Do** use teal only for primary actions, active state, and “now playing” cues.
- **Do** prefer underline nav / view modes over pill clusters.
- **Do** preserve the sticky player and library tree patterns when extending features.
- **Do** keep light linen + slate; match `--radius: 0.45rem` and Figtree/Syne pairing.

### Don't:
- **Don't** reintroduce dark neon, purple-indigo gradients, or glow/bloom accents.
- **Don't** use `rounded-full` pills, emoji ornament, or multi-layer card shadows.
- **Don't** put the Disk OAuth token or secrets in client-visible UI chrome.
- **Don't** invent a second visual world on top of this desk — extend the incumbent tokens.

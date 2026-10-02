# Modrn Magic design system

The site is plain HTML and one stylesheet (`assets/css/site.css`). No framework, no CSS build, no runtime CDN. Every value below exists as a CSS custom property on `:root`; use the token, not the raw value.

The direction is Arc-inspired: soft color behind frosted surfaces, generous rounding, calm density, and motion that explains what changed. Products carry their own color; the studio chrome stays neutral.

## Principles

1. Products first. The chrome is quiet so each app's icon, color, and screenshots do the talking.
2. Real material only. Real screenshots, real store facts. No mock UI, no invented numbers, no testimonials.
3. One accent. Coral from the Modrn mark (`--accent`) is the only studio accent. Product tints appear only inside that product's surfaces.
4. Content is in the HTML. Pages are readable with JavaScript off and by crawlers. JS adds polish only.
5. Fast by default. One font file, one CSS file, one small deferred JS file, lazy images with fixed dimensions.

## Color

Two themes. The page follows `prefers-color-scheme`; the toggle stores an override in `localStorage` and sets `data-theme` on `<html>`. Themes never flip per section.

| Token | Light | Dark | Use |
|---|---|---|---|
| `--bg` | `#eef0f4` | `#0c0d10` | Page canvas |
| `--wash-1..3` | mark hues at 10 to 16% alpha | same hues at 8 to 12% | Fixed radial washes behind glass |
| `--surface` | `rgb(255 255 255 / .62)` | `rgb(26 28 34 / .58)` | Glass cards and nav |
| `--surface-solid` | `#fafbfc` | `#16181d` | Fallback when blur is unavailable or reduced transparency is on |
| `--surface-sunk` | `rgb(20 24 34 / .04)` | `rgb(255 255 255 / .04)` | Chips, wells |
| `--line` | `rgb(20 24 34 / .09)` | `rgb(255 255 255 / .08)` | 1px borders |
| `--highlight` | `rgb(255 255 255 / .7)` | `rgb(255 255 255 / .08)` | Inner top edge on glass |
| `--ink` | `#14161b` | `#eceef3` | Headlines, body |
| `--ink-2` | `#474d59` | `#b0b5c0` | Secondary text |
| `--ink-3` | `#5f6674` | `#8f95a1` | Meta text (AA on `--bg` in both themes) |
| `--accent` | `#d9482a` | `#ff7d5c` | Links on hover, focus ring, primary button |
| `--accent-ink` | `#ffffff` | `#1a0d09` | Text on `--accent` |
| `--status-live` | `#1f8a4c` | `#5fd18f` | Status text only, never a decorative dot |
| `--status-lab` | `#8a5a00` | `#f0b44c` | |
| `--status-archived` | `--ink-3` | `--ink-3` | |

Product tint: each product sets `--tint` inline from `app.json` `color`. It is used for the icon tile, a soft gradient inside that product's card, and nothing else.

## Type

One family: Figtree (variable, 300 to 900, OFL, self-hosted at `assets/fonts/figtree-var.woff2`, `font-display: swap`). Numbers and metadata use `font-variant-numeric: tabular-nums`, not a second family.

| Token | Size | Weight | Tracking | Line height |
|---|---|---|---|---|
| `--t-display` | `clamp(2.5rem, 1.7rem + 3.4vw, 4.25rem)` | 650 | -0.035em | 1.02 |
| `--t-h1` | `clamp(2.25rem, 1.6rem + 2.6vw, 3.5rem)` | 650 | -0.03em | 1.05 |
| `--t-h2` | `clamp(1.75rem, 1.35rem + 1.6vw, 2.5rem)` | 620 | -0.025em | 1.1 |
| `--t-h3` | `1.25rem` | 600 | -0.01em | 1.3 |
| `--t-body` | `1.0625rem` | 420 | 0 | 1.6 |
| `--t-small` | `0.9375rem` | 450 | 0 | 1.5 |
| `--t-meta` | `0.8125rem` | 550 | 0.01em | 1.4 |

Rules: body copy max width `62ch`. Headlines use weight and color for hierarchy, not size alone. No uppercase eyebrows except one per page at most. Emphasis uses the same family (weight or `--ink-2` color), never a second font.

## Radius

One documented system:

| Token | Value | Applies to |
|---|---|---|
| `--r-pill` | `999px` | Every interactive control: buttons, nav pill, chips, toggles |
| `--r-card` | `22px` | Cards, bento cells, fact panels |
| `--r-sheet` | `32px` | Large hero panels and the footer sheet |
| `--r-shot` | `18px` | Screenshots (phone shots use `28px` to echo device corners) |
| `--r-icon` | `22.5%` | App icons, always, at any size |

## Space and layout

- 4px base: `--s-1` 4, `--s-2` 8, `--s-3` 12, `--s-4` 16, `--s-5` 24, `--s-6` 32, `--s-7` 48, `--s-8` 64, `--s-9` 96.
- Content width `--w-content: 1120px`; prose width `62ch`.
- Page gutter `clamp(16px, 4vw, 32px)`. At phone width it is 16px and nothing scrolls horizontally except deliberate screenshot rails.
- Section rhythm: `--s-9` on desktop, `--s-8` under 768px.
- Grids collapse to one column under 768px. Bento cells keep their order.

## Surfaces (glass)

```
background: var(--surface);
backdrop-filter: blur(22px) saturate(160%);
border: 1px solid var(--line);
box-shadow: inset 0 1px 0 var(--highlight), var(--shadow-1);
```

- `--shadow-1`: `0 1px 2px rgb(20 24 34 / .04), 0 8px 24px rgb(20 24 34 / .06)` light; deeper and neutral in dark.
- Fallback: when `backdrop-filter` is unsupported or `prefers-reduced-transparency: reduce`, surfaces use `--surface-solid`.
- Glass sits on the fixed wash layer only. Glass on glass is limited to the floating nav.
- This is web glassmorphism, an approximation. It is not Apple's Liquid Glass.

## Motion

| Token | Value | Use |
|---|---|---|
| `--d-fast` | `140ms` | Hover color, press |
| `--d-base` | `240ms` | Lift, chip, toggle |
| `--d-slow` | `520ms` | Reveal on scroll |
| `--ease-out` | `cubic-bezier(.2, .8, .2, 1)` | Default |
| `--ease-spring` | `cubic-bezier(.34, 1.4, .64, 1)` | Press release, icon pop |

What moves and why:

- Hover lift on cards (`translateY(-2px)`) and press (`scale(.98)`): feedback.
- Link hover: color and underline color ease over `--d-fast`, so the pointer reads as a response, not a flicker.
- Theme switch: the whole page cross-fades over `--d-slow` through a same-document view transition, and the new sun or moon icon pops in with `--ease-spring`. Browsers without the View Transitions API switch instantly.
- FAQ: the answer fades and settles 6px over `--d-base` on open and lifts out over `--d-fast` on close (`site.js` holds the close until the animation ends). The box height snaps on purpose: animating height is layout work, and the eye follows the text, not the box.
- Rail buttons: lift on hover, press to `scale(.94)`, fade to 40% when there is nowhere to go. The rail itself uses the browser's smooth scroll, whose curve the browser owns.
- Skip link: slides down from above the viewport with `--ease-spring` when focused.
- Reveal on scroll (opacity plus 12px rise, 50ms stagger, once): shows the order to read a section.
- Cross-page view transitions: the app icon morphs from the home card into the product page hero (`view-transition-name: icon-<id>`), so the user sees where they went. Progressive; browsers without the API just navigate.
- Hero screenshots settle in once on load.

Only `transform` and `opacity` animate, plus hover `color`, `background`, and `box-shadow` on controls (see the audit). No scroll-driven animation, no loops, no parallax; the rail's one passive scroll listener only updates its position readout. `prefers-reduced-motion: reduce` turns all of it off, including view transitions and the theme cross-fade.

Written exceptions: the focus ring appears instantly (focus must never lag), the rail position number changes instantly (it is a readout), and the hero settle uses 900ms with 120 and 220ms delays because it plays once per load and is meant to be slower than any interaction.

### Motion audit

Every state change on the site, checked 2026-10-02 on `site/studio-index`.

| State change | Motion | Status |
|---|---|---|
| Link hover (body, footer, crumbs, legal) | color, underline color, `--d-fast` | Done |
| Nav link, shelf row, "more" link, founder link hover | background and color, `--d-fast` | Done, see open item 1 |
| Button and bento cell hover and press | lift and spring press, `--d-base`; shadow `--d-base` | Done, see open item 1 |
| Bento arrow and peek | transform, `--d-base` | Done |
| Theme toggle hover and press | background, `scale(.94)`, `--d-fast` | Done |
| Theme switch | page cross-fade `--d-slow`, icon pop `--d-base` | Done |
| FAQ open and close | answer opacity and transform, `--d-base` in, `--d-fast` out | Done, height snaps by design |
| Rail previous and next | button lift and press; smooth scroll | Done |
| Section reveal | opacity and 12px rise, `--d-slow`, 50ms stagger | Done |
| Hero settle | 900ms once per load | Written exception |
| Page-to-page view transition | `--d-base` root fade, `--d-slow` icon morph | Done |
| Skip link | slide, `--d-base` spring | Done |
| Focus ring | instant | Written exception |

Open items:

1. `LANGUAGE.md` allows only transform and opacity, but hover backgrounds, colors, and button and cell shadows animate here, and its own token table lists "hover color" for `--d-fast`. Needs a studio call: allow color, background, and shadow on hover, or replace them with opacity layers.
2. The 50ms reveal stagger and the hero settle timings are raw values, not tokens.
3. No screen recording of the motion yet; timings were checked in code and by tests, not watched by a reviewer.

## Components

- Nav: floating glass pill, one line, 56px tall, sticky. Mark, name, three links, theme toggle. Under 640px the links shorten; no hamburger needed.
- Buttons: pill. Primary is `--accent` fill with `--accent-ink`. Secondary is glass with `--ink`. One label per intent per page ("Email the studio" is the only contact label).
- Store buttons: pill buttons with the store name in text. Only rendered when a live store link exists. Archived apps show "Was on" as plain text.
- Status: text label with color (`Live`, `In the lab`, `Archived`). No dots.
- Screenshot rail: horizontal scroll-snap row, native scrolling, visible edge fade, keyboard focusable. Below it, previous and next pill buttons (44px) and an "n of N" readout; `site.js` shows them only when the rail overflows, so without JavaScript there are no dead buttons. Framed shots (images that already include the device) drop the card border and use a drop shadow. Built by `rail_html()` in `render.py`.
- Legal page: breadcrumb, title, one glass card with the policy text (68ch), and a sticky side card with the support address and related legal links. Rendered from the Markdown next to the page.
- Product site (`apps/<id>/home/`): the store-facing page for one product, from `home/descriptions.json`: hero with framed phones, a tour rail with captions, the product's features, and a closing band with the legal links.
- Facts panel: definition list in a card, two columns on desktop.

## Data

Products live in `apps/<id>/app.json`, listed in order by `apps/index.json`. `_scripts/render.py` turns them into the home page, product pages, sitemap, llms.txt, and JSON-LD. Edit the JSON, run the script, commit the output. See `_docs/APPS.md`.

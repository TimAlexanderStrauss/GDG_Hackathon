# Sidequest design system

Applies to every screen in `web/`. Source of truth for tokens: `web/app/globals.css`.

## Personality

Energetic, friendly, exploratory. Strong typography, generous white space, and small playful details taken from the orange detour-arrow logo. Calm where trust matters: enrollment, consent, security.

Tagline: **Less scrolling. More going.**

## Brand assets

| File | Use |
|---|---|
| `public/sidequest-logo.svg` | Header logo (mark + wordmark), traced from the approved PNG |
| `public/sidequest-mark.svg` | Detour arrow alone: card corner detail, login hero |
| `app/icon.svg` | Favicon (the mark) |

Do not recolour, stretch or rotate the mark. On cards it sits whole in the top-right corner, 48px, in its original orientation.

## Tokens

| Token | Value | Use |
|---|---|---|
| `--es-bg`, `--es-surface` | `#FFFFFF` | Page background, cards |
| `--es-surface-2` | `#F5F6F8` | Secondary surface: discovery ground, insets, date badge |
| `--es-ink` | `#171717` | Primary text, focus ring, success text |
| `--es-muted` | `#596273` | Secondary text |
| `--es-line` | `#E4E7EC` | Borders |
| `--es-line-strong` | `#D0D5DD` | Hovered or secondary-button borders |
| `--es-accent` | `#FF5A36` | Brand orange: primary buttons, logo, highlights |
| `--es-accent-ink` | `#171717` | Text on orange (5.8:1). Never white on orange (3.1:1) |
| `--es-accent-soft` | `#FFE6DC` | Selected chips, "registered" status, soft notices |
| `--es-warn` / `-soft` | `#9A4D00` / `#FFF1DC` | Blocked posts (security), running scans |
| `--es-bad` / `-soft` | `#C0261A` / `#FDE8E6` | Errors |

There is no green in the palette. Success = charcoal text with a ✓ (Done), or orange-soft with a ✓ (Registered).

Flat fills only: no gradients, glows or textures. Backgrounds are white or cool grey.

## Type

Manrope (Google Fonts via `next/font`), fallback `system-ui, -apple-system, "Segoe UI", sans-serif`.

| Role | Size / weight |
|---|---|
| Page headline (h1) | 36–60px, 800, tracking −0.03em, `text-balance` |
| Section / card title | 20–24px, 800 |
| Body | 16px, 400–500 |
| Labels, buttons, chips | 14–16px, 600–700 |
| Meta, help text | 12–14px, muted |
| Audit log | system monospace, 12px |

## Spacing, shape, depth

- 8px rhythm (8, 16, 24, 32, 40…).
- Radii: cards 16px, inputs 12px, chips and buttons pill (999px), date badge 10px.
- Borders 1px `--es-line`. Shadow `0 1px 2px rgb(16 24 40 / 5%)` only.

## Components

| Component | Class / file | Notes |
|---|---|---|
| Primary button | `.btn .btn-primary` | Orange, charcoal text, 48px, pill. One per view section |
| Secondary button | `.btn .btn-secondary` | White, thin border |
| Small button | `+ .btn-sm` | 44px minimum |
| Chip | `.chip` (`.chip-lg` for interests) | `aria-pressed`; selected = `#FFE6DC` + ✓, charcoal text |
| Field | `.field` + `.label` | 48px, 12px radius, orange focus ring with soft halo, errors under the field |
| Card | `.panel` | White, 16px radius, thin border |
| Event card | `components/EventCards.tsx` | Date badge, source (real brand icon), title, venue, time · price, match reason, Enroll me |
| Activity | `components/Activity.tsx` | One status line near results; full audit in an expandable panel |
| Brand icons | `components/BrandIcon.tsx` | Real marks from `simple-icons` (CC0), own colours. Never draw look-alikes |

## Screens

1. **Sign in** (`AuthScreen`): grey ground. Headline + three trust points on the left, account card on the right. Provider buttons + email. Always labelled **Demo sign-in**.
2. **Add your socials** (`SocialsStep`): one card, list of networks with Connect → "✓ Added (demo)". Continue / Skip.
3. **Preferences** (`Onboarding`): centered, spacious. "Less scrolling. More going." → collapsible AI import ("Already told ChatGPT, Claude or Grok what you like?") → large interest chips → name, email, city, look-ahead → sources → consent → **Find my events**.
4. **Discovery** (`Dashboard`): grey ground. "Your next plan is out there." + interest chips + status line + cards + "Update interests" + Activity. The **Your scout** chat sits beside results on desktop (≥1280px) and in a bottom drawer on smaller screens (button "Ask your scout").

## States (every interactive element)

| State | Treatment |
|---|---|
| Hover | Buttons and cards lift 1–2px; chip and secondary borders darken to ink |
| Pressed | Scale 0.98 |
| Focus | 2px charcoal outline, 2px offset; fields get the orange ring |
| Selected | Orange-soft fill + ✓ |
| Disabled | Cool-grey fill, muted text, `not-allowed` cursor, reason in text nearby |
| Loading | Pulsing skeleton cards, "Scanning…" labels |
| Empty | Centered card with a title and one next step |
| Error | Red-soft alert with what failed and what to do |

Motion is short (120–200ms) and off under `prefers-reduced-motion`. Nothing fades in on scroll.

## Honesty rules

- Every status, count and audit line comes from AG-UI shared state. Never fake progress, security results or enrollments.
- Demo features say "demo" on screen: sign-in, Connect.
- X and Facebook show as "soon": they are not in the shared `Platform` type.
- Controls are at least 44px tall; labels are always visible.

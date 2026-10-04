---
name: Public Trust Modern
colors:
  surface: '#f8f9ff'
  surface-dim: '#cbdbf5'
  surface-bright: '#f8f9ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#eff4ff'
  surface-container: '#e5eeff'
  surface-container-high: '#dce9ff'
  surface-container-highest: '#d3e4fe'
  on-surface: '#0b1c30'
  on-surface-variant: '#44474f'
  inverse-surface: '#213145'
  inverse-on-surface: '#eaf1ff'
  outline: '#747780'
  outline-variant: '#c4c6d0'
  surface-tint: '#455e8d'
  primary: '#001636'
  on-primary: '#ffffff'
  primary-container: '#0b2a56'
  on-primary-container: '#7992c4'
  inverse-primary: '#adc7fc'
  secondary: '#1d5abf'
  on-secondary: '#ffffff'
  secondary-container: '#6596fe'
  on-secondary-container: '#002d6e'
  tertiary: '#2a0f00'
  on-tertiary: '#ffffff'
  tertiary-container: '#491f00'
  on-tertiary-container: '#c4835a'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#d7e2ff'
  primary-fixed-dim: '#adc7fc'
  on-primary-fixed: '#001a40'
  on-primary-fixed-variant: '#2d4674'
  secondary-fixed: '#d9e2ff'
  secondary-fixed-dim: '#b0c6ff'
  on-secondary-fixed: '#001944'
  on-secondary-fixed-variant: '#00429a'
  tertiary-fixed: '#ffdbc8'
  tertiary-fixed-dim: '#ffb689'
  on-tertiary-fixed: '#311300'
  on-tertiary-fixed-variant: '#6c3a17'
  background: '#f8f9ff'
  on-background: '#0b1c30'
  surface-variant: '#d3e4fe'
typography:
  headline-xl:
    fontFamily: Public Sans
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 40px
  headline-xl-mobile:
    fontFamily: Public Sans
    fontSize: 24px
    fontWeight: '700'
    lineHeight: 32px
  headline-lg:
    fontFamily: Public Sans
    fontSize: 24px
    fontWeight: '700'
    lineHeight: 32px
  headline-lg-mobile:
    fontFamily: Public Sans
    fontSize: 20px
    fontWeight: '700'
    lineHeight: 28px
  headline-md:
    fontFamily: Public Sans
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
  headline-sm:
    fontFamily: Public Sans
    fontSize: 16px
    fontWeight: '600'
    lineHeight: 24px
  title-md:
    fontFamily: Public Sans
    fontSize: 15px
    fontWeight: '600'
    lineHeight: 22px
  body-lg:
    fontFamily: Source Sans 3
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-md:
    fontFamily: Source Sans 3
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  body-sm:
    fontFamily: Source Sans 3
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
  label-lg:
    fontFamily: Source Sans 3
    fontSize: 14px
    fontWeight: '600'
    lineHeight: 20px
  label-md:
    fontFamily: Source Sans 3
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
  label-sm:
    fontFamily: Source Sans 3
    fontSize: 11px
    fontWeight: '700'
    lineHeight: 14px
  metric-stat:
    fontFamily: Public Sans
    fontSize: 28px
    fontWeight: '700'
    lineHeight: 36px
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  space-2xs: 0.125rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 0.75rem
  space-base: 1rem
  space-lg: 1.25rem
  space-xl: 1.5rem
  space-2xl: 2rem
  space-3xl: 2.5rem
  space-4xl: 3rem
  gutter-desktop: 1.5rem
  gutter-tablet: 1rem
  gutter-mobile: 0.75rem
  sidebar-width-expanded: 240px
  sidebar-width-collapsed: 64px
---

## Brand & Style

The design system embodies an authoritative, accessible, and structured public-sector aesthetic tailored for state agencies, school nutrition sponsors, caseworkers, and regulatory auditors. It bridges institutional reliability with modern web software usability, ensuring users handling high-stakes child nutrition programs experience clarity, efficiency, and unwavering confidence.

### Brand Personality & Core Tenets
- **Institutional Trust & Rigor:** Built upon deep, stable navy structural anchors that signal stability, official accountability, and governance.
- **Flawless Accessibility (WCAG 2.1 AA):** High-contrast ratios, unmistakable state indicators, and generous touch targets eliminate cognitive strain and operational fatigue.
- **Operational Clarity:** Clear semantic cues and disciplined hierarchy cut through dense regulatory workflows, application lifecycles, and verification audits.

### Visual Style
The design system combines **Corporate / Modern enterprise architecture** with deliberate public-sector UI patterns: crisp boundaries, clean off-white field surfaces (`#F4F6F9`), pristine white card containers (`#FFFFFF`), and refined structural framing. Color is used strictly for semantic communication—such as status progression and action priority—rather than ornamental clutter.

## Colors

The palette establishes an official, high-contrast hierarchy where structural deep navy frames the application, active royal blue powers interactive pathways, and crisp neutral grays balance data density.

### Core Roles
- **Primary Navy (`#0B2A56`):** The institutional backbone used for persistent side navigation, high-level headers, active selected navigation tabs, and primary branding elements.
- **Secondary Royal Blue (`#0D52B7`):** The primary interaction color used for action buttons, active focus outlines, linked text, and active interactive controls.
- **Tertiary Dark Royal (`#185ADB`):** Interactive hover states and high-priority action highlights.
- **Neutral Grays (`#64748B`, `#334155`, `#F4F6F9`, `#E2E8F0`):** Provides layered surface separation without visual weight. The primary application canvas resides on `#F4F6F9`, with elevated content areas resting on pure `#FFFFFF`.

### Semantic Status Lifecycle
To preserve unambiguous program auditing across dashboards and review workflows, the status system adheres strictly to explicit color pairings:
- **Draft:** Purple text (`#7C3AED`) on soft purple tint (`#F5F3FF`, border `#DDD6FE`)
- **Ready to Submit:** Teal text (`#0D9488`) on soft teal tint (`#F0FDFA`, border `#99F6E0`)
- **Under Review:** Blue text (`#2563EB`) on soft blue tint (`#EFF6FF`, border `#BFDBFE`)
- **Returned for Correction:** Amber text (`#D97706`) on soft amber tint (`#FFFBEB`, border `#FDE68A`)
- **Approved:** Green text (`#16A34A`) on soft green tint (`#F0FDF4`, border `#BBF7D0`)
- **Denied:** Red text (`#DC2626`) on soft red tint (`#FEF2F2`, border `#FECACA`)
- **Withdrawn:** Slate gray text (`#64748B`) on soft slate tint (`#F1F5F9`, border `#CBD5E1`)
- **Closed:** Dark slate text (`#334155`) on deep neutral tint (`#E2E8F0`, border `#94A3B8`)

## Typography

The typographic hierarchy balances official government authority with dense operational readability. 

- **Headlines (`Public Sans`):** Selected for its sturdy, institutional geometry, neutral apertures, and strict adherence to official public-sector legibility standards. Used for page titles, modal headers, card titles, and high-level dashboard metrics.
- **Body & Labels (`Source Sans 3`):** Crafted for sustained readability in data-intensive layouts, tables, and complex form fields. Its tall x-height and open counters maintain distinct glyph clarity even at 11px and 12px within dense administrative tables and status badges.

All numeric figures inside data summaries and statistics utilize tabular figures (`font-variant-numeric: tabular-nums`) to preserve column alignment and rapid vertical scanning.

## Layout & Spacing

The layout philosophy follows a disciplined, enterprise-grade 12-column grid system designed for data management workflows.

### Grid & Breakpoints
- **Desktop (≥1440px):** Permanent dark navy navigation sidebar (`240px`), 12-column fluid content area with `24px` (`1.5rem`) gutters and `32px` page padding. Grid status cards span 3 columns each (4-across per row).
- **Tablet (768px – 1439px):** Collapsed icon-rail sidebar (`64px`), 8-column layout with `16px` (`1rem`) gutters and `24px` margins. Status overview cards reflow to a 2-column or 4-column balanced configuration.
- **Mobile (<768px):** Off-canvas drawer triggered by an accessible hamburger toggle, 4-column layout with `12px` margins. Status summary cards reflow into a compact 2-column grid. Dense administrative tables convert to vertical stacked data cards.

### Layout Rhythm
Spacings rely on a strict 4px/8px baseline scale. Interactive components maintain a minimum 40px target height (44px on touch viewports) to ensure physical accessibility compliance.

## Elevation & Depth

Visual hierarchy is communicated via clean structural layer stacking, crisp containment borders, and restrained ambient shadows. Rather than deep cinematic drop shadows, the system prioritizes boundary clarity to support accessibility in well-lit office environments.

### Depth Hierarchy
- **Level 0 (Canvas Base):** Flat tone `#F4F6F9` hosting the entire application workspace.
- **Level 1 (Cards & Data Panels):** Solid `#FFFFFF` background bound by a 1px solid structural border `#E2E8F0` with a subtle micro-shadow: `0 1px 3px rgba(11, 42, 86, 0.05)`.
- **Level 2 (Hover & Active Interactive Cards):** Elevated with `0 4px 12px rgba(11, 42, 86, 0.08)` and border shift to `#CBD5E1`.
- **Level 3 (Dropdowns, Flyouts & Context Menus):** Pure white container with `0 8px 24px rgba(11, 42, 86, 0.12)` and 1px border `#CBD5E1`.
- **Level 4 (Modals & Focus Dialogs):** Centered panel with `0 16px 36px rgba(11, 42, 86, 0.20)`, accompanied by a high-contrast dark navy scrim (`rgba(11, 42, 86, 0.60)` with backdrop blur `2px`).

### Accessible Focus Treatment
All focused interactive elements project a distinct, non-ambiguous dual focus ring: `box-shadow: 0 0 0 2px #FFFFFF, 0 0 0 4px #0D52B7`.

## Shapes

The design system employs a refined, professional **Soft (`1`)** shape geometry. This restrained curvature reinforces architectural stability, enterprise data density, and government institutional gravity while avoiding sterile harshness.

- **Base Corner Radius (`0.25rem` / `4px`):** Applied to form inputs, table cells, compact buttons, tabs, and status badges.
- **Container Radius (`0.5rem` / `8px`):** Applied to overview cards, white summary panels, modal containers, and dashboard widgets.
- **Full Radius (`9999px`):** Restricted solely to circular notification counter pips and user profile avatar indicators.

## Components

### Buttons
- **Primary:** Background `#0D52B7`, text `#FFFFFF`, border `transparent`, font Public Sans 14px SemiBold. Hover: `#185ADB`. Active: `#0B2A56`.
- **Secondary / Outline:** Background `#FFFFFF`, text `#0D52B7`, border `1px solid #0D52B7`. Hover: `#EFF6FF`.
- **Tertiary / Ghost:** Background `transparent`, text `#0B2A56`. Hover: `#F1F5F9`.
- **Destructive:** Background `#DC2626`, text `#FFFFFF`. Hover: `#B91C1C`.
- **Sizing:** Standard `36px` height, compact `32px` for table actions, touch `44px`.

### Status Badges & Lifecycle Indicators
Status chips feature a 1px border, 4px border radius, and strict semantic color pairing:
- Format: `[Icon] + Label`
- Typography: Source Sans 3, 12px, font-weight 600.
- Inner padding: `2px 8px`.

### Form Inputs & Select Controls
- **Resting:** Background `#FFFFFF`, border `1px solid #CBD5E1`, text `#0F172A`, placeholder `#94A3B8`, height `38px`, padding `8px 12px`.
- **Focus:** Border color `#0D52B7`, outline ring `3px rgba(13, 82, 183, 0.15)`.
- **Error:** Border color `#DC2626`, accompanied by red helper text and an alert icon.
- **Select Dropdowns:** Include program context switchers (e.g., "Program: NSLP", "Program Year: 2026-27") styled with clear dropdown carats and active focus rings.

### Overview Metric Cards
- Background `#FFFFFF`, border `1px solid #E2E8F0`, padding `16px`.
- Features an icon tinted with the respective status background in the top-left, status label top-right, large metric number (Public Sans 28px bold) in the center, and a dedicated text link ("View all →") at the base.

### Data Tables
- Header: Background `#F8FAFC`, border-bottom `2px solid #E2E8F0`, text `#475569`, 12px uppercase font-weight 600.
- Rows: Background `#FFFFFF`, border-bottom `1px solid #F1F5F9`, alternating hover `#F8FAFC`, cell padding `12px 16px`.
- Inline actions: Compact outline button (`28px` height) with `#0D52B7` text and border.

### Primary Navigation (Sidebar & Top Bar)
- **Sidebar:** Background `#0B2A56` (seed color), active nav item highlighted with vibrant royal `#0D52B7` and a 3px left border accent `#38BDF8`. Inactive items styled in `#94A3B8` shifting to `#FFFFFF` on hover.
- **Top Utility Bar:** Background `#FFFFFF`, border-bottom `1px solid #E2E8F0`, containing program selectors, notification center with red counter badges, and user role profile indicators.
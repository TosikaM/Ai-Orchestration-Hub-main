# Screen: cnp_linq_screen_1_login_sso

<!-- image: screen.png · 1137x602 · RGBA -->
<!-- status: described -->
<!-- described-by: model, from the rendered PNG and the paired code.html -->

## Purpose

The single entry point to the platform. A user authenticates against their organization's
identity provider; the application itself never collects a credential.

## Layout

A centred white card on a light dotted-grid field, with a page footer. Nothing else on the
screen — no marketing panel, no state branding, no alternative sign-in path.

Card contents, top to bottom:

1. The **CNP LINQ** wordmark with the concentric-arc logo mark, and the sub-line
   "Child Nutrition Programs"
2. Heading: **"Sign in with your organization account"**
3. A single full-width primary button, royal blue with a padlock icon: **"Sign in with SSO"**
4. Link: **"Having trouble signing in?"**
5. Helper text: "Contact your systems administrator."

Footer, outside the card: "© 2025 CNP LINQ. All rights reserved." on the left; **Privacy
Policy · Terms of Use · Support** on the right.

## Fields

**None.** There is no username field, no password field, no "remember me", no state or tenant
selector.

This is the correct rendering of two requirements: authentication happens at a real identity
provider with no fabricated-token path, and the tenant is resolved from the subdomain rather
than declared by the user.

## Actions

| Control | Type | Leads to |
|---|---|---|
| Sign in with SSO | Primary button | Redirect to the OIDC provider's login page for the realm resolved from the subdomain |
| Having trouble signing in? | Link (`#help`) | Not specified — no target page in this handover |
| Privacy Policy / Terms of Use / Support | Footer links | Not specified |

## States

Only the resting state is rendered. Not shown, and not specified anywhere in the handover:

- In-flight state while redirecting to the identity provider
- Return-with-error state (authentication failed, account disabled, no role assigned)
- The state a user reaches when the identity provider is unreachable — which matters, because
  the requirement is that **no user can log in and there is no fallback path**
- The state for an authenticated user with no assigned role or scope, which must show no data
  and must not reveal system internals

## Navigation

- **Reaches this screen:** any unauthenticated request; the Angular route guard redirecting an
  unauthenticated user; explicit sign-out
- **This screen reaches:** the identity provider, and on success the role-appropriate landing
  screen — the sponsor dashboard for a Sponsor Director/Staff

## Open questions

- The footer reads **© 2025** while the rest of the corpus is dated 2026.
- No error or unavailable states are designed, though the requirements define behaviour for
  three of them.
- The card carries no tenant branding, but the frontend architecture specifies per-tenant
  logo, agency name and primary colour loaded at bootstrap. Login happens *before* that
  bootstrap, so an unbranded login page may be deliberate — worth confirming, because a state
  agency's users arriving at an unbranded page is a trust signal in a public-sector product.

Source: `screen.png`, cross-read with `code.html`

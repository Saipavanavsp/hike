# 0005. Short-lived JWT in memory plus a rotating refresh token in an httpOnly cookie

**Status:** Accepted

## Context
A single-page app needs to stay signed in across reloads without exposing long-lived
credentials to JavaScript (XSS) or to cross-site requests (CSRF).

## Decision
- Access token: JWT, 15 minutes, kept only in memory, sent as `Authorization: Bearer`.
- Refresh token: 7 days, `HttpOnly`, `SameSite=Lax`, `Secure` in production, path
  `/api/auth`, stored hashed. Every refresh rotates it; reusing a rotated token revokes the
  whole token family (theft detection). Logout and admin deactivation revoke tokens.
- The SPA calls the API on the same origin (proxy/rewrite), so the cookie is first-party.
- Cookie endpoints also require an `X-CSRF-Protection` header and check `Origin`.

## Consequences
- A stolen access token is useful for at most 15 minutes; a stolen refresh token is
  detected on the next legitimate refresh.
- Bearer-token endpoints are not exposed to CSRF; the four cookie endpoints have explicit
  checks (`app/core/csrf.py`).
- Deactivating a user takes effect immediately for refresh, and on the next request for
  access tokens (the user is re-read on every request).

## Alternatives considered
- **Session cookie for everything**: simpler revocation; needs CSRF protection on every
  state-changing endpoint.
- **Tokens in localStorage**: readable by any injected script.

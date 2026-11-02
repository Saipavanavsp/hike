"""CSRF protection for the endpoints that use the refresh-token cookie.

Bearer-token endpoints are not exposed to CSRF (a browser never attaches the token by
itself). The cookie endpoints (login, register, refresh, logout) get two checks on top of
SameSite=Lax:

1. A custom header, X-CSRF-Protection: 1. A cross-site <form> cannot set headers, and a
   cross-origin fetch() that sets one needs a CORS preflight, which only the allowed
   origins pass.
2. If the browser sends an Origin header, it must be an allowed origin or this host.
"""

from urllib.parse import urlsplit

from fastapi import HTTPException, Request, status

from app.core.config import settings

HEADER = "X-CSRF-Protection"


def csrf_protect(request: Request) -> None:
    if request.headers.get(HEADER) != "1":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "CSRF check failed: missing header")
    origin = request.headers.get("origin")
    if origin and origin != "null":
        host = urlsplit(origin).netloc
        if origin not in settings.cors_origin_list and host != request.headers.get("host"):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "CSRF check failed: origin not allowed")

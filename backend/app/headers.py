from flask import Flask, request


def register_security_headers(app: Flask) -> None:
    @app.after_request
    def security_headers(response):
        # The API returns JSON and streams, never HTML, so nothing it sends may run as a page.
        # HSTS is set by the HTTPS proxy in front of the app, since Flask cannot see the scheme.
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
        if request.path.startswith("/api/"):
            # Session, key-status and chat responses must not be kept by browsers or caches
            response.headers["Cache-Control"] = "no-store"
        return response

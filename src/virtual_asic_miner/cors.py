from __future__ import annotations

from collections.abc import Iterable

from flask import Flask, request


def enable_cors(
    app: Flask,
    *,
    allow_origin: str = "*",
    allow_methods: Iterable[str] = ("GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"),
    allow_headers: Iterable[str] = ("Content-Type", "Authorization"),
    max_age_s: int = 86400,
    allow_private_network: bool = True,
) -> None:
    methods = ", ".join([m.strip().upper() for m in allow_methods if str(m).strip()])
    default_headers = ", ".join([h.strip() for h in allow_headers if str(h).strip()])
    vary_value = "Origin, Access-Control-Request-Method, Access-Control-Request-Headers"

    @app.after_request
    def _add_cors_headers(response):  # type: ignore[no-untyped-def]
        response.headers.setdefault("Access-Control-Allow-Origin", allow_origin)
        response.headers.setdefault("Access-Control-Allow-Methods", methods)

        req_headers = request.headers.get("Access-Control-Request-Headers")
        response.headers.setdefault("Access-Control-Allow-Headers", req_headers or default_headers)

        response.headers.setdefault("Access-Control-Max-Age", str(int(max_age_s)))

        if allow_private_network:
            response.headers.setdefault("Access-Control-Allow-Private-Network", "true")

        existing_vary = response.headers.get("Vary")
        if not existing_vary:
            response.headers["Vary"] = vary_value
        elif vary_value not in existing_vary:
            response.headers["Vary"] = f"{existing_vary}, {vary_value}"

        return response


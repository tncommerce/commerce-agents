"""Browser recovery for rejected offers; never redirect or record a clickout."""

from html import escape
from urllib.parse import urlencode

from fastapi import HTTPException, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import HTMLResponse

from .analytics import sanitize_attribution_identifier


async def clickout_exception_handler(request: Request, exc: HTTPException):
    if not (
        request.method == "GET"
        and request.url.path.startswith("/api/clickout/")
        and exc.status_code == 404
        and exc.detail == "Offer not available"
        and "text/html" in request.headers.get("accept", "")
    ):
        return await http_exception_handler(request, exc)

    params = {}
    for key in ("src", "cmp", "content", "sid"):
        value = sanitize_attribution_identifier(request.query_params.get(key))
        if value:
            params[key] = value
    if request.query_params.get("qa", "").lower() in {"1", "true", "on", "yes"}:
        params["qa"] = "1"
    query = "?" + urlencode(params) if params else ""
    catalog = escape("https://dufynd.de/duft" + query, quote=True)
    compare = escape("https://dufynd.de/vergleich" + query, quote=True)
    return HTMLResponse(
        f"""<!doctype html><html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow"><title>Angebot nicht verfügbar | DUFYND</title>
<style>body{{margin:0;background:#f5f0e8;color:#29231e;font:16px/1.6 system-ui,sans-serif}}
main{{max-width:36rem;margin:12vh auto;padding:24px}}h1{{font-size:clamp(1.7rem,6vw,2.4rem);line-height:1.2}}
nav{{display:flex;flex-wrap:wrap;gap:12px;margin-top:24px}}a{{display:inline-block;padding:12px 18px;
border-radius:12px;color:white;background:#513f2d;text-decoration:none}}a:focus-visible{{outline:3px solid #976612;outline-offset:4px}}
</style></head><body><main><p>DUFYND</p><h1>Dieses Angebot ist gerade nicht verfügbar.</h1>
<p>Preis oder Verfügbarkeit konnten nicht bestätigt werden. Du wurdest nicht zum Händler weitergeleitet.</p>
<p>Entdecke andere Düfte oder prüfe die aktuell verfügbaren Angebote im Katalog.</p>
<nav aria-label="Weiter zu DUFYND"><a href="{catalog}">Zum Duftkatalog</a>
<a href="{compare}">Düfte vergleichen</a></nav></main></body></html>""",
        status_code=404,
        headers={
            "Cache-Control": "no-store",
            "X-Robots-Tag": "noindex, nofollow",
            "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'",
            "Referrer-Policy": "no-referrer",
        },
    )

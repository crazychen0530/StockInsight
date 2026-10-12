"""Read-only HTTPS/auth smoke checks against the isolated production rehearsal."""

import base64
import json
import ssl
import urllib.error
import urllib.request
from pathlib import Path


def main():
    directory = Path("secrets/production")
    context = ssl.create_default_context(cafile=str(directory / "local-ca.crt"))
    credential = base64.b64encode(
        ("preview:" + (directory / "preview_password").read_text().strip()).encode()
    ).decode()
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}), urllib.request.HTTPSHandler(context=context)
    )

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, request, response, code, message, headers, url):
            return None

    redirect_opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}), NoRedirect()
    )
    try:
        redirect_opener.open("http://localhost:18080/stocks", timeout=5)
        raise AssertionError("HTTP must redirect")
    except urllib.error.HTTPError as redirect:
        assert redirect.code == 301
        assert redirect.headers["Location"] == "https://localhost:18443/stocks"

    def request(path, expected, authenticated=False, method="GET"):
        headers = {"Authorization": "Basic " + credential} if authenticated else {}
        body = b"{}" if method == "PUT" else None
        req = urllib.request.Request(
            "https://localhost:18443" + path, body, headers, method=method
        )
        try:
            with opener.open(req, timeout=10) as response:
                status, content = response.status, response.read()
        except urllib.error.HTTPError as response:
            status, content = response.code, response.read()
        assert status == expected, (path, status, expected)
        return content

    request("/", 401)
    request("/api/v1/health", 401)
    request("/source-settings", 401)
    request("/", 200, True)
    request("/stocks/600519.SH", 200, True)
    values = json.loads(request("/api/v1/stocks?page_size=1", 200, True))
    assert values["total"] > 0
    request("/api/v1/system/source-policy", 200, True)
    request("/api/v1/system/source-policy", 403, True, "PUT")
    request("/docs", 404, True)
    request("/openapi.json", 404, True)
    print("11 trusted-CA HTTPS/auth/redirect/SPA/read-only checks passed")


if __name__ == "__main__":
    main()

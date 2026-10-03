import httpx
import pytest
from app.sponsors import service

LISTING = """<?xml version="1.0" encoding="UTF-8"?>
<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">
<Name>logos</Name><Prefix>lauf/</Prefix>
<Contents><Key>lauf/gold/a.png</Key></Contents>
<Contents><Key>lauf/silber/b.jpg</Key></Contents>
<Contents><Key>lauf/silver/c.webp</Key></Contents>
<Contents><Key>lauf/bronze/d.svg</Key></Contents>
<Contents><Key>lauf/bronze/readme.txt</Key></Contents>
<Contents><Key>lauf/platin/e.png</Key></Contents>
<Contents><Key>lauf/sponsors.csv</Key></Contents>
</ListBucketResult>"""

CSV = "dateiname,name,url\na.png,Goldene Bäckerei,https://example.org/gold\nb.jpg,Silber GmbH,\n"


def test_normalize_bucket_url():
    assert (
        service.normalize_bucket_url("https://logos.s3-website.fr-par.scw.cloud/lauf/")
        == "https://logos.s3.fr-par.scw.cloud/lauf"
    )
    assert (
        service.normalize_bucket_url("https://logos.s3.fr-par.scw.cloud/lauf")
        == "https://logos.s3.fr-par.scw.cloud/lauf"
    )


@pytest.mark.asyncio
async def test_list_bucket_parses_tiers_and_csv(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        if "list-type=2" in str(request.url):
            return httpx.Response(200, content=LISTING.encode())
        if str(request.url).endswith("/sponsors.csv"):
            return httpx.Response(200, text=CSV)
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    real = httpx.AsyncClient

    class Patched(real):
        def __init__(self, *a, **kw):
            kw["transport"] = transport
            super().__init__(*a, **kw)

    monkeypatch.setattr(service.httpx, "AsyncClient", Patched)
    service._cache.clear()
    listing = await service.list_bucket(
        "https://logos.s3-website.fr-par.scw.cloud/lauf/", use_cache=False
    )
    assert listing.error is None
    assert listing.counts() == {"1": 1, "2": 2, "3": 1}
    gold = listing.by_tier[1][0]
    assert gold["name"] == "Goldene Bäckerei" and gold["url"] == "https://example.org/gold"
    assert gold["image_url"] == "https://logos.s3.fr-par.scw.cloud/lauf/gold/a.png"
    assert listing.by_tier[2][0]["name"] == "Silber GmbH" and listing.by_tier[2][0]["url"] is None


@pytest.mark.asyncio
async def test_list_bucket_is_fault_tolerant(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    class Patched(httpx.AsyncClient):
        def __init__(self, *a, **kw):
            kw["transport"] = httpx.MockTransport(handler)
            super().__init__(*a, **kw)

    monkeypatch.setattr(service.httpx, "AsyncClient", Patched)
    service._cache.clear()
    listing = await service.list_bucket("https://down.example.org/x", use_cache=False)
    assert listing.error and listing.by_tier == {}

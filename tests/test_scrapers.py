import json
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

import pytest

from scrapers.base import ScrapingBlocked, public_url
from scrapers.magicbricks import MagicBricksScraper
from scrapers.maps import MapsScraper
from scrapers.social import SocialScraper
from scrapers.structured import jsonld_records


def html_record(data):
    return '<script type="application/ld+json">' + json.dumps(data) + "</script>"


def test_structured_graph_and_invalid_json():
    html = html_record({"@graph": [{"name": "Listing"}]})
    html += '<script type="application/ld+json">bad json</script>'
    assert any(record.get("name") == "Listing" for record in jsonld_records(html))


def test_owner_only_recent_listings(settings, monkeypatch):
    scraper = MagicBricksScraper(settings)
    data = [
        {
            "name": "Owner Listing",
            "sellerType": "owner",
            "seller": {"name": "Owner"},
            "datePosted": datetime.now(UTC).isoformat(),
        },
        {
            "name": "Broker Listing",
            "sellerType": "broker",
            "datePosted": datetime.now(UTC).isoformat(),
        },
        {
            "name": "Old Listing",
            "sellerType": "owner",
            "datePosted": (datetime.now(UTC) - timedelta(days=30)).isoformat(),
        },
        {
            "name": "Unknown Owner",
            "seller": {"@type": "Person"},
            "datePosted": datetime.now(UTC).isoformat(),
        },
    ]
    monkeypatch.setattr(scraper, "page_html", lambda _: html_record(data))
    results = scraper.collect(
        {
            "property_urls": {
                "magicbricks": [
                    "https://www.magicbricks.com/public-listing",
                ]
            }
        }
    )
    assert len(results) == 1
    assert results[0].business_name == "Owner"
    assert results[0].metadata["owner_verified"]


def test_property_domain_validation(settings):
    with pytest.raises(ScrapingBlocked):
        MagicBricksScraper(settings).collect(
            {
                "property_urls": {
                    "magicbricks": [
                        "https://evil.example/listing",
                    ]
                }
            }
        )


def test_directory_output_and_no_website(settings, monkeypatch):
    scraper = MapsScraper(settings)
    monkeypatch.setattr(
        scraper,
        "page_html",
        lambda _: html_record(
            {
                "@type": "LocalBusiness",
                "name": "Local Studio",
                "@id": "studio-1",
            }
        ),
    )
    rows = scraper.collect({"business_listing_urls": ["https://example.com/listings"]})
    assert rows[0].channel == "maps"
    assert rows[0].metadata["no_website"] is True


def test_seo_missing_elements(settings, monkeypatch):
    scraper = MapsScraper(settings)
    monkeypatch.setattr(scraper, "page_html", lambda _: "<html><title>Studio</title></html>")
    signals = scraper.seo_signals("https://example.com")
    assert signals["weak_seo"]
    assert signals["missing_seo_elements"] == ["meta_description", "h1"]


def test_private_network_targets_rejected(monkeypatch):
    monkeypatch.setattr("socket.getaddrinfo", lambda *_: [(2, 1, 6, "", ("127.0.0.1", 443))])
    with pytest.raises(ScrapingBlocked):
        public_url("http://localhost/private")


def test_robots_blocks_before_browser(settings, monkeypatch):
    scraper = MapsScraper(settings)
    monkeypatch.setattr(scraper, "allowed", lambda _: False)
    with pytest.raises(ScrapingBlocked, match="robots.txt"):
        scraper.page_html("https://example.com/private")


def test_no_login_social_stub(settings):
    with pytest.raises(NotImplementedError):
        SocialScraper(settings).collect({})


def test_scraper_worker_uses_ingest_pipeline(factory, settings, monkeypatch):
    from sqlalchemy import select

    from core.models import Lead, ScraperRun
    from scrapers import jobs

    scraper = Mock()
    from api.schemas.leads import LeadIngest

    scraper.collect.return_value = [LeadIngest(business_name="Studio", channel="maps")]
    monkeypatch.setitem(jobs.SCRAPERS, "maps", lambda _: scraper)
    monkeypatch.setattr(jobs, "get_session_factory", lambda: factory)
    monkeypatch.setattr(jobs, "get_settings", lambda: settings)
    with factory.begin() as db:
        run = ScraperRun(channel="maps")
        db.add(run)
        db.flush()
        run_id = run.id
    jobs.execute_run(str(run_id))
    with factory() as db:
        assert db.get(ScraperRun, run_id).status == "succeeded"
        assert db.scalar(select(Lead)).business_name == "Studio"

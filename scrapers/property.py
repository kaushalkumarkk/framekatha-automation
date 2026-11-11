from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit

from api.schemas.leads import LeadIngest
from core.external import ConfigurationRequired
from scrapers.base import BaseScraper, ScrapingBlocked
from scrapers.structured import jsonld_records


class PropertyScraper(BaseScraper):
    channel = "property"
    source_name = ""
    domain = ""

    def collect(self, config: dict) -> list[LeadIngest]:
        results = []
        cutoff = datetime.now(UTC) - timedelta(days=config.get("property_max_age_days", 7))
        urls = config.get("property_urls", {}).get(self.source_name, [])
        if not urls:
            raise ConfigurationRequired(f"property_urls.{self.source_name} in the scraper YAML")
        for url in urls:
            host = urlsplit(url).hostname or ""
            if host != self.domain and not host.endswith("." + self.domain):
                raise ScrapingBlocked("URL does not belong to the configured property source")
            for item in jsonld_records(self.page_html(url)):
                seller = item.get("seller") or item.get("offeredBy") or {}
                # Do not infer owner status from Person alone. Require explicit
                # owner evidence, a publication date, and a contactable source.
                owner = str(item.get("sellerType", seller.get("sellerType", ""))).lower()
                if owner not in {"owner", "individual_owner"}:
                    continue
                try:
                    published = datetime.fromisoformat(item["datePosted"].replace("Z", "+00:00"))
                    if published.tzinfo is None:
                        published = published.replace(tzinfo=UTC)
                except (KeyError, ValueError, TypeError):
                    continue
                if not cutoff <= published <= datetime.now(UTC):
                    continue
                name = seller.get("name") or item.get("name")
                if not name:
                    continue
                results.append(
                    LeadIngest(
                        business_name=name,
                        channel=self.source_name,
                        external_id=str(item.get("@id") or item.get("url") or url),
                        source_url=url,
                        phone=seller.get("telephone"),
                        email=seller.get("email"),
                        city=config.get("city"),
                        metadata={
                            "owner_verified": True,
                            "published_at": published.isoformat(),
                            "listing_title": item.get("name"),
                        },
                    )
                )
        return results

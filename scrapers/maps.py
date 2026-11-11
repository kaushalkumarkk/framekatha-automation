from bs4 import BeautifulSoup

from api.schemas.leads import LeadIngest
from core.external import ConfigurationRequired
from scrapers.base import BaseScraper


class MapsScraper(BaseScraper):
    """Public business-listing pages; Google Maps UI is intentionally not scraped.

    Public listing adapters use Schema.org LocalBusiness records and website SEO signals.
    """

    channel = "maps"

    def seo_signals(self, url: str | None) -> dict:
        if not url:
            return {"no_website": True, "weak_seo": True, "seo_checked": False}
        try:
            soup = BeautifulSoup(self.page_html(url), "html.parser")
            description = soup.find("meta", attrs={"name": "description"})
            missing = []
            if not soup.title or not soup.title.get_text(strip=True):
                missing.append("title")
            if not description or not description.get("content", "").strip():
                missing.append("meta_description")
            if not soup.find("h1"):
                missing.append("h1")
            return {
                "no_website": False,
                "weak_seo": bool(missing),
                "seo_checked": True,
                "missing_seo_elements": missing,
            }
        except Exception:
            return {"no_website": False, "weak_seo": None, "seo_checked": False}

    def collect(self, config: dict) -> list[LeadIngest]:
        from urllib.parse import quote

        from scrapers.structured import jsonld_records

        results = []
        urls = list(config.get("business_listing_urls", []))
        for template in config.get("business_listing_url_templates", []):
            for location in config.get("locations", []):
                for category in config.get("categories", []):
                    urls.append(template.format(location=quote(location), category=quote(category)))
        if not urls:
            raise ConfigurationRequired("business_listing_urls in the scraper YAML")
        for url in dict.fromkeys(urls):
            html = self.page_html(url)
            for item in jsonld_records(html):
                kinds = item.get("@type", [])
                kinds = [kinds] if isinstance(kinds, str) else kinds
                if not item.get("name") or not any(
                    kind
                    in {
                        "LocalBusiness",
                        "Organization",
                        "Restaurant",
                        "Store",
                        "MedicalClinic",
                        "RealEstateAgent",
                    }
                    for kind in kinds
                ):
                    continue
                address = item.get("address") or {}
                website = item.get("url")
                results.append(
                    LeadIngest(
                        business_name=item["name"],
                        phone=item.get("telephone"),
                        email=item.get("email"),
                        website=website,
                        source_url=url,
                        city=address.get("addressLocality", config.get("city")),
                        channel=self.channel,
                        external_id=str(item.get("@id") or website or item["name"]),
                        metadata=self.seo_signals(website),
                    )
                )
        return results

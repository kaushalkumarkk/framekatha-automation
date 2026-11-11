from scrapers.base import BaseScraper


class SocialScraper(BaseScraper):
    channel = "social"

    def collect(self, config):
        # TODO: terms-of-service risk. Use authorized APIs or manual exports only.
        raise NotImplementedError("Social scraping is disabled; use authorized imports")

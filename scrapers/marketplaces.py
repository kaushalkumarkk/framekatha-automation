from scrapers.base import BaseScraper


class MarketplaceScraper(BaseScraper):
    channel = "marketplaces"

    def collect(self, config):
        # TODO: Upwork/LinkedIn terms-of-service risk. Never scrape behind logins.
        raise NotImplementedError("Upwork/LinkedIn scraping is disabled; use authorized imports")

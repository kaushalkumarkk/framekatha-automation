import hashlib
from importlib.resources import files

from pydantic import BaseModel, Field

from ai.client import generate_json
from api.schemas.leads import LeadIngest
from core.external import ConfigurationRequired
from scrapers.base import BaseScraper


class RadarClassification(BaseModel):
    notable_new_podcast: bool
    person: str | None = None
    reason: str
    confidence: float = Field(ge=0, le=1)


class RadarScraper(BaseScraper):
    channel = "radar"

    def collect(self, config):
        if not self.settings.news_api_key:
            raise ConfigurationRequired("NEWS_API_KEY")
        data = self.get_json(
            "https://newsapi.org/v2/everything",
            headers={"X-Api-Key": self.settings.news_api_key.get_secret_value()},
            params={
                "q": config.get("radar_query", '"new podcast" AND India'),
                "sortBy": "publishedAt",
                "pageSize": 30,
                "language": "en",
            },
        )
        results = []
        for article in data.get("articles", []):
            result = generate_json(
                files("ai").joinpath("prompts/radar.v1.txt").read_text(),
                {"title": article.get("title"), "description": article.get("description")},
                RadarClassification,
                "podcast_radar",
            )
            if result.notable_new_podcast and result.person and result.confidence >= 0.8:
                results.append(
                    LeadIngest(
                        business_name=result.person,
                        channel=self.channel,
                        external_id=hashlib.sha256(article["url"].encode()).hexdigest(),
                        source_url=article["url"],
                        metadata={
                            "classification": result.model_dump(),
                            "published_at": article.get("publishedAt"),
                        },
                    )
                )
        return results

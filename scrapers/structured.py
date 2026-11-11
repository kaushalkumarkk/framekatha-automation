import json

from bs4 import BeautifulSoup


def jsonld_records(html: str) -> list[dict]:
    records = []

    def visit(value):
        if isinstance(value, list):
            for item in value:
                visit(item)
        elif isinstance(value, dict):
            records.append(value)
            for key in ("@graph", "itemListElement", "item", "offers"):
                if key in value:
                    visit(value[key])

    for tag in BeautifulSoup(html, "html.parser").find_all("script", type="application/ld+json"):
        try:
            visit(json.loads(tag.string or tag.get_text()))
        except (ValueError, TypeError):
            continue
    return records

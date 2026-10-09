import json
import re
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from config import ARTICLE_NUMBER, ARTICLE_URL

ROOT = Path(__file__).parent
INPUT = ROOT / "data" / "article.html"
OUTPUT = ROOT / "data" / "sections.json"
BLOCK_TAGS = {"p", "ol", "ul", "table", "iframe", "video"}
HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}


def clean_text(value):
    return re.sub(r"\s+", " ", value).strip()


def absolute_url(value):
    return urljoin(ARTICLE_URL, value)


def links_in(tag, video_title="Video"):
    links = []
    for anchor in tag.find_all("a", href=True):
        item = {"title": clean_text(anchor.get_text(" ", strip=True)), "url": absolute_url(anchor["href"])}
        if "brightcove" in item["url"].lower():
            item["title"] = item["title"] or video_title
            item["kind"] = "video"
        if item["url"] not in {link["url"] for link in links}:
            links.append(item)
    for element in [tag, *tag.find_all(["iframe", "video", "source"])]:
        for attribute in ("src", "data-src", "href"):
            value = element.get(attribute)
            if value and ("brightcove" in value.lower() or element.name in {"iframe", "video"}):
                url = absolute_url(value)
                if url not in {link["url"] for link in links}:
                    title = clean_text(element.get("title") or element.get("aria-label") or video_title)
                    links.append({"title": title, "url": url, "kind": "video"})
    return links


def list_items(tag):
    items = []
    for item in tag.find_all("li", recursive=False):
        text = clean_text(item.get_text(" ", strip=True))
        if text:
            items.append(text)
    return items


def table_rows(tag):
    rows = []
    for row in tag.find_all("tr"):
        cells = [clean_text(cell.get_text(" ", strip=True)) for cell in row.find_all(["th", "td"], recursive=False)]
        if any(cells):
            rows.append(cells)
    return rows


def extract_blocks(root):
    sections = []
    current = {"heading": "Article", "blocks": []}
    sections.append(current)

    for element in root.find_all(list(HEADING_TAGS | BLOCK_TAGS)):
        if element.name in HEADING_TAGS:
            heading = clean_text(element.get_text(" ", strip=True))
            if heading:
                current = {"heading": heading, "blocks": []}
                sections.append(current)
            continue

        if any(parent.name in BLOCK_TAGS for parent in element.parents if parent is not root):
            continue

        block = {"type": element.name}
        if element.name in {"ol", "ul"}:
            block["items"] = list_items(element)
            block["text"] = "\n".join(block["items"])
        elif element.name == "table":
            block["rows"] = table_rows(element)
            block["text"] = "\n".join(" | ".join(row) for row in block["rows"])
        elif element.name in {"iframe", "video"}:
            block["text"] = clean_text(element.get("title") or element.get("aria-label") or "Video")
        else:
            block["text"] = clean_text(element.get_text(" ", strip=True))
        block["links"] = links_in(element, current["heading"])
        if block.get("text") or block["links"]:
            current["blocks"].append(block)

    return [section for section in sections if section["blocks"]]


def main():
    if not INPUT.exists():
        raise SystemExit(f"Missing {INPUT}. Save the article from {ARTICLE_URL} to this exact path first.")

    soup = BeautifulSoup(INPUT.read_bytes(), "html.parser")
    for element in soup.select("script, style, noscript, header, footer, nav, aside, form, [role='navigation']"):
        element.decompose()

    root = soup.find("main") or soup.find("article") or soup.body or soup
    title_tag = root.find("h1") or soup.find("h1") or soup.title
    title = clean_text(title_tag.get_text(" ", strip=True)) if title_tag else ""
    sections = extract_blocks(root)
    if not sections:
        raise SystemExit("No article sections were found in data/article.html.")

    affected_products = []
    product_heading = soup.find(id=re.compile(r"^AffectedProduct$", re.IGNORECASE))
    product_list = product_heading.find_next_sibling("span", class_="content-heading_details") if product_heading else None
    if product_list:
        affected_products = [item.strip() for item in product_list.get_text(" ", strip=True).split(",") if item.strip()]
    if not affected_products:
        for section in sections:
            if "affected product" in section["heading"].lower():
                text = " ".join(block.get("text", "") for block in section["blocks"])
                affected_products = [item.strip() for item in re.split(r",|\n", text) if item.strip()]
                break

    page_text = clean_text(root.get_text(" ", strip=True))
    modified = re.search(r"Last Modified:\s*([^\n]+?)(?:\s+Version:|$)", page_text, re.IGNORECASE)
    videos = []
    for section in sections:
        for block in section["blocks"]:
            for link in block.get("links", []):
                if link.get("kind") == "video" and link not in videos:
                    videos.append(link)

    result = {
        "article_number": ARTICLE_NUMBER,
        "url": ARTICLE_URL,
        "title": title,
        "last_modified": clean_text(modified.group(1)) if modified else "",
        "affected_products": affected_products,
        "sections": sections,
        "videos": videos,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Saved {len(sections)} article sections to {OUTPUT}")
    if not affected_products:
        print("Warning: the Affected Products list was not detected; check data/sections.json before building the graph.")


if __name__ == "__main__":
    main()

"""
scrape.py - collect property listings from darglobal.co.uk and wasalt.sa
and write them to data/raw/<site>.jsonl for process_data.py.

Install:
    pip install requests beautifulsoup4 playwright
    playwright install chromium

Notes
- Darglobal's /projects page is server-rendered, so requests + BeautifulSoup works.
- Wasalt renders its listing cards with JavaScript, so it needs Playwright.
- Selectors marked "TO VERIFY" were inferred, not read from raw HTML. Open the
  page in DevTools and adjust the constants below if a field comes back empty.
- There is NO fake/sample-data fallback on purpose: a chatbot must never answer
  from invented properties. If a scraper returns nothing, the script says so.
"""
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

# ----------------------------------------------------------------- config
RAW_DIR = "data/raw"
USER_AGENT = "Mozilla/5.0 (compatible; PropertyChatbotBot/1.0; +mailto:you@example.com)"
HEADLESS = os.environ.get("HEADLESS", "1") != "0"   # HEADLESS=0 -> visible browser
DELAY_SECONDS = 1.5          # pause between requests (be polite)
TIMEOUT = 20

# Darglobal
DG_BASE = "https://darglobal.co.uk"
DG_LIST_URL = f"{DG_BASE}/projects"
DG_CARD_SELECTOR = "main a[href][title]"       # TO VERIFY (class names unknown)
DG_FETCH_DETAILS = True                        # visit each project page for more text
DG_MAX_PROJECTS = None                         # e.g. 5 while testing

# Wasalt
WS_BASE = "https://wasalt.sa"
WS_SEEDS = [                                   # category pages that showed listings
    f"{WS_BASE}/en/properties-for-sale-in-riyadh",
    f"{WS_BASE}/en/apartments-for-sale-in-riyadh",
    f"{WS_BASE}/en/apartments-for-sale-in-south-riyadh",
    f"{WS_BASE}/en/properties-for-sale-in-north-riyadh",
    f"{WS_BASE}/en/buildings-for-sale-in-saudi-arabia",
    f"{WS_BASE}/en/apartments-for-rent-in-riyadh-for-sar-45000",
]
WS_MAX_PAGES_PER_SEED = 3                      # pagination is ?page=N; raise carefully
WS_CARD_LINK = 'a[href*="/en/property/"]'      # detail-page links (verified URL pattern)
WS_FETCH_DETAILS = False                       # True = open each detail page too (slow)

CURRENCY = r"(?:AED|USD|SAR|QAR|GBP|EUR|OMR|\$|£|€)"
PRICE_RE = re.compile(rf"{CURRENCY}\s?\d[\d,\.]*\s?(?:million|mn|m|bn|k)?", re.I)

# ----------------------------------------------------------------- helpers
session = requests.Session()
session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "en"})
_robots = {}


def allowed(url):
    """Respect robots.txt. Fetches it with OUR user agent (urllib's default agent
    gets 403 from many sites, which RobotFileParser wrongly reads as 'disallow all')."""
    p = urlparse(url)
    base = f"{p.scheme}://{p.netloc}"
    if base not in _robots:
        rp = RobotFileParser()
        robots_url = base + "/robots.txt"
        try:
            r = requests.get(robots_url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
            print(f"  [robots] {robots_url} -> HTTP {r.status_code}")
            if r.status_code == 200:
                save_debug(f"{p.netloc}_robots.txt", r.text)   # read this file yourself!
                rp.parse(r.text.splitlines())
            elif r.status_code in (401, 403):
                print("  [robots] robots.txt itself is blocked for this client; "
                      "treating as disallow-all (conservative).")
                rp.disallow_all = True
            else:
                rp.allow_all = True                           # 404 etc. = no rules
        except Exception as e:
            print(f"  [warn] could not read {robots_url} ({e}); skipping this site to be safe")
            rp.disallow_all = True
        _robots[base] = rp
    return _robots[base].can_fetch(USER_AGENT, url)


def fetch(url):
    if not allowed(url):
        raise PermissionError(f"robots.txt disallows {url}")
    resp = session.get(url, timeout=TIMEOUT)
    resp.raise_for_status()
    time.sleep(DELAY_SECONDS)
    return resp


def clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def infer_property_type(text):
    t = text.lower()
    if "penthouse" in t:
        return "Penthouse"
    if "villa" in t or "mansion" in t:
        return "Villa"
    if "hotel" in t:
        return "Hotel"
    if "plot" in t or "land" in t:
        return "Plot"
    if "building" in t:
        return "Building"
    if any(k in t for k in ("apartment", "residence", "tower", "flat")):
        return "Apartment"
    return ""


def write_jsonl(path, records):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


# ----------------------------------------------------------------- Darglobal
def extract_detail(html):
    """Return (meta_description, main_text) from a project page."""
    soup = BeautifulSoup(html, "html.parser")
    meta = soup.find("meta", attrs={"name": "description"})
    meta_desc = clean(meta.get("content")) if meta else ""
    for tag in soup(["script", "style", "noscript", "nav", "footer", "form", "svg"]):
        tag.decompose()
    root = soup.find("main") or soup.body or soup
    blocks, seen = [], set()
    for el in root.find_all(["h1", "h2", "h3", "p", "li"]):
        t = clean(el.get_text(" "))
        if len(t) >= 3 and t not in seen:
            seen.add(t)
            blocks.append(t)
    return meta_desc, "\n".join(blocks)


def save_debug(name, content):
    os.makedirs("data/debug", exist_ok=True)
    with open(os.path.join("data/debug", name), "w", encoding="utf-8") as f:
        f.write(content)


BLOCK_HINTS = ("just a moment", "captcha", "access denied", "verify you are human",
               "attention required", "cf-chl", "enable javascript", "unusual traffic",
               "incapsula", "request unsuccessful")


def diagnose(tag, html, status=None):
    """Print what a page really contains, so we can tell content from a block page."""
    soup = BeautifulSoup(html or "", "html.parser")
    title = clean(soup.title.get_text()) if soup.title else "(no <title>)"
    for t in soup(["script", "style", "noscript"]):
        t.decompose()
    text = clean(soup.get_text(" "))
    hits = [h for h in BLOCK_HINTS if h in (title + " " + text).lower()]
    print(f"  [diag:{tag}] status={status} title={title!r} html_bytes={len(html or '')} "
          f"links={len(soup.find_all('a'))} text_chars={len(text)}")
    print(f"  [diag:{tag}] text starts: {text[:200]!r}")
    if hits:
        print(f"  [diag:{tag}] LOOKS LIKE A BLOCK/CHALLENGE PAGE (matched: {hits}). "
              f"Do not try to bypass it; see the notes.")
    return bool(hits)


def render_html(url, wait_selector="a[title]"):
    """Load a page in headless Chromium and return the rendered HTML."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        page = browser.new_context(user_agent=USER_AGENT, locale="en-US").new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
        try:
            page.wait_for_selector(wait_selector, timeout=15000)
        except Exception:
            pass
        page.wait_for_timeout(2000)
        html = page.content()
        browser.close()
    time.sleep(DELAY_SECONDS)
    return html


def dg_collect_cards(html):
    soup = BeautifulSoup(html, "html.parser")
    anchors = soup.select(DG_CARD_SELECTOR) or soup.select("a[href][title]")
    print(f"  {len(anchors)} <a title> elements, {len(soup.find_all('a'))} links in total")
    records, seen = [], set()
    for a in anchors:
        href = urljoin(DG_LIST_URL, a["href"])
        if urlparse(href).netloc != urlparse(DG_BASE).netloc or href in seen:
            continue
        title = clean(a.get("title"))
        # The card text repeats the title; what remains is location (+ optional tagline).
        parts = []
        for s in a.stripped_strings:
            s = clean(s)
            if s and s != title and s not in parts:
                parts.append(s)
        if not title or not parts:      # skips logo / nav links that have no card text
            continue
        seen.add(href)
        location = parts[0]
        tagline = parts[1] if len(parts) > 1 else ""
        records.append({
            "source": "darglobal",
            "listing_type": "project",
            "url": href,
            "title": title,
            "location": location,
            "country": location.split(",")[-1].strip(),
            "tagline": tagline,
            "property_type": infer_property_type(f"{title} {tagline}"),
            "price": "",
            "description": tagline,
            "detail_text": "",
            "scraped_at": now_iso(),
        })
    return records


def scrape_darglobal():
    print("Scraping DarGlobal /projects ...")
    resp = fetch(DG_LIST_URL)
    html = resp.text
    save_debug("darglobal_projects_requests.html", html)
    if diagnose("darglobal requests", html, resp.status_code):
        print("  DarGlobal is blocking automated access. Stopping (no retries). "
              "Use an official data source or a manually curated dataset.")
        return []
    records = dg_collect_cards(html)
    if not records:
        print("  no cards in the static HTML (probably rendered by JavaScript); "
              "retrying with Playwright ...")
        try:
            html = render_html(DG_LIST_URL)
            diagnose("darglobal rendered", html)
            save_debug("darglobal_projects_rendered.html", html)
            records = dg_collect_cards(html)
        except ImportError:
            print("  Playwright not installed: pip install playwright && playwright install chromium")
    print(f"  found {len(records)} project cards")
    if not records:
        print("  open data/debug/darglobal_projects_*.html and check what the page really contains")
    if DG_MAX_PROJECTS:
        records = records[:DG_MAX_PROJECTS]

    if DG_FETCH_DETAILS:
        for i, r in enumerate(records, 1):
            print(f"  [{i}/{len(records)}] {r['url']}")
            try:
                meta_desc, text = extract_detail(fetch(r["url"]).text)
                if len(text) < 300:                      # likely JS-rendered
                    meta_desc, text = extract_detail(render_html(r["url"], "h1"))
            except Exception as e:
                print(f"    skipped detail ({e})")
                continue
            if meta_desc:
                r["description"] = meta_desc
            r["detail_text"] = text[:8000]
            m = PRICE_RE.search(text)
            if m:
                r["price"] = clean(m.group(0))      # best guess; check manually
            if not r["property_type"]:
                r["property_type"] = infer_property_type(text[:1500])
    return records


# ----------------------------------------------------------------- Wasalt
_CARD_JS = """
(sel) => {
  const countHrefs = el => new Set(
      [...el.querySelectorAll(sel)].map(a => a.getAttribute('href'))).size;
  const out = new Map();
  for (const a of document.querySelectorAll(sel)) {
    let node = a;
    while (node.parentElement && node.parentElement !== document.body &&
           countHrefs(node.parentElement) <= 1) node = node.parentElement;
    const href = a.href;
    const text = node.innerText || '';
    const prev = out.get(href);
    if (!prev || text.length > prev.text.length)
      out.set(href, {href, text, title: a.getAttribute('title') || ''});
  }
  return [...out.values()];
}
"""


def parse_wasalt_card(card, listing_type):
    lines = [clean(l) for l in card["text"].splitlines() if clean(l)]
    title = ""
    for l in lines:                                   # e.g. "Apartment 219 SQM with 6 Bedrooms Tuwaiq, West Riyadh, Riyadh"
        if re.search(r"sqm|bedroom", l, re.I):
            title = l
            break
    title = title or card["title"] or (lines[0] if lines else "")

    area = re.search(r"(\d[\d,\.]*)\s*SQM", title, re.I)
    beds = re.search(r"(\d+)\s*Bedrooms?", title, re.I)
    ptype = re.match(r"^(.*?)\s+\d", title)
    loc = re.split(r"Bedrooms?\s+|SQM\s+", title, maxsplit=1, flags=re.I)
    location = loc[-1] if len(loc) > 1 else ""

    price = re.search(r"\b\d{1,3}(?:,\d{3})+\b", card["text"])   # first large number = price (TO VERIFY)
    period = re.search(r"\b(yearly|annual|annually|monthly|year|month)\b", card["text"], re.I)

    listing_id = re.search(r"-(\d+)/?$", urlparse(card["href"]).path)
    facts = [f"{ptype.group(1) if ptype else 'Property'} for {listing_type}"]
    if location:
        facts[0] += f" in {location}"
    if area:
        facts.append(f"{area.group(1)} sqm")
    if beds:
        facts.append(f"{beds.group(1)} bedrooms")
    if price:
        facts.append(f"price {price.group(0)} SAR" + (f" per {period.group(1)}" if period else ""))

    return {
        "source": "wasalt",
        "listing_type": listing_type,
        "listing_id": listing_id.group(1) if listing_id else "",
        "url": card["href"],
        "title": title,
        "location": location,
        "country": "Saudi Arabia",
        "property_type": ptype.group(1) if ptype else infer_property_type(title),
        "price": price.group(0) if price else "",
        "currency": "SAR",
        "bedrooms": beds.group(1) if beds else "",
        "area_sqm": area.group(1) if area else "",
        "description": ". ".join(facts) + ".",
        "detail_text": "",
        "raw_text": card["text"][:500],            # kept for debugging selectors
        "scraped_at": now_iso(),
    }


def scrape_wasalt():
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    except ImportError:
        print("Playwright not installed: pip install playwright && playwright install chromium")
        return []

    print("Scraping Wasalt (JavaScript-rendered, using Playwright) ...")
    records = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        page = browser.new_context(user_agent=USER_AGENT, locale="en-US").new_page()

        blocked_site = False
        for seed in WS_SEEDS:
            listing_type = "rent" if "for-rent" in seed else "sale"
            for n in range(1, WS_MAX_PAGES_PER_SEED + 1):
                url = seed if n == 1 else f"{seed}?page={n}"     # pagination pattern from the report
                if not allowed(url):
                    print(f"  robots.txt disallows {url}; skipping seed")
                    break
                resp = None
                try:
                    resp = page.goto(url, wait_until="domcontentloaded", timeout=45000)
                    page.wait_for_selector(WS_CARD_LINK, timeout=15000)
                    page.wait_for_timeout(1000)
                except PWTimeout:
                    if diagnose(f"wasalt p{n}", page.content(), resp.status if resp else None):
                        blocked_site = True
                    os.makedirs("data/debug", exist_ok=True)
                    page.screenshot(path="data/debug/wasalt_no_cards.png", full_page=True)
                    print(f"  {url}: no listing cards (see data/debug/wasalt_no_cards.png)")
                    break
                cards = page.evaluate(_CARD_JS, WS_CARD_LINK)
                if not cards:
                    if diagnose(f"wasalt p{n}", page.content(), resp.status if resp else None):
                        blocked_site = True
                        break
                new = 0
                for c in cards:
                    if c["href"] not in records:
                        records[c["href"]] = parse_wasalt_card(c, listing_type)
                        new += 1
                print(f"  {url}: {len(cards)} cards, {new} new")
                if new == 0:
                    break
                time.sleep(DELAY_SECONDS)
            if blocked_site:
                print("  Wasalt served a bot challenge. Stopping the whole site (not retrying). "
                      "Keeping what was collected so far.")
                break

        if WS_FETCH_DETAILS:
            for i, r in enumerate(records.values(), 1):
                print(f"  detail [{i}/{len(records)}] {r['url']}")
                try:
                    page.goto(r["url"], wait_until="domcontentloaded", timeout=45000)
                    page.wait_for_timeout(1500)
                    meta_desc, text = extract_detail(page.content())
                    r["detail_text"] = text[:8000]
                    if meta_desc:
                        r["description"] = f"{r['description']} {meta_desc}"
                except Exception as e:
                    print(f"    skipped ({e})")
                time.sleep(DELAY_SECONDS)
        browser.close()
    return list(records.values())


# ----------------------------------------------------------------- main
def main():
    results = {}
    for name, fn in (("darglobal", scrape_darglobal), ("wasalt", scrape_wasalt)):
        try:
            results[name] = fn()
        except Exception as e:
            print(f"[error] {name} failed: {e}")
            results[name] = []

    total = 0
    for name, records in results.items():
        if records:
            write_jsonl(os.path.join(RAW_DIR, f"{name}.jsonl"), records)
        else:
            print(f"[warn] {name}: 0 records. Not writing a file; check selectors/robots. "
                  f"(No sample data is generated.)")
        total += len(records)
        print(f"{name}: {len(records)} records")

    if total == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()

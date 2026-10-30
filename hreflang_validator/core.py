"""Check hreflang annotations: codes, self references, return links, x-default and canonical conflicts.

Rules follow Google Search Central's guidance on localized versions, plus general best practice:
- every hreflang URL must be absolute and return 200,
- every page should list itself and every alternate must link back (return link),
- the alternate should be canonical and indexable, or Google ignores the pair,
- codes are a language (ISO 639-1), optionally followed by a region (ISO 3166-1), or x-default,
- one code per page set, plus an x-default for users that match no version.
NP stat (global-internet-users-by-language): "Use Hreflang Correctly" is one of its actionable insights.
"""
import re
import time
from collections import deque
from urllib.parse import urljoin, urlsplit, urlunsplit
from xml.etree import ElementTree

import pandas as pd
import requests
from bs4 import BeautifulSoup

USER_AGENT = "hreflang-validator/1.0 (+https://github.com/marketing-MEER/hreflang-validator)"
SEVERITY = {"error": 0, "warning": 1, "notice": 2}

# A hand-picked set of language codes that sites use most often. A code outside this set is not
# wrong by itself; the tool only asks you to double-check it.
COMMON_LANGS = set(
    "ar bg bn ca cs da de el en es et fa fi fr he hi hr hu id it ja ko lt lv ms nb nl no pl pt "
    "ro ru sk sl sr sv th tl tr uk ur vi zh".split())
# Country codes people often use by mistake where a language code belongs.
COUNTRY_NOT_LANGUAGE = {"jp": "ja", "cz": "cs", "dk": "da", "se": "sv", "gr": "el", "kr": "ko",
                        "cn": "zh", "ua": "uk", "ee": "et", "si": "sl", "at": "de", "ch": "de",
                        "br": "pt", "mx": "es", "gb": "en", "us": "en", "in": "hi", "ir": "fa",
                        "il": "he", "vn": "vi", "rs": "sr", "my": "ms"}
# Region codes that are not ISO 3166-1 country codes.
REGION_FIXES = {"uk": "gb", "eu": "(no EU code; list countries)", "la": "419 (Latin America)"}
CODE_RE = re.compile(r"^([a-z]{2,3})(?:-([a-z]{4}))?(?:-([a-z]{2}|\d{3}))?$", re.I)


def check_code(code: str):
    """Return (severity, problem) or None when the code looks fine."""
    c = code.strip().lower()
    if c == "x-default":
        return None
    m = CODE_RE.match(c)
    if not m:
        if "_" in c:
            return "error", f"Uses an underscore; write it as {c.replace('_', '-')}"
        return "error", "Not a language or language-region code"
    lang, _, region = m.groups()
    if lang in COUNTRY_NOT_LANGUAGE:
        return "error", f"'{lang}' is a country code, not a language (did you mean {COUNTRY_NOT_LANGUAGE[lang]}?)"
    if region and region in REGION_FIXES:
        return "error", f"Region '{region}' is not a valid country code; use {REGION_FIXES[region]}"
    if lang not in COMMON_LANGS:
        return "notice", f"'{lang}' is not a common language code; check it is ISO 639-1"
    return None


def norm(url: str) -> str:
    """Normalise a URL for comparison: lower-case scheme and host, drop the fragment."""
    p = urlsplit(url.strip())
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path or "/", p.query, ""))


class Fetcher:
    """Polite GETs: own user agent, at least 0.5 s between requests, redirects not followed."""

    def __init__(self, delay: float = 0.5, timeout: float = 20, session=None):
        self.delay, self.timeout = max(delay, 0.5), timeout
        self.session = session or requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self._last = 0.0
        self.requests = 0

    def get(self, url):
        wait = self.delay - (time.monotonic() - self._last)
        if wait > 0 and self.requests:
            time.sleep(wait)
        self._last = time.monotonic()
        self.requests += 1
        try:
            return self.session.get(url, timeout=self.timeout, allow_redirects=False)
        except requests.RequestException as exc:
            return exc


def parse_link_header(value: str, base: str):
    """hreflang entries from an HTTP Link header (used for PDFs and other non-HTML files)."""
    out = []
    for part in value.split(","):
        m = re.search(r"<([^>]+)>", part)
        lang = re.search(r'hreflang\s*=\s*"?([^";]+)"?', part, re.I)
        if m and lang and re.search(r'rel\s*=\s*"?alternate', part, re.I):
            out.append((lang.group(1).strip(), m.group(1).strip(), "http header"))
    return out


def fetch_page(url: str, fetch: Fetcher) -> dict:
    info = {"url": url, "status": None, "location": "", "canonical": "", "noindex": False,
            "hreflang": [], "error": ""}
    resp = fetch.get(url)
    if isinstance(resp, Exception):
        info["status"], info["error"] = "failed", str(resp)[:150]
        return info
    info["status"] = resp.status_code
    info["location"] = urljoin(url, resp.headers.get("Location", "")) if resp.is_redirect else ""
    if "noindex" in resp.headers.get("X-Robots-Tag", "").lower():
        info["noindex"] = True
    if resp.headers.get("Link"):
        info["hreflang"] += parse_link_header(resp.headers["Link"], url)
    if resp.status_code != 200 or "html" not in resp.headers.get("Content-Type", "html"):
        return info
    soup = BeautifulSoup(resp.text, "html.parser")
    for link in soup.find_all("link", href=True):
        rel = [r.lower() for r in (link.get("rel") or [])]
        if "canonical" in rel and not info["canonical"]:
            info["canonical"] = urljoin(url, link["href"].strip())
        if "alternate" in rel and link.get("hreflang"):
            info["hreflang"].append((link["hreflang"].strip(), link["href"].strip(), "html"))
    for meta in soup.find_all("meta", attrs={"name": re.compile(r"^(robots|googlebot)$", re.I)}):
        if "noindex" in (meta.get("content") or "").lower():
            info["noindex"] = True
    return info


def read_sitemap(url: str, fetch: Fetcher):
    """URLs and xhtml:link hreflang entries from one sitemap (indexes are followed one level)."""
    urls, notes = [], {}
    resp = fetch.get(url)
    if isinstance(resp, Exception) or resp.status_code != 200:
        return urls, notes
    try:
        root = ElementTree.fromstring(resp.content)
    except ElementTree.ParseError:
        return urls, notes
    tag = root.tag.split("}")[-1]
    if tag == "sitemapindex":
        for loc in root.iter():
            if loc.tag.endswith("loc") and loc.text:
                u, n = read_sitemap(loc.text.strip(), fetch)
                urls += u
                notes.update(n)
        return urls, notes
    for node in root:
        loc = next((c.text.strip() for c in node if c.tag.endswith("loc") and c.text), None)
        if not loc:
            continue
        urls.append(loc)
        for c in node:
            if c.tag.endswith("link") and c.get("rel") == "alternate" and c.get("hreflang"):
                notes.setdefault(norm(loc), []).append((c.get("hreflang"), c.get("href", ""), "sitemap"))
    return urls, notes


def _issue(rows, page, severity, issue, detail="", code="", target=""):
    rows.append({"page": page, "severity": severity, "issue": issue, "hreflang": code,
                 "target": target, "detail": detail})


def crawl(start_urls, fetch: Fetcher, sitemap_notes=None, max_pages=300):
    """Fetch the start URLs and every hreflang target on the same hosts, up to max_pages."""
    hosts = {urlsplit(u).netloc.lower() for u in start_urls}
    pages, queue, seen = {}, deque(), set()
    for u in start_urls:
        if norm(u) not in seen:
            seen.add(norm(u))
            queue.append(u)
    sitemap_notes = sitemap_notes or {}
    while queue and len(pages) < max_pages:
        url = queue.popleft()
        info = fetch_page(url, fetch)
        info["hreflang"] += sitemap_notes.get(norm(url), [])
        pages[norm(url)] = info
        for _, href, _ in info["hreflang"]:
            target = urljoin(url, href)
            if urlsplit(target).netloc.lower() in hosts and norm(target) not in seen:
                seen.add(norm(target))
                queue.append(target)
    return pages


def analyse(pages: dict):
    """Turn crawled pages into issues, an annotation table and a page table."""
    issues, notes, rows = [], [], []
    for key, p in pages.items():
        url, tags = p["url"], p["hreflang"]
        indexable = p["status"] == 200 and not p["noindex"]
        canonical_ok = not p["canonical"] or norm(p["canonical"]) == key
        codes = {}
        for code, href, source in tags:
            target = urljoin(url, href)
            codes.setdefault(code.lower(), set()).add(norm(target))
            if not re.match(r"^https?://", href, re.I):
                _issue(issues, url, "error", "hreflang URL is relative", "Use the full URL with https://", code, href)
            bad = check_code(code)
            if bad:
                _issue(issues, url, bad[0], "Invalid or unusual hreflang code", bad[1], code, target)
        if not tags:
            if p["status"] == 200:
                _issue(issues, url, "notice", "No hreflang annotations on this page")
        else:
            if p["status"] != 200:
                _issue(issues, url, "error", f"Page with hreflang returns {p['status']}", p["location"])
            if not canonical_ok:
                _issue(issues, url, "error", "hreflang on a page that canonicalises elsewhere",
                       f"canonical: {p['canonical']}. Put hreflang on the canonical URL only.")
            if p["noindex"]:
                _issue(issues, url, "warning", "hreflang on a noindex page", "Google will not show it in any language")
            self_codes = [c for c, ts in codes.items() if key in ts and c != "x-default"]
            if not self_codes:
                _issue(issues, url, "warning", "No self-referencing hreflang", "List the page itself in its own set")
            if "x-default" not in codes:
                _issue(issues, url, "notice", "No x-default", "Tell Google which page to show users who match no version")
            for code, ts in codes.items():
                if len(ts) > 1:
                    _issue(issues, url, "error", "Same hreflang code points to different URLs",
                           " | ".join(sorted(ts)), code)
        for code, href, source in tags:
            target = urljoin(url, href)
            t = pages.get(norm(target))
            row = {"page": url, "hreflang": code, "target": target, "source": source,
                   "target_status": "not checked", "return_link": "not checked", "target_canonical": ""}
            if t is not None and norm(target) != key:
                row["target_status"] = t["status"]
                back = [c for c, h, _ in t["hreflang"] if norm(urljoin(t["url"], h)) == key]
                row["return_link"] = ("yes" if back else "no") if t["status"] == 200 else "n/a"
                row["target_canonical"] = t["canonical"]
                if t["status"] != 200:
                    _issue(issues, url, "error", f"hreflang target returns {t['status']}",
                           t["location"] or t["error"], code, target)
                elif t["canonical"] and norm(t["canonical"]) != norm(target):
                    _issue(issues, url, "error", "hreflang target canonicalises elsewhere",
                           f"canonical: {t['canonical']}", code, target)
                elif t["noindex"]:
                    _issue(issues, url, "error", "hreflang target is noindex", "", code, target)
                if not back and t["status"] == 200:
                    _issue(issues, url, "error", "No return link from the alternate page",
                           "Both pages must point to each other or Google ignores the pair", code, target)
            elif norm(target) == key:
                row["target_status"], row["return_link"] = p["status"], "self"
            notes.append(row)
        rows.append({"url": url, "status": p["status"], "canonical": p["canonical"],
                     "indexable": "yes" if indexable else "no", "hreflang_tags": len(tags),
                     "languages": ", ".join(sorted(codes)), "self_reference": "yes" if any(
                         key in ts for c, ts in codes.items() if c != "x-default") else "no",
                     "x_default": "yes" if "x-default" in codes else "no"})
    issues_df = pd.DataFrame(issues, columns=["page", "severity", "issue", "hreflang", "target", "detail"])
    if not issues_df.empty:
        issues_df = issues_df.sort_values(["severity", "page"], key=lambda s: s.map(SEVERITY) if s.name == "severity" else s)
    notes_df = pd.DataFrame(notes, columns=["page", "hreflang", "target", "source", "target_status",
                                            "return_link", "target_canonical"])
    pages_df = pd.DataFrame(rows, columns=["url", "status", "canonical", "indexable", "hreflang_tags",
                                           "languages", "self_reference", "x_default"])
    return issues_df.reset_index(drop=True), notes_df, pages_df


def summarise(issues: pd.DataFrame) -> pd.DataFrame:
    cols = ["issue", "severity", "count", "pages"]
    if issues.empty:
        return pd.DataFrame(columns=cols)
    g = issues.groupby(["issue", "severity"]).agg(count=("page", "size"), pages=("page", "nunique")).reset_index()
    g["rank"] = g["severity"].map(SEVERITY)
    return g.sort_values(["rank", "count"], ascending=[True, False])[cols].reset_index(drop=True)


def read_inputs(source: str, fetch: Fetcher):
    """A URL, a sitemap URL (.xml) or a text/CSV file with one URL per line. Returns (urls, sitemap notes)."""
    if re.match(r"^https?://", source, re.I):
        if urlsplit(source).path.lower().endswith((".xml", ".xml.gz")):
            return read_sitemap(source, fetch)
        return [source], {}
    urls = []
    with open(source, encoding="utf-8-sig") as fh:
        for line in fh:
            m = re.search(r"https?://[^\s,;\"']+", line)
            if m:
                urls.append(m.group(0))
    return urls, {}


def audit(source: str, delay=0.5, max_pages=300, fetch=None):
    fetch = fetch or Fetcher(delay=delay)
    urls, notes = read_inputs(source, fetch)
    pages = crawl(urls, fetch, notes, max_pages=max_pages)
    issues, annotations, page_df = analyse(pages)
    return {"start_urls": urls, "pages": page_df, "annotations": annotations, "issues": issues,
            "summary": summarise(issues), "requests": fetch.requests}

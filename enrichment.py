"""Domain parsing and free-text company website scraping."""
import re
import requests
from bs4 import BeautifulSoup

FREE_EMAIL_DOMAINS = {
    "gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "icloud.com",
    "aol.com", "live.com", "msn.com", "protonmail.com", "mail.com",
}

GENERIC_LOCAL_PARTS = {
    "info", "sales", "support", "admin", "contact", "noreply", "no-reply",
    "hello", "office", "help", "service", "team",
}

REQUEST_TIMEOUT = 6
USER_AGENT = "Mozilla/5.0 (compatible; OspreyOutreachBot/1.0)"


def parse_contact(row: dict) -> dict:
    email = (row.get("email") or "").strip()
    local_part, _, domain = email.partition("@")
    domain = domain.lower().strip()

    name = (row.get("name") or "").strip()
    if not name:
        name = local_part.replace(".", " ").replace("_", " ").title()

    company = (row.get("company") or "").strip()
    if not company and domain:
        company = domain.split(".")[0].replace("-", " ").title()

    return {
        "email": email,
        "name": name,
        "company": company,
        "domain": domain,
        "is_generic_inbox": local_part.lower() in GENERIC_LOCAL_PARTS,
        "is_free_email": domain in FREE_EMAIL_DOMAINS,
    }


def scrape_company_site(domain: str) -> str | None:
    """Best-effort fetch of the company homepage (and /about) as plain text."""
    if not domain:
        return None

    text_parts = []
    for path in ("/", "/about", "/about-us"):
        for base in (f"https://{domain}", f"https://www.{domain}"):
            html = _fetch(base + path)
            if html:
                text_parts.append(_extract_text(html))
                break
        if path == "/" and not text_parts:
            # homepage failed on both hosts, no point trying /about
            break

    combined = "\n".join(p for p in text_parts if p)
    return combined[:3000] if combined else None


def _fetch(url: str) -> str | None:
    try:
        resp = requests.get(
            url, timeout=REQUEST_TIMEOUT, headers={"User-Agent": USER_AGENT}
        )
        if resp.status_code < 400 and resp.text:
            return resp.text
    except requests.RequestException:
        pass
    return None


def _extract_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "noscript"]):
        tag.decompose()

    title = soup.title.string.strip() if soup.title and soup.title.string else ""
    meta_desc = ""
    meta = soup.find("meta", attrs={"name": "description"})
    if meta and meta.get("content"):
        meta_desc = meta["content"].strip()

    body_text = soup.get_text(separator=" ", strip=True)
    body_text = re.sub(r"\s+", " ", body_text)

    parts = [p for p in (title, meta_desc, body_text) if p]
    return " | ".join(parts)

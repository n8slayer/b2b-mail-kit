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

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")

EMAIL_HEADERS = {"email", "e mail", "email address", "contact email", "work email", "business email"}
COMPANY_HEADERS = {"company", "company name", "organization", "organisation", "employer", "business", "account name", "account"}
FIRST_NAME_HEADERS = {"first name", "firstname", "first", "given name"}
LAST_NAME_HEADERS = {"last name", "lastname", "last", "surname", "family name"}
NAME_HEADERS = {"name", "full name", "fullname", "contact name", "contact", "contact person"}


def _normalize_header(header: str) -> str:
    header = (header or "").strip().lower()
    header = re.sub(r"[_\-]+", " ", header)
    return re.sub(r"\s+", " ", header)


def map_columns(fieldnames: list[str], rows: list[dict]) -> dict:
    """Guess which column holds email/name/company from arbitrary CSV headers."""
    normalized = {f: _normalize_header(f) for f in fieldnames}
    used = set()

    def pick(exact: set, contains: str | None = None):
        for field, norm in normalized.items():
            if field not in used and norm in exact:
                used.add(field)
                return field
        if contains:
            for field, norm in normalized.items():
                if field not in used and contains in norm:
                    used.add(field)
                    return field
        return None

    email_col = pick(EMAIL_HEADERS, contains="mail")
    if not email_col:
        # no header looks like an email column; find whichever column's values
        # actually look like email addresses
        best_field, best_score = None, 0
        for field in fieldnames:
            if field in used:
                continue
            score = sum(1 for r in rows[:25] if EMAIL_RE.search(r.get(field) or ""))
            if score > best_score:
                best_field, best_score = field, score
        if best_field:
            email_col = best_field
            used.add(best_field)

    return {
        "email": email_col,
        "company": pick(COMPANY_HEADERS, contains="compan"),
        "first_name": pick(FIRST_NAME_HEADERS),
        "last_name": pick(LAST_NAME_HEADERS),
        "name": pick(NAME_HEADERS, contains="name"),
    }


def extract_fields(row: dict, column_map: dict) -> dict:
    """Pull email/name/company out of a raw CSV row using a column map."""
    email = ""
    email_col = column_map.get("email")
    if email_col:
        match = EMAIL_RE.search(row.get(email_col) or "")
        if match:
            email = match.group(0)
    if not email:
        for value in row.values():
            match = EMAIL_RE.search(value or "")
            if match:
                email = match.group(0)
                break

    name = ""
    if column_map.get("name"):
        name = (row.get(column_map["name"]) or "").strip()
    else:
        first = (row.get(column_map["first_name"]) or "").strip() if column_map.get("first_name") else ""
        last = (row.get(column_map["last_name"]) or "").strip() if column_map.get("last_name") else ""
        name = f"{first} {last}".strip()

    company = (row.get(column_map["company"]) or "").strip() if column_map.get("company") else ""

    return {"email": email, "name": name, "company": company}


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

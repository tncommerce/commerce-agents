"""Reuse PR776 c00eaad1 exact identity guards, without the 33-product CLI.

Copied unchanged pure guards; keep flanker/concentration equality and preserve
the distinction between name matching and independently verified size.
"""

import re
import unicodedata
from urllib.parse import urlsplit

ADVERTISER = "31081"
FEED = "91379"
MERCHANT = "top-parfuemerie"
RIGHTS_BASIS = "awin_top_parfuemerie_feed_materials_20260928"
PHOTO_PATH = re.compile(
    r"/media/catalog/product/(?:[a-z0-9]/){0,3}[a-z0-9_-]+\.(?:png|jpe?g|webp)$",
    re.IGNORECASE,
)
VOLUME = re.compile(r"(?<![\d.,])(\d+(?:[.,]\d+)?)\s*(?:ml|milliliter)(?!\w)", re.I)
# Only presentation words are dispensable. Variant words and concentration
# markers must participate in equality, never a one-way subset match.
STOP = {
    "perfume",
    "perfumes",
    "parfums",
    "spray",
    "nat",
    "vapo",
    "flacon",
    "flasche",
}
CONCENTRATIONS = (
    (r"\b(?:extrait de parfum|extrait)\b", "strength_extrait"),
    (r"\b(?:eau de parfum|edp)\b", "strength_edp"),
    (r"\b(?:eau de toilette|edt)\b", "strength_edt"),
    (r"\b(?:eau de cologne|edc)\b", "strength_edc"),
    (r"\bparfum\b", "strength_parfum"),
)
MULTIPACK = re.compile(r"[+×/]|\b\d+\s*[xX]\s*\d|\b\d+\s*(?:teilig|pcs|stuck)\b")
MAX_CANDIDATES = 3


def norm(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    return re.sub(
        r"\s+",
        " ",
        "".join(
            ch.lower() if ch.isalnum() else " " for ch in text if not unicodedata.combining(ch)
        ),
    ).strip()


def safe_feed_image(value: object) -> str | None:
    url = str(value or "").strip()
    try:
        p = urlsplit(url)
        safe = (
            p.scheme == "https"
            and p.hostname in {"topparfuemerie.de", "www.topparfuemerie.de"}
            and p.port is None
            and p.username is None
            and p.password is None
            and not p.query
            and not p.fragment
            and PHOTO_PATH.fullmatch(p.path) is not None
        )
    except ValueError:
        return None
    return url if safe else None


def feed_name_matches(item: dict, row: dict) -> bool:
    def identity(value: object) -> set[str]:
        label = norm(VOLUME.sub(" ", str(value or "")))
        # Bounded spellings observed in the official review artifact 11715220608.
        # Do not globally discard "by", perfumer names or refill qualifiers.
        if item.get("product_id") == "SC-ESSENTIAL-PARFUMS-BOIS-IMPERIAL-100":
            label = label.replace("bois imperial by quentin bisch", "bois imperial")
            label = label.replace("nat spray nachfullbar", "nat spray")
        if item.get("brand") == "Giorgio Armani":
            label = label.replace("giorgio armani emporio armani", "giorgio armani")
        for pattern, marker in CONCENTRATIONS:
            label = re.sub(pattern, marker, label)
        return set(label.split()) - STOP

    title = str(row.get("product_name") or "")
    if MULTIPACK.search(title):
        return False
    quantities = [float(v.replace(",", ".")) for v in VOLUME.findall(title)]
    expected = int(item.get("volume_ml") or 0)
    if expected <= 0 or (quantities and quantities != [expected]):
        return False
    names = identity(item.get("name"))
    brands = identity(item.get("brand"))
    concentration = identity(item.get("concentration"))
    if not names or not brands or not concentration:
        return False
    # Equality rejects both missing and additional flanker/edition words,
    # sets, refills and body products. Missing size remains an unverified lead
    # for compatibility with feed titles that omit volume, never a size claim.
    return identity(title) == names | brands | concentration

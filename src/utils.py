# src/utils.py
from urllib.parse import urlparse, parse_qs

def extract_prod_sn(url):
    """
    Extracts the onlineProdSn from a given URL.
    """
    try:
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        if "onlineProdSn" in query:
            return query["onlineProdSn"][0]
    except Exception:
        pass
    return None


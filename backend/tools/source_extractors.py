"""
Tier 1 Hardcoded Extractors for Zero-LLM Lead Discovery.
"""
import asyncio
import re
import json
import logging
from urllib.parse import quote
from bs4 import BeautifulSoup
import httpx

logger = logging.getLogger(__name__)

# Standard headers to bypass basic blocks
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

def _extract_areas_from_address(address: str, city: str) -> list[str]:
    """Dynamically extract neighbourhood/locality names from an address."""
    if not address or not city:
        return []
    areas = []
    cleaned = address.replace(city, "").strip(", ")
    parts = [p.strip() for p in cleaned.split(",") if p.strip()]
    for part in parts:
        words = part.split()
        if 1 <= len(words) <= 4 and not re.match(r'^\d+$', part):
            if len(part) > 4 and part.lower() not in {city.lower(), "india", ""}:
                areas.append(part)
    return areas[:2]

async def extract_google_maps(query: str, city: str, max_areas: int = 5) -> list[dict]:
    """
    Extracts from Google Maps by parsing the embedded JSON data.
    Implements dynamic area discovery by extracting neighbourhoods from addresses.
    """
    all_leads = []
    seen_names = set()
    discovered_areas = set()
    area_queue = [city]
    searched_areas = set()
    areas_done = 0
    
    # httpx AsyncClient for connection pooling
    async with httpx.AsyncClient(headers=_HEADERS, follow_redirects=True) as client:
        while area_queue and areas_done < max_areas:
            area = area_queue.pop(0)
            if area in searched_areas:
                continue
            searched_areas.add(area)
            areas_done += 1
            
            search_term = f"{query} in {area}"
            url = f"https://www.google.com/maps/search/{quote(search_term)}/"
            logger.info("GMaps Tier 1 scraping: %s", search_term)
            
            try:
                resp = await client.get(url, timeout=10.0)
                if resp.status_code != 200:
                    continue
                    
                match = re.search(r'window\.APP_INITIALIZATION_STATE=\[\[(.*?)\]\];', resp.text)
                if not match:
                    continue
                    
                raw_json = "[[" + match.group(1) + "]]"
                data = json.loads(raw_json)
                
                # Helper to recursively find objects that look like businesses
                def find_businesses(obj, results):
                    if isinstance(obj, list):
                        if len(obj) > 14 and isinstance(obj[14], list) and len(obj[14]) > 11 and isinstance(obj[14][11], str):
                            results.append(obj)
                        for item in obj:
                            find_businesses(item, results)

                businesses = []
                find_businesses(data, businesses)
                
                for b in businesses:
                    try:
                        name = b[14][11]
                        if not name or name.lower() in seen_names:
                            continue
                        seen_names.add(name.lower())
                        
                        address = ""
                        if len(b[14]) > 18 and isinstance(b[14][18], str):
                            address = b[14][18]
                        elif len(b[14]) > 2 and isinstance(b[14][2], list) and b[14][2]:
                            address = ", ".join(str(x) for x in b[14][2] if x)
                            
                        phone = ""
                        try:
                            if len(b[14]) > 178 and b[14][178] and b[14][178][0] and b[14][178][0][0]:
                                phone = str(b[14][178][0][0])
                        except Exception:
                            pass
                            
                        website = ""
                        try:
                            if len(b[14]) > 7 and b[14][7] and b[14][7][0]:
                                website = str(b[14][7][0])
                        except Exception:
                            pass
                            
                        source_url = url
                        try:
                            if len(b[14]) > 9 and b[14][9] and b[14][9][0]:
                                source_url = str(b[14][9][0])
                        except Exception:
                            source_url = f"https://www.google.com/maps/search/{quote(name)}"

                        lead = {
                            "name": name,
                            "address": address,
                            "phone": phone,
                            "website_url": website,
                            "source_url": source_url,
                            "social_media_url": ""
                        }
                        all_leads.append(lead)
                        
                        # Extract areas for recursive search
                        new_areas = _extract_areas_from_address(address, city)
                        for na in new_areas:
                            if na not in searched_areas and na not in discovered_areas:
                                discovered_areas.add(na)
                                area_queue.append(na)
                    except Exception as e:
                        logger.debug("Failed to parse a Gmaps business entry: %s", e)
                        continue
                        
            except Exception as e:
                logger.warning("Tier 1 Google Maps extraction failed for %s: %s", area, e)
                
    if not all_leads:
        logger.info("JSON Tier 1 GMaps returned 0 leads. Falling back to Tier 2.5 Visual Scraper.")
        from tools.visual_gmaps_scraper import visual_scrape_gmaps
        all_leads = await visual_scrape_gmaps(query, city)
        
    return all_leads


async def extract_google_search(query: str) -> list[dict]:
    """Tier 1: Parses organic Google Search results (div.g)."""
    url = f"https://www.google.com/search?q={quote(query)}&num=20"
    all_leads = []
    
    async with httpx.AsyncClient(headers=_HEADERS, follow_redirects=True) as client:
        try:
            resp = await client.get(url, timeout=10.0)
            if resp.status_code != 200:
                return []
                
            soup = BeautifulSoup(resp.text, "lxml")
            blocks = soup.select("div.g")
            
            for block in blocks:
                title_el = block.select_one("h3")
                link_el = block.select_one("a[href]")
                
                if not title_el or not link_el:
                    continue
                    
                name = title_el.get_text(strip=True)
                href = link_el["href"]
                
                if href.startswith("/search") or "google.com" in href:
                    continue
                    
                all_leads.append({
                    "name": name,
                    "address": "",
                    "phone": "",
                    "website_url": href if not href.startswith("http") and "linkedin" not in href else "",
                    "source_url": href,
                    "social_media_url": href if "linkedin.com" in href or "instagram.com" in href or "facebook.com" in href or "twitter.com" in href else ""
                })
        except Exception as e:
            logger.warning("Tier 1 Google Search extraction failed: %s", e)
            
    return all_leads

async def extract_from_source(source: str, query: str, location: str) -> list[dict]:
    """
    Dispatcher for Tier 1 extractors.
    source should be one of: google_maps, google_search, linkedin_dork, etc.
    """
    try:
        if source == "google_maps":
            return await extract_google_maps(query, location)
        elif source == "google_search":
            return await extract_google_search(f"{query} {location}")
        elif source == "linkedin_dork":
            return await extract_google_search(f'site:linkedin.com/in OR site:linkedin.com/company "{query}" "{location}"')
        elif source == "social_dorks":
            return await extract_google_search(f'site:instagram.com OR site:facebook.com OR site:twitter.com "{query}" "{location}"')
        elif source == "sebi_advisors":
            return await extract_google_search(f'site:sebi.gov.in "{query}" "{location}"')
        elif source in ["justdial", "sulekha", "indiamart", "tradeindia", "yellowpages"]:
            return await extract_google_search(f'site:{source}.com "{query}" "{location}"')
    except Exception as e:
        logger.error("Error in Tier 1 dispatcher for %s: %s", source, e)
        
    return []

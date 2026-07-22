"""
Tier 2.5: Visual Playwright Scraper for Google Maps.
Invoked dynamically if the Tier 1 JSON HTTP method fails or is blocked.
Uses CloakBrowser for maximum stealth and human-like scrolling.
"""
import asyncio
import random
import re
import logging
from urllib.parse import quote

from tools.stealth_browser import get_stealth_browser

logger = logging.getLogger(__name__)

async def _human_scroll(page, selector: str, scrolls: int = 4):
    """Mimic a human scrolling down a side panel with variable delays."""
    panel = await page.query_selector(selector)
    if not panel:
        return
        
    for _ in range(scrolls):
        # Move mouse near the panel randomly
        try:
            box = await panel.bounding_box()
            if box:
                x = box['x'] + random.uniform(10, box['width'] - 10)
                y = box['y'] + random.uniform(10, box['height'] - 10)
                await page.mouse.move(x, y, steps=random.randint(5, 15))
        except Exception:
            pass
            
        # Scroll the panel
        await panel.evaluate("el => el.scrollTop += (el.clientHeight * 0.8)")
        await asyncio.sleep(random.uniform(0.7, 1.8))


async def visual_scrape_gmaps(query: str, location: str, max_results: int = 15) -> list[dict]:
    """
    Launches CloakBrowser, navigates to GMaps, scrolls, and extracts business cards.
    Does NOT use the LLM (zero tokens).
    """
    search_term = f"{query} in {location}"
    url = f"https://www.google.com/maps/search/{quote(search_term)}/"
    
    logger.info("Tier 2.5 Visual GMaps Fallback invoked for: %s", search_term)
    
    leads = []
    seen_names = set()
    
    playwright, browser = await get_stealth_browser()
    try:
        page = browser.contexts[0].pages[0] if browser.contexts and browser.contexts[0].pages else await browser.new_page()
        
        await page.goto(url, wait_until="domcontentloaded", timeout=45000)
        await asyncio.sleep(random.uniform(2.5, 4.0)) # Let JS settle
        
        # Scroll the left feed panel to load results
        await _human_scroll(page, '[role="feed"]', scrolls=5)
        
        # Find all business cards
        listings = await page.query_selector_all('.Nv2PK')
        if not listings:
            listings = await page.query_selector_all('[data-result-index]')
            
        logger.info("Visual scraper found %d cards in UI.", len(listings))
        
        for idx, listing in enumerate(listings):
            if len(leads) >= max_results:
                break
                
            try:
                # Scroll element into view smoothly
                await listing.scroll_into_view_if_needed()
                
                # We can extract text without clicking if we just want basic info
                text_content = await listing.inner_text()
                lines = [line.strip() for line in text_content.split('\n') if line.strip()]
                
                if not lines:
                    continue
                    
                name = lines[0]
                if name.lower() in seen_names:
                    continue
                    
                # The visual card text varies widely. E.g.
                # "Smith Finance"
                # "4.5 (20) · Financial Advisor"
                # "Mumbai, Maharashtra · Open 24 hours"
                # "099999 99999"
                
                # Let's extract safely what we can
                phone = ""
                website = ""
                address = ""
                
                # Look for a phone number format in the lines
                for line in lines:
                    phone_match = re.search(r'(\+91[\-\s]?)?[0-9]{4,5}[\-\s]?[0-9]{5,6}', line)
                    if phone_match:
                        phone = phone_match.group(0)
                        
                # Look for the website button's href inside this card
                web_btn = await listing.query_selector('a[data-value="Website"]')
                if web_btn:
                    website = await web_btn.get_attribute('href') or ""
                    
                # To get address accurately, we'd normally have to click the card to open the detail pane.
                # To save time and keep it stable, we just rely on what is in the feed card.
                # Often address is lines[2] or lines[3] but it's risky to guess. 
                # We'll leave it empty if we can't be sure, Enrichment will fix it later.
                
                source_url = url
                link_el = await listing.query_selector('a.hfpxzc')
                if link_el:
                    source_url = await link_el.get_attribute('href') or url
                    
                seen_names.add(name.lower())
                leads.append({
                    "name": name,
                    "address": address,
                    "phone": phone,
                    "website_url": website,
                    "source_url": source_url,
                    "social_media_url": ""
                })
                
            except Exception as e:
                logger.debug("Visual extraction error on card %d: %s", idx, e)
                
    except Exception as e:
        logger.error("Tier 2.5 Visual Scraper completely failed: %s", e)
    finally:
        await browser.close()
        
    return leads

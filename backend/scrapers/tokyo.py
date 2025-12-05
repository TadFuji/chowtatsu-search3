from typing import List
from playwright.async_api import async_playwright
from .base import BaseScraper, BidItem, normalize_date
import logging

logger = logging.getLogger(__name__)

class TokyoMetroScraper(BaseScraper):
    async def search(self, keyword: str, category: str) -> List[BidItem]:
        results = []
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                locale="ja-JP"
            )
            page = await context.new_page()
            
            try:
                await page.goto("https://www.e-procurement.metro.tokyo.lg.jp/indexPbi.jsp", timeout=60000)
                await page.wait_for_load_state("networkidle")
                
                # Click "発注予定情報" (Order Schedule)
                await page.evaluate("SelectTargetSubmit(3,3,'_top')")
                await page.wait_for_load_state("networkidle")
                await page.wait_for_timeout(2000)
                
                # Select Category
                target_selector = "input[name='constConsgoods']" # Default Construction
                if category == "goods":
                    target_selector = "input[name='itemConsgoods']"
                
                await page.check(target_selector)
                
                # Input Keyword
                if keyword:
                    await page.fill("input[name='ankenName']", keyword)
                
                # Click Search
                await page.evaluate("setTimeout(() => SelectSubmitOrder(4,1), 0)")
                await page.wait_for_timeout(5000)
                
                # Check for confirmation page
                if await page.locator("a[href*='SelectSubmit(4,3)']").count() > 0:
                    await page.evaluate("SelectSubmit(4,3)")
                    await page.wait_for_load_state("networkidle")
                
                # Wait for results
                try:
                    await page.wait_for_selector("table.list-data", timeout=10000)
                except:
                    logger.info("No results found or timeout.")
                    return []
                
                # Extract items (First page only for real-time speed)
                items = await page.evaluate("""() => {
                    const items = [];
                    const table = document.querySelector('table.list-data');
                    if (!table) return [];
                    
                    const rows = Array.from(table.querySelectorAll('tr'));
                    
                    for (let i = 1; i < rows.length; i++) {
                        const row = rows[i];
                        const cells = row.querySelectorAll('td');
                        if (cells.length < 10) continue;
                        
                        const link = row.querySelector("a[href*='SelectSubmitNo']");
                        if (!link) continue;
                        
                        const title = link.innerText.trim();
                        // Construct absolute URL? The link is JS. 
                        // We can just return the title and maybe a dummy URL or try to extract ID.
                        // The original scraper extracted href.
                        const url = "https://www.e-procurement.metro.tokyo.lg.jp/indexPbi.jsp"; // Placeholder as it's JS link
                        
                        let org = "";
                        if (cells.length > 10) {
                            org = cells[10].innerText.trim();
                        }
                        
                        let deadline = "";
                        if (cells.length > 8) {
                            deadline = cells[8].innerText.trim();
                        }
                        
                        items.push({
                            title: title,
                            url: url,
                            org: org,
                            deadline: deadline
                        });
                    }
                    return items;
                }""")
                
                for item in items:
                    results.append(BidItem(
                        title=item['title'],
                        organization=item['org'],
                        deadline=normalize_date(item['deadline']),
                        category=category,
                        url=item['url'],
                        source="Tokyo Metro"
                    ))
                    
            except Exception as e:
                logger.error(f"Error scraping Tokyo Metro: {e}")
            finally:
                await browser.close()
                
        return results

from typing import List
from playwright.async_api import async_playwright
from .base import BaseScraper, BidItem
import logging

logger = logging.getLogger(__name__)

class GovernmentPortalScraper(BaseScraper):
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
                # Direct link to search page
                search_url = "https://www.p-portal.go.jp/pps-web-biz/UAA01/OAA0100?OAA0115"
                await page.goto(search_url, timeout=60000)
                await page.wait_for_load_state("networkidle")
                
                # Select Category
                # Categories: '物品' (Goods), '役務' (Services), '工事' (Construction), '測量' (Surveying)
                # Map input category to these.
                target_cats = []
                if category == "construction":
                    target_cats = ['工事']
                elif category == "goods":
                    target_cats = ['物品']
                elif category == "services":
                    target_cats = ['役務']
                elif category == "all":
                    target_cats = ['物品', '役務', '工事']
                
                for cat in target_cats:
                    try:
                        await page.locator(f"label:has-text('{cat}')").locator("input").check()
                    except:
                        pass
                
                # Input Keyword
                if keyword:
                    try:
                        # Use the ID found in HTML: #case-name
                        await page.fill("#case-name", keyword)
                    except Exception as e:
                        logger.warning(f"Could not fill keyword: {e}")
                
                # Click Search
                # The search button ID is #OAA0102
                await page.click("#OAA0102", timeout=60000)
                
                # Wait for results
                # Wait for "a.koukoku.info-button" or similar
                try:
                    await page.wait_for_selector("a.koukoku.info-button", timeout=20000)
                except:
                    logger.info("No results found or timeout on Gov Portal.")
                    return []

                # Extract items
                items = await page.evaluate(r"""() => {
                    const items = [];
                    const rows = document.querySelectorAll('table.main-summit-info tbody tr.highlight');
                    
                    rows.forEach(row => {
                        // Title
                        const titleEl = row.querySelector('td[id$="articleNm"]');
                        const title = titleEl ? titleEl.innerText.trim() : "Unknown Title";
                        
                        // Org
                        const orgEl = row.querySelector('td[id$="procurementOrgan"]');
                        const org = orgEl ? orgEl.innerText.trim() : "Government";
                        
                        // Date (Deadline/Start Date)
                        // Found in td ending with procurementImplementNoticeBean
                        const dateTd = row.querySelector('td[id$="procurementImplementNoticeBean"]');
                        let deadline = "";
                        if (dateTd) {
                            const text = dateTd.innerText;
                            // Match pattern like 令和07年01月09日
                            const match = text.match(/令和(\d+)年(\d+)月(\d+)日/);
                            if (match) {
                                const year = parseInt(match[1]) + 2018; // Reiwa 1 = 2019, so +2018
                                const month = match[2].padStart(2, '0');
                                const day = match[3].padStart(2, '0');
                                deadline = `${year}-${month}-${day}`;
                            }
                        }
                        
                        // URL
                        // Prefer "入札" (Bid) button which has a direct link in onclick
                        let url = "";
                        const bidBtn = row.querySelector('a.info-button.keiyaku');
                        if (bidBtn) {
                            const onclick = bidBtn.getAttribute('onclick');
                            if (onclick) {
                                const match = onclick.match(/window\.open\('([^']+)'/);
                                if (match) url = match[1];
                            }
                        }
                        
                        // Fallback to "公示本文" (Public Notice) if no bid link
                        if (!url) {
                            const detailBtn = row.querySelector('a.koukoku.info-button');
                            if (detailBtn) {
                                url = detailBtn.href;
                            }
                        }
                        
                        items.push({
                            title: title,
                            org: org,
                            url: url,
                            deadline: deadline
                        });
                    });
                    return items;
                }""")
                
                for item in items:
                    url = item['url']
                    if url:
                        if url.startswith("javascript:"):
                            # Cannot link directly to javascript post actions
                            # Fallback to the search page or top page
                            url = "https://www.p-portal.go.jp/pps-web-biz/UAA01/OAA0100?OAA0115"
                        elif not url.startswith("http"):
                            url = f"https://www.p-portal.go.jp{url}"
                        
                    results.append(BidItem(
                        title=item['title'],
                        organization=item['org'],
                        deadline=item['deadline'],
                        category=category,
                        url=url,
                        source="Gov Portal"
                    ))
                    
            except Exception as e:
                logger.error(f"Error scraping Gov Portal: {e}")
            finally:
                await browser.close()
                
        return results

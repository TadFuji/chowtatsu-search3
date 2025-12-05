from typing import List
from playwright.async_api import async_playwright
from .base import BaseScraper, BidItem
import logging
import asyncio

logger = logging.getLogger(__name__)

class KanagawaScraper(BaseScraper):
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
                # 1. Top Page
                url = "http://nyusatsu.e-kanagawa.lg.jp/"
                logger.info(f"Navigating to {url}")
                await page.goto(url, timeout=60000)
                await page.wait_for_load_state("networkidle")
                
                # 2. Click "入札情報サービスシステム"
                # It opens a new window/tab usually.
                # Use a more robust way to get the new page.
                initial_pages = len(context.pages)
                await page.click("text=入札情報サービスシステム")
                await page.wait_for_timeout(3000) # Wait for potential popup
                
                if len(context.pages) > initial_pages:
                    page2 = context.pages[-1]
                    logger.info("Popup detected, switching to new page")
                else:
                    page2 = page
                    logger.info("No popup detected, continuing on same page")
                
                await page2.wait_for_load_state("networkidle")
                
                # 3. Find Menu Frame and Click "神奈川県"
                await page2.wait_for_timeout(2000)
                
                menu_frame = None
                for frame in page2.frames:
                    try:
                        if await frame.locator("text=神奈川県").count() > 0:
                            menu_frame = frame
                            break
                    except:
                        pass
                
                if menu_frame:
                    logger.info(f"Found menu frame with Kanagawa: {menu_frame.url}")
                    # Click "神奈川県" inside the frame
                    link = menu_frame.locator("a:has-text('神奈川県')").first
                    if await link.count() > 0:
                        await link.click()
                    else:
                        await menu_frame.click("text=神奈川県")
                        
                    await page2.wait_for_timeout(5000) # Wait for navigation
                    
                    # 4. Inspect frames for the specific Goods link
                    found_link = False
                    for i, frame in enumerate(page2.frames):
                        logger.info(f"Checking Frame {i}: {frame.url}")
                        try:
                            # Look for the specific link
                            link = frame.locator("a[onclick*='P6510_10']").first
                            if await link.count() > 0:
                                logger.info(f"Found Goods link in Frame {i}")
                                await link.click()
                                found_link = True
                                await page2.wait_for_timeout(5000)
                                break
                        except:
                            pass
                    
                    if found_link:
                        # Check for new pages (Search Form)
                        search_page = None
                        if len(context.pages) > initial_pages:
                            search_page = context.pages[-1]
                        else:
                            # If no new page, it might be in a frame.
                            # But usually the search form is in the main frame or a specific frame.
                            # Based on debug, it's in a frame (Frame 0 of page2).
                            # Let's find the frame with the search form.
                            for frame in page2.frames:
                                if "検索条件入力" in await frame.content():
                                    search_page = frame
                                    break
                        
                        if search_page:
                            logger.info("Found search form page/frame")
                            
                            # Select Page Size = 100
                            try:
                                await search_page.select_option("select[name='ddl_pageSize']", "100")
                                logger.info("Selected page size 100")
                            except:
                                logger.warning("Could not select page size")

                            # Click Search
                            # The button is input[value="検索"]
                            await search_page.click("input[value='検索']")
                            logger.info("Clicked Search button")
                            
                            await page2.wait_for_timeout(5000)
                            
                            # Parse Results
                            rows = await search_page.locator("table[border='1'] tr").all()
                            logger.info(f"Found {len(rows)} rows in result table")
                            
                            for row in rows:
                                cols = await row.locator("td").all()
                                # We expect about 10-11 columns.
                                # The header rows have th, data rows have th (No.) and td.
                                # Let's check if it's a data row.
                                # Data row: th(No), td(Btn), td(Btn), td(ID), td(Dept), td(Method), td(Cat), td(Date), td(Title), td(Loc), td(Dead)
                                # Total 1 th + 10 td = 11 elements.
                                
                                if len(cols) < 8:
                                    continue
                                    
                                try:
                                    # Extract text from columns
                                    # Indices in 'cols' (which only contains tds):
                                    # 0: Detail Button
                                    # 1: Attachment Button
                                    # 2: Procurement Number
                                    # 3: Department
                                    # 4: Method
                                    # 5: Category
                                    # 6: Opening Date
                                    # 7: Title
                                    # 8: Location
                                    # 9: Deadline
                                    
                                    title = await cols[7].text_content()
                                    title = title.strip() if title else ""
                                    
                                    # Filter by keyword
                                    if keyword and keyword not in title:
                                        continue
                                        
                                    # Extract other columns
                                    dept = await cols[3].text_content()
                                    method = await cols[4].text_content()
                                    category_text = await cols[5].text_content()
                                    opening_date = await cols[6].text_content()
                                    deadline = await cols[9].text_content()

                                    # Clean up text
                                    dept = dept.strip() if dept else ""
                                    method = method.strip() if method else ""
                                    category_text = category_text.strip() if category_text else ""
                                    opening_date = opening_date.strip() if opening_date else ""
                                    deadline = deadline.strip() if deadline else ""
                                    
                                    # Create BidItem
                                    item = BidItem(
                                        title=title,
                                        organization=dept,
                                        deadline=normalize_date(deadline),
                                        category=category_text,
                                        url="http://nyusatsu.e-kanagawa.lg.jp/",
                                        source="Kanagawa"
                                    )
                                    results.append(item)
                                    logger.info(f"Found match: {title}")
                                    
                                except Exception as e:
                                    logger.error(f"Error parsing row: {e}")
                                    continue
                                    
                        else:
                            logger.error("Could not find search form frame")
                    else:
                        logger.error("Could not find '入札公告' link for Goods in any frame")
                        
                else:
                    logger.error("Could not find menu frame with '神奈川県'")
                
            except Exception as e:
                logger.error(f"Error scraping Kanagawa: {e}")
                # Save screenshot on error
                try:
                    await page.screenshot(path="kanagawa_error.png")
                except:
                    pass
            finally:
                await browser.close()
                
        return results

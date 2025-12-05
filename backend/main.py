from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import llm_service
from scrapers.tokyo import TokyoMetroScraper
from scrapers.gov import GovernmentPortalScraper
from scrapers.kanagawa import KanagawaScraper
import sys
import asyncio
import logging
import uuid

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    logger.info("Set WindowsProactorEventLoopPolicy")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SearchResult(BaseModel):
    id: str
    title: str
    organization: str
    deadline: Optional[str]
    category: str
    url: str
    source: str


from fastapi.responses import StreamingResponse
import json

@app.get("/api/v1/bids")
async def search_bids(q: Optional[str] = None, category: Optional[str] = "all", free_text: Optional[str] = None, sources: Optional[str] = "gov,tokyo,kanagawa"):
    async def event_generator():
        results = []
        
        # Initialize scrapers
        tokyo_scraper = TokyoMetroScraper()
        gov_scraper = GovernmentPortalScraper()
        kanagawa_scraper = KanagawaScraper()
        
        target_sources = sources.split(",") if sources else ["gov", "tokyo", "kanagawa"]

        search_queries = []
        
        if free_text:
            logger.info(f"Analyzing free text: {free_text}")
            yield json.dumps({"type": "log", "message": f"「{free_text}」というご要望を分析しています..."}) + "\n"
            try:
                search_queries = await llm_service.analyze_requirements(free_text)
                keywords_str = ", ".join([f"「{k}」" for k, c in search_queries])
                logger.info(f"Generated queries: {search_queries}")
                yield json.dumps({"type": "log", "message": f"AIが以下の検索キーワードを生成しました: {keywords_str}"}) + "\n"
            except Exception as e:
                logger.error(f"LLM analysis failed: {e}")
                yield json.dumps({"type": "log", "message": "AIによる分析に失敗しました。入力された言葉でそのまま検索します。"}) + "\n"
                # Fallback to simple keyword search
                search_queries = [(free_text[:20], category)]
        else:
            search_queries = [(q or "", category)]
            yield json.dumps({"type": "log", "message": f"キーワード「{q}」で検索を開始します。"}) + "\n"

        all_results = []
        
        # Function to execute search for a list of queries
        async def execute_search(queries):
            tasks = []
            for kw, cat in queries:
                # Tokyo Metro Search
                if "tokyo" in target_sources:
                    tokyo_searches = []
                    if cat == "all":
                        tokyo_searches = ["construction", "goods"]
                    elif cat == "construction":
                        tokyo_searches = ["construction"]
                    elif cat in ["goods", "services"]:
                        tokyo_searches = ["goods"]
                    
                    for tc in tokyo_searches:
                        tasks.append(tokyo_scraper.search(kw, tc))
                
                # Government Portal Search
                if "gov" in target_sources:
                    tasks.append(gov_scraper.search(kw, cat))
                
                # Kanagawa Search
                # Currently supports "goods" (which covers services too in Kanagawa)
                if "kanagawa" in target_sources:
                    if cat in ["all", "goods", "services"]:
                        tasks.append(kanagawa_scraper.search(kw, "goods"))
            
            if not tasks:
                return []
            
            return await asyncio.gather(*tasks, return_exceptions=True)

        scraper_results = []
        # We need to await the execute_search inside the generator, but execute_search is also async.
        # However, execute_search returns a coroutine that returns results.
        # We can't yield from inside execute_search easily if it's just gathering tasks.
        # Let's just call it.
        
        # To provide more granular updates, we could wrap the tasks, but for now let's just log before execution.
        yield json.dumps({"type": "log", "message": "各サイトの検索を開始します..."}) + "\n"
        
        # Re-implement execute_search logic inline to yield logs if needed, or just keep it simple.
        # Keeping it simple for now to minimize risk.
        scraper_results = await execute_search(search_queries)
        
        # Process results
        for res in scraper_results:
            if isinstance(res, list):
                for item in res:
                    all_results.append(SearchResult(
                        id=str(uuid.uuid4()),
                        title=item.title,
                        organization=item.organization,
                        deadline=item.deadline,
                        category=item.category,
                        url=item.url,
                        source=item.source
                    ).dict())
            else:
                logger.error(f"Error in scraper: {res!r}")
        
        yield json.dumps({"type": "log", "message": f"最初の検索で {len(all_results)} 件の案件が見つかりました。"}) + "\n"

        # Refine search if results are few and using free text
        if free_text and len(all_results) < 5:
            logger.info("Few results found. Refining search...")
            yield json.dumps({"type": "log", "message": "検索結果が少ないため、AIがより広いキーワードで再検索を試みます..."}) + "\n"
            previous_keywords = [q[0] for q in search_queries]
            new_queries = await llm_service.refine_search(free_text, previous_keywords)
            
            if new_queries:
                keywords_str = ", ".join([f"「{k}」" for k, c in new_queries])
                logger.info(f"Refined queries: {new_queries}")
                yield json.dumps({"type": "log", "message": f"追加のキーワードを生成しました: {keywords_str}"}) + "\n"
                
                refined_results = await execute_search(new_queries)
                added_count = 0
                for res in refined_results:
                    if isinstance(res, list):
                        for item in res:
                            # Avoid duplicates based on URL
                            if not any(r['url'] == item.url for r in all_results):
                                all_results.append(SearchResult(
                                    id=str(uuid.uuid4()),
                                    title=item.title,
                                    organization=item.organization,
                                    deadline=item.deadline,
                                    category=item.category,
                                    url=item.url,
                                    source=item.source
                                ).dict())
                                added_count += 1
                yield json.dumps({"type": "log", "message": f"再検索の結果、新たに {added_count} 件の案件を追加しました。"}) + "\n"
            else:
                yield json.dumps({"type": "log", "message": "追加の有効なキーワードが見つかりませんでした。"}) + "\n"

        yield json.dumps({"type": "log", "message": f"最終的に {len(all_results)} 件の案件を表示します。"}) + "\n"
        yield json.dumps({"type": "result", "data": all_results}) + "\n"

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")

if __name__ == "__main__":
    import uvicorn
    # Disable reload for Windows asyncio compatibility
    uvicorn.run(app, host="0.0.0.0", port=8004)

import os
import json
import google.generativeai as genai
import logging
from typing import List, Tuple
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv(override=True)

# Configure Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
else:
    logger.warning("GEMINI_API_KEY not found in environment variables.")

def _get_model():
    return genai.GenerativeModel('gemini-2.5-flash')

async def analyze_requirements(text: str) -> List[Tuple[str, str]]:
    """
    Analyzes the user's free text and returns a list of (keyword, category) tuples.
    Categories: 'construction', 'goods', 'services'.
    """
    if not GEMINI_API_KEY:
        logger.error("Gemini API key missing")
        return [("Error: API Key Missing", "all")]

    model = _get_model()
    
    prompt = f"""
    You are a procurement expert. Your task is to translate the user's request into effective search keywords for government tenders (入札案件).
    
    User Input: "{text}"
    
    CRITICAL STRATEGY:
    1. TRANSLATE TO "BUREAUCRATIC LANGUAGE" (お役所言葉): Government tenders use formal, specific terminology. You must translate everyday words into these formal terms.
    2. EXPAND TO BROADER CATEGORIES: Tenders are often grouped by broader categories.
    3. THINK DIVERSELY: The user might be a taxi driver, a fishmonger, a construction worker, or an IT engineer. Apply the same translation logic to any domain.
    
    EXAMPLES OF TRANSLATION LOGIC:
    - "Taxi" (タクシー) -> "旅客運送" (Passenger Transport), "車両借上" (Vehicle Charter), "送迎" (Pick-up/Drop-off)
    - "Fishmonger" (魚屋) -> "水産物" (Marine Products), "食材納入" (Food Supply), "給食" (School Lunch Supply)
    - "Beach House" (海の家) -> "海水浴場" (Beach), "売店設置" (Shop Installation), "占用許可" (Occupancy Permit), "運営委託" (Operation Outsourcing)
    - "Lifesaver" (ライフセーバー) -> "監視業務" (Monitoring Service), "警備" (Security), "安全管理" (Safety Management)
    
    OUTPUT RULES:
    - Generate 3-5 keywords.
    - Mix specific formal terms and broader category terms.
    - Classify each into 'construction', 'goods', or 'services'.
    
    Return ONLY a JSON array:
    [
        {{"keyword": "旅客運送", "category": "services"}},
        {{"keyword": "車両借上", "category": "services"}}
    ]
    """
    
    try:
        response = await model.generate_content_async(prompt)
        content = response.text
        
        # Clean up code blocks if present
        if content.startswith("```json"):
            content = content[7:]
        if content.endswith("```"):
            content = content[:-3]
        
        data = json.loads(content.strip())
        results = []
        for item in data:
            results.append((item.get("keyword"), item.get("category", "all")))
        
        return results
    except Exception as e:
        logger.error(f"Error in analyze_requirements: {e}")
        # Fallback: just use the text as a keyword if it's short, or generic if long
        return [(text[:20], "all")]

async def refine_search(text: str, previous_keywords: List[str]) -> List[Tuple[str, str]]:
    """
    Suggests broader or alternative keywords if initial search yielded few results.
    """
    if not GEMINI_API_KEY:
        return []

    model = _get_model()
    
    prompt = f"""
    The user is looking for procurement opportunities based on: "{text}".
    
    We previously searched for: {previous_keywords}.
    These searches yielded few or no results.
    
    Suggest 3 BROADER or ALTERNATIVE search queries (keyword, category) that might yield more results.
    Think about synonyms, related fields, or more general terms.
    
    Return the result ONLY as a JSON array of objects with 'keyword' and 'category' fields.
    """
    
    try:
        response = await model.generate_content_async(prompt)
        content = response.text
        if content.startswith("```json"):
            content = content[7:]
        if content.endswith("```"):
            content = content[:-3]
            
        data = json.loads(content.strip())
        results = []
        for item in data:
            results.append((item.get("keyword"), item.get("category", "all")))
        
        return results
    except Exception as e:
        logger.error(f"Error in refine_search: {e}")
        return []

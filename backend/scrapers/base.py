from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import datetime
from dataclasses import dataclass

@dataclass
class BidItem:
    title: str
    organization: str
    deadline: Optional[str]
    category: str
    url: str
    source: str

class BaseScraper(ABC):
    def __init__(self):
        pass

    @abstractmethod
    async def search(self, keyword: str, category: str) -> List[BidItem]:
        """Search bids with keyword and category."""
        pass

def normalize_date(date_str: str) -> Optional[str]:
    """
    Normalizes date string to YYYY-MM-DD.
    Handles:
    - YYYY/MM/DD, YYYY-MM-DD
    - R6.11.27 (Reiwa)
    - H30.11.27 (Heisei)
    - S60.11.27 (Showa)
    - 令和6年11月27日
    """
    if not date_str:
        return None
    
    date_str = date_str.strip()
    
    # Handle ranges: pick the last date (Deadline)
    # Common separators: ～, ~, - (careful with YYYY-MM-DD)
    # We split by '～' or '~' first.
    if '～' in date_str:
        date_str = date_str.split('～')[-1].strip()
    elif '~' in date_str:
        date_str = date_str.split('~')[-1].strip()
    elif ' - ' in date_str: # Space hyphen space to avoid YYYY-MM-DD conflict
        date_str = date_str.split(' - ')[-1].strip()
    elif 'から' in date_str:
        date_str = date_str.split('から')[-1].strip()
    
    try:
        import re
        from datetime import datetime
        
        # Handle "令和XX年XX月XX日"
        match = re.match(r'.*令和(\d+)年(\d+)月(\d+)日', date_str)
        if match:
            year = int(match.group(1)) + 2018
            return f"{year}-{match.group(2).zfill(2)}-{match.group(3).zfill(2)}"
            
        # Handle "R6.11.27" or "R06.11.27"
        match = re.match(r'.*R(\d+)\.(\d+)\.(\d+)', date_str)
        if match:
            year = int(match.group(1)) + 2018
            return f"{year}-{match.group(2).zfill(2)}-{match.group(3).zfill(2)}"

        # Handle "H30.11.27"
        match = re.match(r'.*H(\d+)\.(\d+)\.(\d+)', date_str)
        if match:
            year = int(match.group(1)) + 1988
            return f"{year}-{match.group(2).zfill(2)}-{match.group(3).zfill(2)}"

        # Handle "S60.11.27"
        match = re.match(r'.*S(\d+)\.(\d+)\.(\d+)', date_str)
        if match:
            year = int(match.group(1)) + 1925
            return f"{year}-{match.group(2).zfill(2)}-{match.group(3).zfill(2)}"
            
        # Handle "MM月DD日" (Assume current year)
        match = re.match(r'.*?(\d+)月(\d+)日', date_str)
        if match:
            year = datetime.now().year
            # If month is drastically different? For now assume current year.
            # E.g. if today is Jan 2025 and date is Dec 25, it might be 2024.
            # But usually bids are recent.
            # Let's just use current year.
            return f"{year}-{match.group(1).zfill(2)}-{match.group(2).zfill(2)}"

        # Handle "YYYY/MM/DD" or "YYYY.MM.DD"
        clean_str = date_str.replace('/', '-').replace('.', '-')
        
        # Basic YYYY-MM-DD check
        match = re.search(r'(\d{4})-(\d{1,2})-(\d{1,2})', clean_str)
        if match:
            return f"{match.group(1)}-{match.group(2).zfill(2)}-{match.group(3).zfill(2)}"
            
        return date_str
    except Exception:
        return date_str

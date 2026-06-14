import urllib.request
import urllib.parse
import re

# 🟢 FIX #2: Safe type conversion helper
def safe_int_convert(val, default=50):
    """Safely convert any value to int, handling floats and invalid strings."""
    try:
        return int(float(str(val)))
    except (ValueError, TypeError):
        return default

def calculate_next_version(current_version, categories_in_release):
    """Calculates the next semantic version based on the release types."""
    try:
        major, minor, patch = map(int, current_version.replace('v', '').strip().split('.'))
        if "Core" in categories_in_release:
            major += 1
            minor = 0
            patch = 0
        elif "UI" in categories_in_release:
            minor += 1
            patch = 0
        elif "Bug" in categories_in_release:
            patch += 1
        return f"{major}.{minor}.{patch}"
    except Exception:
        return current_version 

def get_youtube_embed_url(exercise_name):
    """
    Silently searches YouTube using pure Python built-ins! 
    Zero external packages or API keys required.
    """
    try:
        # 1. Format the search phrase safely for a web URL
        query = urllib.parse.quote_plus(f"how to do {exercise_name} perfect form tutorial")
        url = f"https://www.youtube.com/results?search_query={query}"
        
        # 2. Pretend to be a real web browser to bypass YouTube's basic bot blockers
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        html = urllib.request.urlopen(req)
        response_text = html.read().decode()
        
        # 3. Use Regex to hunt down the first 11-character YouTube Video ID in the code
        video_ids = re.findall(r"watch\?v=([a-zA-Z0-9_-]{11})", response_text)
        
        if video_ids:
            # 4. Hand the perfect URL back to Streamlit
            return f"https://www.youtube.com/watch?v={video_ids[0]}"
            
    except Exception as e:
        print(f"Native YouTube Scrape Error: {e}")
        
    return None
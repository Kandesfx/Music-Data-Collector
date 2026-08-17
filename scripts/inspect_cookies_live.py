import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.storage.db_manager import DBManager
from src.utils.cookie_checker import CookieHealthChecker

db = DBManager()
cookies = db.get_all_cookies()
print(f"Number of cookies in MongoDB: {len(cookies)}")
for c in cookies:
    content = c.get("content", "")
    diag = CookieHealthChecker.check_health(raw_text=content, probe_network=False)
    print(f"- ID: {c.get('id')}, Name: '{c.get('name')}', Active: {c.get('is_active')}, Size: {len(content)}, Valid: {diag.get('valid')}, Critical: {diag.get('critical_keys_found')}")

# Also check local file config/cookies.txt
p = BASE_DIR / "config" / "cookies.txt"
if p.exists():
    with open(p, "r", encoding="utf-8") as f:
        file_content = f.read()
    diag_file = CookieHealthChecker.check_health(raw_text=file_content, probe_network=False)
    print(f"\nLocal file 'config/cookies.txt': Size: {len(file_content)}, Valid: {diag_file.get('valid')}, Critical: {diag_file.get('critical_keys_found')}")

import sys
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.storage.db_manager import DBManager
db = DBManager()
cookies = db.get_all_cookies()
print(f"Total cookies in DB: {len(cookies)}")
for c in cookies:
    print(f" - [{c.get('service')}] Name: '{c.get('filename')}', Active: {c.get('is_active')}, Size: {c.get('size_bytes')} bytes, Uploaded: {c.get('uploaded_at')}")

# Check disk cookies
p = Path("/opt/music-data-collector/config/cookies.txt")
print(f"\nDisk cookie file: {p} (exists={p.exists()}, size={p.stat().st_size if p.exists() else 0} bytes)")
if p.exists():
    with open(p, "r", encoding="utf-8", errors="ignore") as f:
        lines = [line.strip() for line in f if line.strip() and not line.startswith("#")]
        print(f"Number of cookie lines in file: {len(lines)}")
        print("Sample cookies:", [l.split("\t")[5] for l in lines if len(l.split("\t")) >= 6][:10])

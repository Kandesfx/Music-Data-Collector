import json
from src.utils.cookie_checker import CookieHealthChecker

res = CookieHealthChecker.check_health(probe_network=True)
print(json.dumps(res, indent=2, ensure_ascii=False))

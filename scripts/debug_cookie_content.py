from pathlib import Path

cookie_path = Path("config/cookies.txt")
if not cookie_path.exists():
    print("cookies.txt does not exist!")
    exit()

print(f"{'DOMAIN':<25} {'KEY':<25} {'SECURE':<10} {'EXPIRY':<15} {'LEN'}")
print("-" * 80)
with open(cookie_path, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#"):
            parts = line.split("\t")
            if len(parts) >= 7:
                domain, flag, path, secure, expiry, name, val = parts[0], parts[1], parts[2], parts[3], parts[4], parts[5], parts[6]
                print(f"{domain:<25} {name:<25} {secure:<10} {expiry:<15} {len(val)}")

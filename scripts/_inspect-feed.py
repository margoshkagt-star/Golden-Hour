import json
from pathlib import Path
p = Path("skills/clawsec-suite/advisories/feed.json")
d = json.loads(p.read_text(encoding="utf-8"))
print("version:", d.get("version"))
print("updated:", d.get("updated"))
advs = d.get("advisories", [])
print("count:", len(advs))
# list any advisory whose id starts with letter A-G (malicious_skill-ish)
for a in advs[:20]:
    print("-", a.get("id"), "|", a.get("severity"), "|", a.get("type"), "|", a.get("title"))
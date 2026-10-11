"""Re-check that every resource link in the debrief library still loads. Links go stale, so run this before a demo.
Run:  backend\\.venv\\Scripts\\python spikes\\check_resource_links.py
Reports the HTTP status and final URL for each entry. A 403 from a site that blocks scripts does not mean the link is
dead, so those are listed separately for a person to open in a browser. This checks that a page loads, not that its
content still matches the entry's description."""
import json
import sys
from pathlib import Path

import httpx

LIBRARY = Path(__file__).resolve().parent.parent / "backend" / "app" / "modules" / "prepcrew" / "data" / "resources.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; PrepCrewLinkCheck/1.0)"}


def main() -> int:
    items = json.loads(LIBRARY.read_text(encoding="utf-8"))
    ok, blocked, dead = [], [], []
    with httpx.Client(follow_redirects=True, timeout=30, headers=HEADERS) as client:
        for item in items:
            try:
                r = client.get(item["url"])
                code, final = r.status_code, str(r.url)
            except Exception as e:
                code, final = type(e).__name__, ""
            row = (item["id"], code, final if final != item["url"] else "")
            (ok if code == 200 else blocked if code in (401, 403, 429) else dead).append(row)
            print(f"{code!s:>14}  {item['id']:22} {item['url']}" + (f"  -> {final}" if final and final != item['url'] else ""))
    print(f"\n{len(ok)} load, {len(blocked)} refuse scripts (open in a browser), {len(dead)} broken, of {len(items)}")
    return 1 if dead else 0


if __name__ == "__main__":
    sys.exit(main())

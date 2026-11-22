"""Conservative public-employer-feed job finder. Python stdlib only; no API keys."""
import datetime
import html
import json
import pathlib
import re
import urllib.error
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
BOARDS = json.loads((ROOT / "data/employer-boards.json").read_text())["greenhouse"]
OUT = ROOT / "data/fresh-jobs.json"
BLOCKED = (ROOT / "JOB_SEARCH_DO_NOT_REPEAT.md").read_text().casefold()
REMOTE = re.compile(r"\b(remote|work from home|work-from-home|telecommut)\b", re.I)
PART = re.compile(r"\b(part[ -]?time|15[ -]?20 hours|10[ -]?20 hours|20 hours per week)\b", re.I)
TEXAS = re.compile(r"\b(texas|\btx\b|united states|\busa\b|anywhere in the us)\b", re.I)
ROLE = re.compile(r"survey|interview|research|customer satisfaction|appointment|scheduling|customer support|customer service", re.I)
EXCLUDE = re.compile(r"commission.only|cold.call|sales quota|high.volume|fast.paced|full.time|on.site|on-site|hybrid|travel required|bilingual required|spanish required", re.I)

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "CareerFinder/1.0 (public hiring feeds)"})
    with urllib.request.urlopen(req, timeout=15) as response:
        return json.load(response)

def clean(text):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]*>", " ", text or ""))).strip()

results = []
for board in BOARDS:
    token = board["token"]
    try:
        payload = fetch("https://boards-api.greenhouse.io/v1/boards/" + urllib.parse.quote(token) + "/jobs?content=true")
    except (urllib.error.URLError, ValueError, TimeoutError) as exc:
        print(f"Skipped unavailable board {token}: {type(exc).__name__}")
        continue
    for job in payload.get("jobs", []):
        title = job.get("title", "")
        location = (job.get("location") or {}).get("name", "")
        desc = clean(job.get("content", ""))
        excerpt = (title + " " + location + " " + desc)[:12000]
        employer = board["name"]
        # Conservative: require explicit remote + part-time + US/Texas eligibility.
        # Location alone can be misleading, so Texas-specific exclusions still disqualify.
        if not (ROLE.search(title) and REMOTE.search(excerpt) and PART.search(excerpt) and TEXAS.search(excerpt)):
            continue
        if EXCLUDE.search(excerpt):
            continue
        if re.search(r"\b(except|excluding|not available in|must reside outside)\b.{0,45}\b(texas|\btx\b)", excerpt, re.I):
            continue
        # Do not recycle companies named in the permanent do-not-repeat file.
        if re.search(r"(?<!\w)" + re.escape(employer.casefold()) + r"(?!\w)", BLOCKED):
            continue
        url = job.get("absolute_url", "")
        if not url.startswith("https://"):
            continue
        results.append({"company": employer, "title": title, "location": location,
                        "url": url, "hours": "Part-time mentioned; confirm actual schedule",
                        "pay": "Confirm with employer", "call_volume": "Unknown",
                        "verification": "Automated keyword match only; confirm employer details"})
results = list({item["url"]: item for item in results}.values())[:20]
# Preserve a stable file and avoid commits when no new result appears.
existing = json.loads(OUT.read_text())
if existing.get("jobs") != results:
    OUT.write_text(json.dumps({"updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "source": "Public employer Greenhouse boards; not independently verified",
        "jobs": results}, indent=2) + "\n")
print(f"Candidate jobs: {len(results)}")

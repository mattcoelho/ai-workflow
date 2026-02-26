# Hybrid title filtering — status report

## 1. Per-scraper: lines removed or changed

### job-monitor/scrapers/greenhouse.py
- **Removed:** Comment "Filter for Product Manager positions (case-insensitive)" (previously line 28).
- **Removed:** Conditional `if re.search(r'product manager|platform manager|...', title.lower()):` (previously line 30).
- **Changed:** Unindented the `jobs.append({...})` block so it runs for every job in the API response. All jobs are now returned; no title filter.

### job-monitor/scrapers/ashby.py
- **Removed:** Comment "Filter for Product Manager positions (case-insensitive)" (previously line 66).
- **Removed:** Conditional `if re.search(r'product manager|platform manager|...', link_text.lower()):` (previously line 68).
- **Changed:** Unindented the inner block (job_id extraction, job_url, title, location, append) so any link with `/jobs/` in `href` is added. `import re` and `re.search` for location and job ID extraction are unchanged.

### job-monitor/scrapers/static.py
- **scrape_static:** Replaced the two-line condition  
  `if not re.search(r'product manager|...', title.lower()) or len(title) < 5: continue`  
  with `if len(title) < 5: continue` (kept minimal length guard only).
- **scrape_parallel:** Removed the `title_re = re.compile(...)` block (4 lines). Removed `if not title_re.search(title): continue` (2 lines). Loop now appends every job from the API regardless of title. `import re` remains (used in `_slugify`, `_extract_location_from_text`, and debug `re.compile` in scrape_static).

### job-monitor/scrapers/playwright_scraper.py
- **Replaced:** The entire block that built `text_nodes` (PM-regex), `aria_anchors` (PM-regex), and `candidate_anchors` from those (lines 91–139) with logic that collects all `<a href=True>` links: iterate `soup.find_all('a', href=True)`, dedupe by href, skip empty/`#` hrefs, and build `candidate_anchors` as `('link', anchor)`. Debug print updated to "links found". The existing `for source, anchor in candidate_anchors` loop and URL/title/location handling are unchanged; for `'link'` source the else branch uses `anchor.get_text(strip=True)` for title. No per-job title regex.

### job-monitor/scrapers/facetwp_scraper.py
- **Removed:** The two-line title regex check:  
  `if not re.search(r'product manager|platform manager|...', title.lower()): continue`  
  (previously lines 26–27). Kept `if not title or len(title) < 5: continue`. `import re` remains (used in `_generate_id`).

---

## 2. main.py: hybrid block confirmation

The hybrid block in `main.py` matches the spec exactly:

- **Added:** `import re` at top with other imports.
- **Added:** `TITLE_FILTER = r'product manager|platform manager|product lead|group product|staff product|head of product|director of product'` (replaced the previous comment-only line).
- **Replaced** the single line  
  `new_jobs = [j for j in new_jobs if is_pm_role(j.get("title", ""))]`  
  with:
  - `filtered_jobs = []`
  - `for job in new_jobs:` with `title = job.get("title", "")`
  - `if re.search(TITLE_FILTER, title, re.IGNORECASE): filtered_jobs.append(job)` (fast path, no API call)
  - `elif is_pm_role(title): filtered_jobs.append(job)` (AI path)
  - `new_jobs = filtered_jobs`

Order is correct: regex first, then AI fallback; no other logic in the block.

---

## 3. No other logic changed

- **main.py:** Only the listed edits were made (import `re`, `TITLE_FILTER` constant, hybrid filter block). `get_new_jobs`, the analysis loop, scoring, email, and saving seen jobs are unchanged.
- **Scrapers:** Only the title-filter removals/changes above were made. No other behavior, imports (except removal of unused regex constant where applicable), or helpers were changed.

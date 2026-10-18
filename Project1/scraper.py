"""Scraper: Open Library search API (public, paginated JSON). Pause/resume/stop supported."""
import csv, os, threading, time
from urllib.parse import urlparse, parse_qs
import requests
from PyQt6.QtCore import QThread, pyqtSignal

API = "https://openlibrary.org/search.json"
FIELDS = ("key,title,author_name,first_publish_year,edition_count,number_of_pages_median,"
          "ratings_average,ratings_count,want_to_read_count,subject,publisher")
COLUMNS = ["Title", "Author", "First Published", "Editions", "Pages", "Rating",
           "Ratings Count", "Want To Read", "Subject", "Publisher"]
TYPES = ["str", "str", "num", "num", "num", "num", "num", "num", "str", "str"]
CSV_FILE = "books.csv"
DEFAULT_QUERIES = [f"subject:{s}" for s in (
    "fiction science history romance fantasy biography mystery children poetry philosophy art religion "
    "cooking travel music mathematics medicine business psychology politics war education nature computers "
    "humor drama law sports economics technology").split()]

def to_row(d):
    first = lambda x, n: ", ".join(x[:n]) if x else ""
    ra = d.get("ratings_average")
    return [d.get("title", ""), first(d.get("author_name"), 2), d.get("first_publish_year"),
            d.get("edition_count"), d.get("number_of_pages_median"),
            round(ra, 2) if ra is not None else None, d.get("ratings_count"),
            d.get("want_to_read_count"), first(d.get("subject"), 3), first(d.get("publisher"), 1)]

def url_to_query(text):
    """Bonus: accept a URL (search?q=..., /subjects/x) or plain keyword."""
    text = text.strip()
    if not text.lower().startswith("http"): return text
    u = urlparse(text); q = parse_qs(u.query).get("q")
    if q: return q[0]
    parts = [p for p in u.path.split("/") if p]
    if len(parts) >= 2 and parts[0] == "subjects": return f"subject:{parts[1]}"
    return parts[-1] if parts else ""

def save_csv(rows, path=CSV_FILE):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(COLUMNS); w.writerows(rows)

def load_csv(path=CSV_FILE):
    if not os.path.exists(path): return []
    rows = []
    with open(path, encoding="utf-8") as f:
        r = csv.reader(f); next(r, None)
        for line in r:
            row = []
            for v, t in zip(line, TYPES):
                if t == "num": row.append(float(v) if v not in ("", "None") and "." in v else (int(v) if v not in ("", "None") else None))
                else: row.append(v)
            rows.append(row)
    return rows

class ScrapeWorker(QThread):
    progress = pyqtSignal(int, int)
    status = pyqtSignal(str)
    done = pyqtSignal(list)

    def __init__(self, target, queries):
        super().__init__()
        self.target, self.queries = target, queries
        self._go = threading.Event(); self._go.set(); self._stop = False

    def pause(self): self._go.clear()
    def resume(self): self._go.set()
    def stop(self): self._stop = True; self._go.set()

    def run(self):
        s = requests.Session(); s.headers["User-Agent"] = "CS200-Project1/1.0 (student project)"
        seen, rows = set(), []
        max_pages = 200 if len(self.queries) == 1 else 15
        for q in self.queries:
            for page in range(1, max_pages + 1):
                self._go.wait()
                if self._stop or len(rows) >= self.target: break
                docs = None
                for attempt in range(3):
                    try:
                        r = s.get(API, params={"q": q, "fields": FIELDS, "limit": 100, "page": page}, timeout=30)
                        r.raise_for_status(); docs = r.json().get("docs", []); break
                    except Exception as e:
                        self.status.emit(f"Network error ({e}); retry {attempt + 1}/3"); time.sleep(2)
                if not docs: break
                for d in docs:
                    k = d.get("key")
                    if k in seen or not d.get("title"): continue
                    seen.add(k); rows.append(to_row(d))
                self.progress.emit(min(len(rows), self.target), self.target)
                self.status.emit(f"Query '{q}' page {page}")
                time.sleep(0.25)   # be polite to the API
            if self._stop or len(rows) >= self.target: break
        self.done.emit(rows[: self.target])

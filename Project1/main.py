import sys
from PyQt6.QtCore import Qt, QAbstractTableModel, QModelIndex, QThread, pyqtSignal
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QTabWidget, QTableView, QSplitter, QLabel, QPushButton, QComboBox, QLineEdit, QSpinBox, QProgressBar,
    QDialog, QTableWidget, QTableWidgetItem, QMessageBox, QHeaderView)
import time
from algorithms import (ALGOS, run_sort, build_items, search, STR_OPS, NUM_OPS, SEARCH_ALGOS)
from scraper import (COLUMNS, TYPES, DEFAULT_QUERIES, ScrapeWorker, url_to_query, save_csv, load_csv)

QUAD_CAP = 3000   # benchmark: O(n²) algorithms run on a sample this big

class RowsModel(QAbstractTableModel):
    def __init__(self): super().__init__(); self.rows = []; self.view = []
    def rowCount(self, p=QModelIndex()): return len(self.view)
    def columnCount(self, p=QModelIndex()): return len(COLUMNS)
    def data(self, idx, role=Qt.ItemDataRole.DisplayRole):
        if not idx.isValid(): return None
        v = self.rows[self.view[idx.row()]][idx.column()]
        if role == Qt.ItemDataRole.DisplayRole: return "" if v is None else str(v)
        if role == Qt.ItemDataRole.TextAlignmentRole and TYPES[idx.column()] == "num":
            return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
    def headerData(self, s, o, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole:
            return COLUMNS[s] if o == Qt.Orientation.Horizontal else str(s + 1)
    def set_rows(self, rows):
        self.beginResetModel(); self.rows = rows; self.view = list(range(len(rows))); self.endResetModel()
    def set_view(self, view):
        self.beginResetModel(); self.view = view; self.endResetModel()

class Task(QThread):
    ok = pyqtSignal(object); fail = pyqtSignal(str)
    def __init__(self, fn): super().__init__(); self.fn = fn
    def run(self):
        try: self.ok.emit(self.fn())
        except Exception as e: self.fail.emit(str(e))

class FilterRow(QWidget):
    def __init__(self, first):
        super().__init__()
        h = QHBoxLayout(self); h.setContentsMargins(0, 0, 0, 0)
        self.conn = QComboBox(); self.conn.addItems(["", "NOT"] if first else ["AND", "OR", "AND NOT", "OR NOT"])
        self.col = QComboBox(); self.col.addItems(COLUMNS)
        self.op = QComboBox(); self.val = QLineEdit(); self.val.setPlaceholderText("value")
        self.algo = QComboBox(); self.algo.addItems(SEARCH_ALGOS)
        for w in (self.conn, self.col, self.op, self.val, self.algo): h.addWidget(w)
        h.setStretch(3, 1)
        self.col.currentIndexChanged.connect(self.refresh_ops); self.refresh_ops()
    def refresh_ops(self):
        self.op.clear(); self.op.addItems(NUM_OPS if TYPES[self.col.currentIndex()] == "num" else STR_OPS)

class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CS200 Project 1 – Book Explorer"); self.resize(1300, 820)
        self.model = RowsModel(); self.base_order = []; self.active_set = None
        self.worker = None; self.task = None; self.frows = []
        tabs = QTabWidget()
        tabs.addTab(self.scrape_tab(), "1. Scrape"); tabs.addTab(self.sort_tab(), "2. Sort")
        tabs.addTab(self.filter_tab(), "3. Search / Filter")
        self.table = QTableView(); self.table.setModel(self.model)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().sectionClicked.connect(lambda c: self.lv_col[0].setCurrentIndex(c))
        for i, w in enumerate((300, 160, 110, 80, 70, 70, 100, 100, 260, 160)): self.table.setColumnWidth(i, w)
        self.info = QLabel("Ready"); self.info.setWordWrap(True)
        top = QWidget(); tv = QVBoxLayout(top); tv.addWidget(tabs); tv.addWidget(self.info)
        sp = QSplitter(Qt.Orientation.Vertical); sp.addWidget(top); sp.addWidget(self.table); sp.setSizes([300, 520])
        self.setCentralWidget(sp)
        rows = load_csv()
        if rows: self.set_data(rows); self.info.setText(f"Loaded {len(rows)} cached rows from books.csv")

    # ---------- data ----------
    def set_data(self, rows):
        self.model.set_rows(rows); self.base_order = list(range(len(rows))); self.active_set = None

    # ---------- scrape tab ----------
    def scrape_tab(self):
        w = QWidget(); g = QGridLayout(w)
        self.url = QLineEdit(); self.url.setPlaceholderText(
            "Optional (bonus): Open Library URL or keyword, e.g. https://openlibrary.org/search.json?q=love  (empty = 30 default subjects)")
        self.target = QSpinBox(); self.target.setRange(100, 100000); self.target.setValue(15000)
        self.b_start, self.b_pause, self.b_resume, self.b_stop = (QPushButton(t) for t in ("Start", "Pause", "Resume", "Stop"))
        self.bar = QProgressBar(); self.sl = QLabel("Idle")
        g.addWidget(QLabel("URL / keyword:"), 0, 0); g.addWidget(self.url, 0, 1, 1, 5)
        g.addWidget(QLabel("Target entities:"), 1, 0); g.addWidget(self.target, 1, 1)
        for i, b in enumerate((self.b_start, self.b_pause, self.b_resume, self.b_stop)): g.addWidget(b, 1, 2 + i)
        g.addWidget(self.bar, 2, 0, 1, 6); g.addWidget(self.sl, 3, 0, 1, 6)
        self.b_start.clicked.connect(self.start_scrape)
        self.b_pause.clicked.connect(lambda: (self.worker.pause(), self.sl.setText("Paused")))
        self.b_resume.clicked.connect(lambda: (self.worker.resume(), self.sl.setText("Resumed")))
        self.b_stop.clicked.connect(lambda: self.worker.stop())
        self.scrape_buttons(False)
        return w
    def scrape_buttons(self, running):
        self.b_start.setEnabled(not running)
        for b in (self.b_pause, self.b_resume, self.b_stop): b.setEnabled(running)
    def start_scrape(self):
        q = url_to_query(self.url.text())
        self.worker = ScrapeWorker(self.target.value(), [q] if q else DEFAULT_QUERIES)
        self.bar.setMaximum(self.target.value()); self.bar.setValue(0)
        self.worker.progress.connect(lambda n, t: (self.bar.setValue(n), self.bar.setFormat(f"{n} / {t}")))
        self.worker.status.connect(self.sl.setText)
        self.worker.done.connect(self.scrape_done)
        self.scrape_buttons(True); self.worker.start()
    def scrape_done(self, rows):
        self.scrape_buttons(False)
        if rows:
            save_csv(rows); self.set_data(rows)
            self.sl.setText(f"Finished: {len(rows)} entities saved to books.csv")
        else: self.sl.setText("No data scraped (check connection)")

    # ---------- sort tab ----------
    def sort_tab(self):
        w = QWidget(); g = QGridLayout(w)
        self.lv_col, self.lv_ord = [], []
        for i in range(3):
            c = QComboBox(); c.addItems(([] if i == 0 else ["(none)"]) + COLUMNS)
            o = QComboBox(); o.addItems(["Ascending", "Descending"])
            g.addWidget(QLabel(f"Level {i + 1}:"), i, 0); g.addWidget(c, i, 1); g.addWidget(o, i, 2)
            self.lv_col.append(c); self.lv_ord.append(o)
        self.algo = QComboBox()
        for n, (_, cx, st, _) in ALGOS.items(): self.algo.addItem(f"{n} — {cx}, {'stable' if st else 'unstable'}", n)
        self.scope = QComboBox(); self.scope.addItems(["Full dataset", "Filtered results only"])
        self.b_sort = QPushButton("Sort"); self.b_bench = QPushButton("Benchmark")
        g.addWidget(QLabel("Algorithm:"), 0, 3); g.addWidget(self.algo, 0, 4, 1, 2)
        g.addWidget(QLabel("Scope:"), 1, 3); g.addWidget(self.scope, 1, 4, 1, 2)
        g.addWidget(self.b_sort, 2, 4); g.addWidget(self.b_bench, 2, 5)
        g.addWidget(QLabel("Tip: click a column header to set Level 1. * = additional algorithm beyond class."), 3, 0, 1, 6)
        self.b_sort.clicked.connect(self.do_sort); self.b_bench.clicked.connect(self.do_bench)
        return w
    def levels(self):
        lv = [(self.lv_col[0].currentIndex(), self.lv_ord[0].currentIndex() == 1)]
        for i in (1, 2):
            k = self.lv_col[i].currentIndex() - 1
            if k >= 0: lv.append((k, self.lv_ord[i].currentIndex() == 1))
        return lv
    def lock(self, busy, msg=""):
        self.b_sort.setEnabled(not busy); self.b_bench.setEnabled(not busy)
        if msg: self.info.setText(msg)
    def indices(self):
        return list(self.base_order) if self.scope.currentIndex() == 0 else list(self.model.view)
    def do_sort(self):
        if not self.model.rows: return
        lv = self.levels(); name = self.algo.currentData(); scope = self.scope.currentIndex()
        items = build_items(self.model.rows, self.indices(), lv, TYPES)
        self.lock(True, f"Sorting {len(items)} rows with {name}… (O(n²) algorithms on 15k rows can take a while)")
        self.task = Task(lambda: run_sort(items, name))
        self.task.ok.connect(lambda r: self.sort_done(r, name, lv, scope)); self.task.fail.connect(lambda e: self.lock(False, e))
        self.task.start()
    def sort_done(self, res, name, lv, scope):
        a, ms, cm, sw = res; order = [x[1] for x in a]
        if scope == 0:
            self.base_order = order
            view = order if self.active_set is None else [i for i in order if i in self.active_set]
        else: view = order
        self.model.set_view(view)
        _, cx, st, _ = ALGOS[name]
        by = " → ".join(COLUMNS[c] + (" ↓" if d else " ↑") for c, d in lv)
        self.lock(False, f"Sorted by {by} | {name} | Time: {ms:.2f} ms | Comparisons: {cm:,} | "
                         f"Swaps/moves: {sw:,} | {cx} | {'Stable' if st else 'Unstable'}")
    def do_bench(self):
        if not self.model.rows: return
        lv = self.levels(); items = build_items(self.model.rows, self.indices(), lv, TYPES)
        self.lock(True, "Benchmarking all algorithms… (O(n²) ones use a 3000-row sample if data is larger)")
        def job():
            out = []
            for n, (_, cx, st, quad) in ALGOS.items():
                its = items[:QUAD_CAP] if quad and len(items) > QUAD_CAP else items
                _, ms, cm, sw = run_sort(its, n)
                out.append((n, cx, "Yes" if st else "No", f"{len(its):,}", f"{ms:.2f}", f"{cm:,}", f"{sw:,}"))
            return out
        self.task = Task(job); self.task.ok.connect(self.bench_done); self.task.fail.connect(lambda e: self.lock(False, e))
        self.task.start()
    def bench_done(self, out):
        self.lock(False, "Benchmark complete")
        d = QDialog(self); d.setWindowTitle("Benchmark"); d.resize(900, 360); v = QVBoxLayout(d)
        t = QTableWidget(len(out), 7); t.setHorizontalHeaderLabels(
            ["Algorithm", "Complexity", "Stable", "n", "Time (ms)", "Comparisons", "Swaps/moves"])
        for r, row in enumerate(out):
            for c, x in enumerate(row): t.setItem(r, c, QTableWidgetItem(x))
        t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch); v.addWidget(t)
        self.bench_dlg = d; d.show()

    # ---------- filter tab ----------
    def filter_tab(self):
        w = QWidget(); self.fv = QVBoxLayout(w)
        self.rows_box = QVBoxLayout(); self.fv.addLayout(self.rows_box)
        h = QHBoxLayout()
        for text, fn in (("+ Add condition", self.add_cond), ("– Remove last", self.rem_cond),
                         ("Apply filters", self.apply_filters), ("Clear", self.clear_filters)):
            b = QPushButton(text); b.clicked.connect(fn); h.addWidget(b)
        self.fv.addLayout(h); self.add_cond()
        return w
    def add_cond(self):
        r = FilterRow(first=not self.frows); self.frows.append(r); self.rows_box.addWidget(r)
    def rem_cond(self):
        if len(self.frows) > 1: self.frows.pop().setParent(None)
    def apply_filters(self):
        rows = self.model.rows; ALL = set(range(len(rows))); res = None; notes = ""; t0 = time.perf_counter()
        try:
            for k, f in enumerate(self.frows):
                if not f.val.text().strip(): continue
                col = f.col.currentIndex()
                s, note = search(rows, col, TYPES[col] == "num", f.op.currentText(), f.val.text().strip(),
                                 f.algo.currentText(), range(len(rows)))
                notes += note; conn = f.conn.currentText()
                if res is None: res = (ALL - s) if conn == "NOT" else s
                else:
                    t = (ALL - s) if conn.endswith("NOT") else s
                    res = res & t if conn.startswith("AND") else res | t
        except ValueError as e:
            QMessageBox.warning(self, "Invalid filter", str(e)); return
        if res is None: return self.clear_filters()
        self.active_set = res; self.model.set_view([i for i in self.base_order if i in res])
        self.info.setText(f"{len(res):,} of {len(rows):,} rows match | {(time.perf_counter() - t0) * 1000:.2f} ms | {notes}")
    def clear_filters(self):
        self.active_set = None; self.model.set_view(list(self.base_order)); self.info.setText("Filters cleared")

if __name__ == "__main__":
    app = QApplication(sys.argv); w = Window(); w.show(); sys.exit(app.exec())

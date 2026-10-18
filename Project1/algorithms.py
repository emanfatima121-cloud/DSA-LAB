"""Sorting + searching algorithms with comparison/swap counters.
Items are (key, row_index) tuples; only keys are compared."""
import time

class Counter:
    __slots__ = ("cmp", "swap")
    def __init__(self): self.cmp = 0; self.swap = 0

# ---------------- SORTING ----------------
def bubble(a, c):
    n = len(a)
    for i in range(n - 1):
        sw = False
        for j in range(n - 1 - i):
            c.cmp += 1
            if a[j + 1][0] < a[j][0]:
                a[j], a[j + 1] = a[j + 1], a[j]; c.swap += 1; sw = True
        if not sw: break

def selection(a, c):
    n = len(a)
    for i in range(n - 1):
        m = i
        for j in range(i + 1, n):
            c.cmp += 1
            if a[j][0] < a[m][0]: m = j
        if m != i:
            a[i], a[m] = a[m], a[i]; c.swap += 1

def insertion(a, c):               # swap = element shift
    for i in range(1, len(a)):
        x = a[i]; j = i - 1
        while j >= 0:
            c.cmp += 1
            if x[0] < a[j][0]:
                a[j + 1] = a[j]; c.swap += 1; j -= 1
            else: break
        a[j + 1] = x

def merge_sort(a, c):              # bottom-up; swap = element move/write
    n = len(a); src = a; dst = [None] * n; w = 1
    while w < n:
        for lo in range(0, n, 2 * w):
            mid = min(lo + w, n); hi = min(lo + 2 * w, n)
            i, j, k = lo, mid, lo
            while i < mid and j < hi:
                c.cmp += 1
                if src[j][0] < src[i][0]: dst[k] = src[j]; j += 1
                else: dst[k] = src[i]; i += 1
                k += 1; c.swap += 1
            while i < mid: dst[k] = src[i]; i += 1; k += 1; c.swap += 1
            while j < hi: dst[k] = src[j]; j += 1; k += 1; c.swap += 1
        src, dst = dst, src; w *= 2
    if src is not a: a[:] = src

def quick(a, c):                   # iterative, random pivot, 3-way partition
    import random
    stack = [(0, len(a) - 1)]
    while stack:
        lo, hi = stack.pop()
        if lo >= hi: continue
        p = a[random.randint(lo, hi)][0]
        lt, i, gt = lo, lo, hi
        while i <= gt:
            c.cmp += 1
            if a[i][0] < p:
                a[lt], a[i] = a[i], a[lt]; c.swap += 1; lt += 1; i += 1
            else:
                c.cmp += 1
                if p < a[i][0]:
                    a[i], a[gt] = a[gt], a[i]; c.swap += 1; gt -= 1
                else: i += 1
        stack.append((lo, lt - 1)); stack.append((gt + 1, hi))

def heap(a, c):
    n = len(a)
    def sift(i, end):
        while True:
            l = 2 * i + 1
            if l >= end: return
            m = l
            if l + 1 < end:
                c.cmp += 1
                if a[l][0] < a[l + 1][0]: m = l + 1
            c.cmp += 1
            if a[i][0] < a[m][0]:
                a[i], a[m] = a[m], a[i]; c.swap += 1; i = m
            else: return
    for i in range(n // 2 - 1, -1, -1): sift(i, n)
    for end in range(n - 1, 0, -1):
        a[0], a[end] = a[end], a[0]; c.swap += 1; sift(0, end)

def shell(a, c):                   # ADDITIONAL 1 (Knuth gaps)
    n = len(a); gap = 1
    while gap < n // 3: gap = 3 * gap + 1
    while gap >= 1:
        for i in range(gap, n):
            x = a[i]; j = i
            while j >= gap:
                c.cmp += 1
                if x[0] < a[j - gap][0]: a[j] = a[j - gap]; c.swap += 1; j -= gap
                else: break
            a[j] = x
        gap //= 3

def comb(a, c):                    # ADDITIONAL 2
    n = len(a); gap = n; done = False
    while not done:
        gap = max(1, int(gap / 1.3)); done = gap == 1
        for i in range(n - gap):
            c.cmp += 1
            if a[i + gap][0] < a[i][0]:
                a[i], a[i + gap] = a[i + gap], a[i]; c.swap += 1; done = False

# name: (function, complexity, stable, is_quadratic)
ALGOS = {
    "Bubble Sort":    (bubble,     "O(n²)",       True,  True),
    "Selection Sort": (selection,  "O(n²)",       False, True),
    "Insertion Sort": (insertion,  "O(n²)",       True,  True),
    "Merge Sort":     (merge_sort, "O(n log n)",  True,  False),
    "Quick Sort":     (quick,      "O(n log n) avg", False, False),
    "Heap Sort":      (heap,       "O(n log n)",  False, False),
    "Shell Sort*":    (shell,      "~O(n^1.5)",   False, False),
    "Comb Sort*":     (comb,       "O(n²) worst, ~n log n avg", False, False),
}

def run_sort(items, name):
    fn = ALGOS[name][0]; a = list(items); c = Counter()
    t = time.perf_counter(); fn(a, c)
    return a, (time.perf_counter() - t) * 1000, c.cmp, c.swap

class Rev:
    """Wrapper that reverses ordering (for descending columns)."""
    __slots__ = ("v",)
    def __init__(self, v): self.v = v
    def __lt__(self, o): return o.v < self.v
    def __eq__(self, o): return self.v == o.v

def build_items(rows, indices, levels, types):
    """levels = [(col, descending)]; missing values always sort last."""
    items = []
    for i in indices:
        parts = []
        for col, desc in levels:
            v = rows[i][col]
            if types[col] == "num": miss = v is None; val = 0 if miss else v
            else: val = (v or "").lower(); miss = val == ""
            parts.append((1 if miss else 0, Rev(val) if desc else val))
        items.append((tuple(parts) if len(parts) > 1 else parts[0], i))
    return items

# ---------------- SEARCHING ----------------
STR_OPS = ["contains", "starts with", "ends with", "equals"]
NUM_OPS = ["=", "!=", ">", ">=", "<", "<="]
SEARCH_ALGOS = ["Linear Search", "Binary Search", "Jump Search"]

def _pred(is_num, op, t):
    if is_num:
        f = {"=": lambda v: v == t, "!=": lambda v: v != t, ">": lambda v: v > t,
             ">=": lambda v: v >= t, "<": lambda v: v < t, "<=": lambda v: v <= t}[op]
        return lambda v: v is not None and f(v)
    f = {"contains": lambda s: t in s, "starts with": lambda s: s.startswith(t),
         "ends with": lambda s: s.endswith(t), "equals": lambda s: s == t}[op]
    return lambda v: f((v or "").lower())

def _lb(vals, t):
    lo, hi = 0, len(vals)
    while lo < hi:
        m = (lo + hi) // 2
        if vals[m] < t: lo = m + 1
        else: hi = m
    return lo

def _ub(vals, t):
    lo, hi = 0, len(vals)
    while lo < hi:
        m = (lo + hi) // 2
        if t < vals[m]: hi = m
        else: lo = m + 1
    return lo

def _jump_first(vals, t):
    import math
    n = len(vals); step = max(1, int(math.sqrt(n))); prev = 0
    while prev < n and vals[min(prev + step, n) - 1] < t: prev += step
    j = prev
    while j < min(prev + step, n) and vals[j] < t: j += 1
    return j

def search(rows, col, is_num, op, value, algo, indices):
    """Returns (set_of_row_indices, note)."""
    if is_num:
        try: t = float(value)
        except ValueError: raise ValueError(f"'{value}' is not a number")
    else: t = value.lower()
    use = algo
    if algo == "Binary Search" and not ((is_num and op != "!=") or (not is_num and op in ("equals", "starts with"))):
        use = "Linear Search"
    if algo == "Jump Search" and op not in ("=", "equals"): use = "Linear Search"
    note = f"{algo} can't do '{op}', used Linear. " if use != algo else ""
    if use == "Linear Search":
        p = _pred(is_num, op, t)
        return {i for i in indices if p(rows[i][col])}, note
    pairs = []
    for i in indices:
        v = rows[i][col]
        if is_num:
            if v is None: continue
        else: v = (v or "").lower()
        pairs.append((v, i))
    pairs.sort(); vals = [p[0] for p in pairs]; n = len(vals)
    if use == "Jump Search":
        lo = _jump_first(vals, t); hi = lo
        while hi < n and vals[hi] == t: hi += 1
    elif is_num:
        lo, hi = {"=": (_lb(vals, t), _ub(vals, t)), ">": (_ub(vals, t), n), ">=": (_lb(vals, t), n),
                  "<": (0, _lb(vals, t)), "<=": (0, _ub(vals, t))}[op]
    elif op == "equals": lo, hi = _lb(vals, t), _ub(vals, t)
    else: lo, hi = _lb(vals, t), _lb(vals, t + "\uffff")
    return {pairs[k][1] for k in range(lo, hi)}, note

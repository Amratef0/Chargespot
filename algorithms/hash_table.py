"""Custom hash table (Member 1's HashTable, rebuilt).

Original problems (found in the audit): no collision handling (two keys in one bucket silently
overwrote each other), `get` returned 0 for missing keys, it used Python's per-run randomised
`hash()`, and nothing in the project used it.

Now: own deterministic hash function, separate chaining, automatic resize, and statistics
(collisions, load factor, longest chain) for the algorithm evidence. Same method names as before:
HashTable(size), .hash(key), .put(key, value), .get(key).
"""


class HashTable:
    def __init__(self, size=64):
        if not isinstance(size, int) or size < 1:
            raise ValueError("Hash table size must be a positive integer.")
        self.size = size
        self.buckets = [[] for _ in range(size)]
        self.count = 0
        self.collisions = 0           # inserts that landed in a non-empty bucket
        self.last_probes = 0          # key comparisons made by the last get() (for the evidence page)

    def hash(self, key):
        """Polynomial rolling hash over the text of the key (deterministic across runs)."""
        h = 5381
        for ch in str(key):
            h = (h * 33 + ord(ch)) & 0xFFFFFFFF
        return h % self.size

    def put(self, key, value):
        bucket = self.buckets[self.hash(key)]
        for pair in bucket:
            if pair[0] == key:
                pair[1] = value                    # update existing key
                return
        if bucket:
            self.collisions += 1
        bucket.append([key, value])
        self.count += 1
        if self.count / self.size > 0.75:
            self._resize()

    def get(self, key, default=None):
        self.last_probes = 0
        for k, v in self.buckets[self.hash(key)]:
            self.last_probes += 1
            if k == key:
                return v
        return default

    def contains(self, key):
        return any(k == key for k, _ in self.buckets[self.hash(key)])

    def remove(self, key):
        bucket = self.buckets[self.hash(key)]
        for i, (k, v) in enumerate(bucket):
            if k == key:
                bucket.pop(i)
                self.count -= 1
                return v
        return None

    def items(self):
        return [(k, v) for b in self.buckets for k, v in b]

    def keys(self):
        return [k for k, _ in self.items()]

    def __len__(self):
        return self.count

    def __contains__(self, key):
        return self.contains(key)

    def _resize(self):
        old = self.items()
        self.size *= 2
        self.buckets = [[] for _ in range(self.size)]
        self.count = 0
        self.collisions = 0
        for k, v in old:
            self.put(k, v)

    def stats(self):
        longest = max((len(b) for b in self.buckets), default=0)
        return {"entries": self.count, "buckets": self.size, "load_factor": round(self.count / self.size, 3),
                "collisions": self.collisions, "longest_chain": longest,
                "empty_buckets": sum(1 for b in self.buckets if not b)}

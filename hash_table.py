class HashTable:
    def __init__(self, size):
        self.size = size
        self.table = {}
        for i in range(size):
            self.table[i] = 0

    def hash(self, key):
        return hash(key) % self.size

    def get(self, key):
        return self.table[self.hash(key)]

    def put(self, key, value):
        self.table[self.hash(key)] = value



class Queue:
    def __init__(self):
        self._items = []
        self._head = 0

    def __len__(self):
        return len(self._items) - self._head

    def __iter__(self):
        return iter(self._items[self._head:])

    def is_empty(self):
        return len(self) == 0

    def enqueue(self, item):
        self._items.append(item)
        return len(self)                      # position (1-based) of the new item

    def dequeue(self):
        if self.is_empty():
            return None
        item = self._items[self._head]
        self._head += 1
        if self._head > 32 and self._head * 2 > len(self._items):    # compact
            self._items = self._items[self._head:]
            self._head = 0
        return item

    def peek(self):
        return None if self.is_empty() else self._items[self._head]

    def position_of(self, predicate):
        """1-based queue position of the first item matching predicate, or None."""
        for i, item in enumerate(self._items[self._head:], start=1):
            if predicate(item):
                return i
        return None

    def remove_where(self, predicate):
        """Remove and return the first item matching predicate (None if no match)."""
        for i in range(self._head, len(self._items)):
            if predicate(self._items[i]):
                return self._items.pop(i)
        return None

    def to_list(self):
        return list(self)

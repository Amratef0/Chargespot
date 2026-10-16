
def merge_sort(arr, key=lambda x: x, reverse=False):
    comparisons = 0

    def merge(left, right):
        nonlocal comparisons
        result = []
        i = j = 0

        while i < len(left) and j < len(right):
            comparisons += 1
            left_key = key(left[i])
            right_key = key(right[j])

            if reverse:
                take_left = left_key >= right_key
            else:
                take_left = left_key <= right_key

            if take_left:
                result.append(left[i])
                i += 1
            else:
                result.append(right[j])
                j += 1

        result.extend(left[i:])
        result.extend(right[j:])
        return result

    def sort(items):
        if len(items) <= 1:
            return items

        mid = len(items) // 2
        left = sort(items[:mid])
        right = sort(items[mid:])
        return merge(left, right)

    return sort(list(arr)), comparisons


def merge_sort_with_stats(arr, key=lambda x: x, reverse=False):
    """Same algorithm, also counting recursive calls (PDF: track comparisons / swaps / recursive calls)."""
    calls = 0

    def sort(items):
        nonlocal calls
        calls += 1
        if len(items) <= 1:
            return list(items)
        mid = len(items) // 2
        left, right = sort(items[:mid]), sort(items[mid:])
        out, i, j = [], 0, 0
        while i < len(left) and j < len(right):
            lk, rk = key(left[i]), key(right[j])
            take_left = lk >= rk if reverse else lk <= rk
            if take_left:
                out.append(left[i]); i += 1
            else:
                out.append(right[j]); j += 1
        return out + left[i:] + right[j:]

    result, comparisons = merge_sort(arr, key, reverse)
    sort(list(arr))
    return {"sorted": result, "comparisons": comparisons, "recursive_calls": calls, "n": len(result)}

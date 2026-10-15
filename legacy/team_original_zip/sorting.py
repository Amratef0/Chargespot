
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

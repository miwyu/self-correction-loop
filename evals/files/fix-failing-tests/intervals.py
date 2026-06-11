"""Utilities for working with half-open-ish integer intervals [start, end]."""


def merge_intervals(intervals):
    """Merge overlapping or touching (start, end) intervals.

    Touching intervals like (1, 3) and (3, 5) merge into (1, 5).
    Returns a sorted list of tuples.
    """
    if not intervals:
        return []
    intervals = sorted(intervals)
    merged = [list(intervals[0])]
    for start, end in intervals[1:]:
        if start < merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return [tuple(m) for m in merged]


def total_coverage(intervals):
    """Total length covered by the intervals (overlaps counted once)."""
    return sum(end - start for start, end in intervals)


def find_gaps(intervals, lo, hi):
    """Return the uncovered gaps within [lo, hi] as (start, end) tuples."""
    merged = merge_intervals(intervals)
    gaps = []
    cur = lo
    for start, end in merged:
        if end <= lo or start >= hi:
            continue
        if start > cur:
            gaps.append((cur, min(start, hi)))
        cur = max(cur, end)
    return gaps

from intervals import merge_intervals, total_coverage, find_gaps


def test_merge_empty():
    assert merge_intervals([]) == []


def test_merge_disjoint():
    assert merge_intervals([(1, 2), (4, 5)]) == [(1, 2), (4, 5)]


def test_merge_overlapping():
    assert merge_intervals([(1, 4), (2, 6)]) == [(1, 6)]


def test_merge_touching():
    assert merge_intervals([(1, 3), (3, 5)]) == [(1, 5)]


def test_merge_unsorted_input():
    assert merge_intervals([(5, 7), (1, 3), (2, 4)]) == [(1, 4), (5, 7)]


def test_merge_contained():
    assert merge_intervals([(1, 10), (2, 3), (4, 5)]) == [(1, 10)]


def test_coverage_disjoint():
    assert total_coverage([(0, 2), (5, 8)]) == 5


def test_coverage_overlapping_counted_once():
    assert total_coverage([(0, 5), (3, 8)]) == 8


def test_coverage_duplicates():
    assert total_coverage([(1, 4), (1, 4), (1, 4)]) == 3


def test_gaps_basic():
    assert find_gaps([(2, 4), (6, 8)], 0, 10) == [(0, 2), (4, 6), (8, 10)]


def test_gaps_trailing():
    assert find_gaps([(0, 3)], 0, 10) == [(3, 10)]


def test_gaps_fully_covered():
    assert find_gaps([(0, 10)], 0, 10) == []


def test_gaps_interval_beyond_range():
    assert find_gaps([(8, 15)], 0, 10) == [(0, 8)]

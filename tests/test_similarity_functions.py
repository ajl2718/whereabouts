from whereabouts.utils import ngram_jaccard, numeric_overlap, list_overlap


# test ngram_jaccard
def test_ngram_jaccard_identical():
    assert ngram_jaccard("hello", "hello") == 1.0

def test_ngram_jaccard_completely_different():
    score = ngram_jaccard("abc", "xyz")
    assert score == 0.0

def test_ngram_jaccard_partial_overlap():
    score = ngram_jaccard("abc", "abd")
    assert 0.0 < score < 1.0

def test_ngram_jaccard_returns_float():
    assert isinstance(ngram_jaccard("test", "testing"), float)


# test numeric_overlap
def test_numeric_overlap_identical():
    assert numeric_overlap(["1", "2", "3"], ["1", "2", "3"]) == 1.0

def test_numeric_overlap_no_overlap():
    assert numeric_overlap(["1", "2"], ["3", "4"]) == 0.0

def test_numeric_overlap_partial():
    result = numeric_overlap(["1", "2", "3"], ["2", "3", "4"])
    assert result == 2.0 / 3.0


# test list_overlap
def test_list_overlap_above_threshold():
    assert list_overlap(["1", "2", "3"], ["1", "2", "3"], 0.5) is True

def test_list_overlap_below_threshold():
    assert list_overlap(["1", "2", "3"], ["4", "5", "6"], 0.5) is False

def test_list_overlap_none_input():
    assert list_overlap(None, ["1", "2"], 0.5) is False

def test_list_overlap_empty_list2():
    assert list_overlap(["1", "2"], [], 0.5) is False

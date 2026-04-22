import numpy as np
from whereabouts.utils import (
    order_matches,
    get_unmatched,
    filter_to_single_response,
    list_overlap,
    numeric_overlap,
)

def example_match_result():
    return [{'address_id': 3, 
             'address': '115 sydney rd brusnwick 3056 ', 
             'address_id2': 7174666, 
             'address_matched': '115 SYDNEY RD BRUNSWICK VIC 3056', 
             'suburb': 'BRUNSWICK', 
             'postcode': 3056, 
             'latitude': -37.774810791015625, 
             'longitude': 144.9606170654297, 
             'similarity': 0.8076923076923077},
             {'address_id': 1, 
             'address': '115 sydney rd brunswick', 
             'address_id2': 7174666, 
             'address_matched': '115 SYDNEY RD BRUNSWICK VIC 3056', 
             'suburb': 'BRUNSWICK', 
             'postcode': 3056, 
             'latitude': -37.774810791015625, 
             'longitude': 144.9606170654297, 
             'similarity': 0.7551020408163265},
             {'address_id': 2, 
             'address': '115 sydney rd brusnwick 3056 ', 
             'address_id2': np.nan, 
             'address_matched': np.nan, 
             'suburb': np.nan, 
             'postcode': np.nan, 
             'latitude': np.nan, 
             'longitude': np.nan, 
             'similarity': np.nan}]

def test_order_matches():
    matches = example_match_result()
    expected = order_matches(matches)
    assert expected[0]['address_id'] == 1
    assert expected[1]['address_id'] == 2
    assert expected[2]['address_id'] == 3

def test_address_matches():
    matches = example_match_result()
    expected = order_matches(matches)
    assert expected[0]['address_matched'] == "115 SYDNEY RD BRUNSWICK VIC 3056"
    assert expected[2]['address_matched'] == "115 SYDNEY RD BRUNSWICK VIC 3056"

def test_address_match_similarity():
    matches = example_match_result()
    expected = order_matches(matches)
    assert expected[0]['similarity'] > 0.6
    assert expected[2]['similarity'] > 0.6

def test_get_unmatched():
    matches = example_match_result()
    matched, unmatched = get_unmatched(matches, 0.5)
    assert len(matched) == 2
    assert len(unmatched) == 1
    assert matched[0]['address_id'] == 3
    assert matched[1]['address_id'] == 1
    assert unmatched[0]['address_id'] == 2


def test_filter_to_single_response_keeps_highest_similarity():
    matches = [
        {'address_id': 0, 'similarity': 0.9},
        {'address_id': 0, 'similarity': 0.6},
        {'address_id': 1, 'similarity': 0.8},
    ]
    # pre-sorted as order_matches would produce
    result = filter_to_single_response(matches)
    assert len(result) == 2
    assert result[0]['address_id'] == 0
    assert result[0]['similarity'] == 0.9
    assert result[1]['address_id'] == 1


def test_filter_to_single_response_empty():
    assert filter_to_single_response([]) == []


def test_list_overlap_above_threshold():
    assert list_overlap(['1', '2'], ['1', '2', '3'], 0.5) is True


def test_list_overlap_below_threshold():
    assert list_overlap(['1', '2', '3'], ['4'], 0.5) is False


def test_list_overlap_none_input():
    assert list_overlap(None, ['1'], 0.5) is False


def test_list_overlap_empty_list1():
    assert list_overlap([], ['1'], 0.5) is False


def test_list_overlap_empty_list2():
    assert list_overlap(['1'], [], 0.5) is False


def test_numeric_overlap_full_match():
    assert numeric_overlap(['1', '2'], ['1', '2', '3']) == 1.0


def test_numeric_overlap_partial_match():
    assert numeric_overlap(['1', '2'], ['1']) == 0.5


def test_numeric_overlap_no_match():
    assert numeric_overlap(['1'], ['2']) == 0.0


def test_numeric_overlap_empty_input():
    assert numeric_overlap([], ['1']) == 0.0


def test_numeric_overlap_none_input():
    assert numeric_overlap(None, ['1']) == 0.0
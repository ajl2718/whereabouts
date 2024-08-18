import numpy as np
from whereabouts.utils import order_matches, get_unmatched

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
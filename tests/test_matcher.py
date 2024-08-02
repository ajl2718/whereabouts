from whereabouts.Matcher import Matcher 

def example_addresses():
    return ['115 sydney rd brusnwick 3056', 
            '115 sydnee rd brusnwick', 
            '115 sydney rd brunswick']

def test_matching_standard():
    addresses = example_addresses()
    matcher = Matcher('db_test')
    results = matcher.geocode(addresses)
    assert len(results) == 3
    assert results[0]['similarity'] > 0.5
    assert results[2]['similarity'] < results[0]['similarity']

def test_matching_trigram():
    addresses = example_addresses()
    matcher = Matcher('db_test')
    results = matcher.geocode(addresses, how='trigram')
    assert len(results) == 3
    assert results[0]['similarity'] > 0.5
    assert results[1]['similarity'] > 0.5
    assert results[2]['similarity'] > 0.5
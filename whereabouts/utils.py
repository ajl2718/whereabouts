def get_unmatched(results, threshold):
    """
    Given results (outputs from Matcher), filter out those that are correctly matched and
    those that are not.
    """

    # unmatched are those below threshold in similarity value
    # get the id values of the unmatched (so we can correctly order at the end)
    matched = [result for result in results if result['similarity'] >= threshold]
    unmatched = [result for result in results if result['similarity'] < threshold]

    return matched, unmatched

def order_matches(matches):
    """
    Given a list of results order by the address_id value
    """
    matches_sorted = sorted(matches, key=lambda k: k['address_id1']) 
    return matches_sorted
    
from .utils import get_unmatched, order_matches

class MatcherPipeline:
    """
    MatcherPipeline class for concatenating Matcher objects to improve the recall of addresses.

    Attributes
    ----------
    matchers : list of Matcher
        A list of Matcher objects used for geocoding addresses.

    Methods
    -------
    geocode(addresses, address_ids=None) :
        Geocode a list of addresses using the Matcher objects in sequence.
    """
    
    def __init__(self, matchers):
        """
        Initialize a MatcherPipeline object.

        Parameters
        ----------
        matchers : list of Matcher
            A list of Matcher objects to be used in the pipeline.
        """
        if matchers:
            self.matchers = matchers

    def set_matches(self, matchers):
        """
        Set the list of Matcher objects for the pipeline.

        Parameters
        ----------
        matchers : list of Matcher
            A list of Matcher objects to replace the current matchers.
        """
        self.matchers = matchers

    def geocode(self, addresses, address_ids=None):
        """
        Geocode a list of addresses by passing them through each Matcher object in the pipeline.

        Parameters
        ----------
        addresses : list of str
            A list of strings representing addresses or place names.
        address_ids : list of int, optional
            A list of integers representing the IDs of the addresses or place names (default is None).

        Returns
        -------
        results : list of dict
            A list of dictionaries containing the best match for each input address.
        """
        all_results = []

        # Geocode with the first matcher
        matcher = self.matchers[0]
        results = matcher.geocode(addresses)
        threshold = matcher.threshold

        matched, unmatched = get_unmatched(results, threshold)
        addresses0 = [result["address"] for result in unmatched]
        address_ids0 = [result["address_id"] for result in unmatched]

        all_results.extend(matched)

        # Process unmatched addresses with the remaining matchers
        for matcher in self.matchers[1:]:
            if not unmatched:
                break
            results = matcher.geocode(addresses0, address_ids0)
            threshold = matcher.threshold
            matched, unmatched = get_unmatched(results, threshold)

            addresses0 = [result["address"] for result in unmatched]
            address_ids0 = [result["address_id"] for result in unmatched]

            all_results.extend(matched)

        # Combine matched and unmatched results, and order them
        results = all_results + unmatched
        results = order_matches(results)

        return results
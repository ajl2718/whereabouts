from time import time
from .utils import get_unmatched, order_matches


class MatcherPipeline(object):
    def __init__(self, matchers):
        """
        matchers: list of Matcher objects
        """
        self.matchers = matchers

    def match(self, addresses, address_ids=None):
        """
        Pass the list of addresses through each of the matchers, filtering out those that
        are likely to be correctly matched at each step

        Args:
        addresses: list of strs representing addresses or place names
        address_ids (default=None): list of ints representing the id values of addresses or place names

        Return:
        all_results: list of dicts representing the best match do each of the addresses
        """
        all_results = []

        # this needs to be optimised
        matcher = self.matchers[0]
        results = matcher.match(addresses)
        threshold = matcher.threshold

        matched, unmatched = get_unmatched(results, threshold)
        addresses0 = [result["input_address"] for result in unmatched]
        address_ids0 = [result["address_id1"] for result in unmatched]

        all_results += matched

        # if there are unmatched addresses then send to next matcher
        for matcher in self.matchers[1:]:
            if len(unmatched) == 0:
                break
            results = matcher.match(addresses0, address_ids0)
            threshold = matcher.threshold
            matched, unmatched = get_unmatched(results, threshold)

            addresses0 = [result["input_address"] for result in unmatched]
            address_ids0 = [result["address_id1"] for result in unmatched]

            all_results += matched

        answers = all_results + unmatched
        answers = order_matches(answers)

        return answers

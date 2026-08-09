# Test the performance (accuracy, sensitivity, speed) on a set of addresses of varying quality
from time import time
import pandas as pd

from whereabouts import Matcher

# load a matcher
matcher = Matcher("au_all_sm", how="standard")

# load the test set
df_tests = pd.read_csv("tests/test_set.csv")
addresses = df_tests.input_address.tolist()
addresses_correct = df_tests.correct_match.tolist()

# compare results from geocoder with correct matches
t1 = time()
results = matcher.geocode(addresses)
t2 = time()

matches = [
    (add0, add1["address_matched"], add2)
    for add0, add1, add2 in zip(addresses, results, addresses_correct)
    if add1["address_matched"] == add2
]
non_matches = [
    (add0, add1["address_matched"], add2)
    for add0, add1, add2 in zip(addresses, results, addresses_correct)
    if add1["address_matched"] != add2
]
num_matches = len(matches)
matching_time = t2 - t1

print("\nResults for matching")
print("--------------------")
print(f"Geocoded {len(addresses)} addresses in {t2 - t1:.2f}s")
print(f"Correctly matched: {num_matches}")
print(f"Unmatched: {len(addresses) - num_matches}")
print(f"Accuracy: {num_matches / len(addresses) * 100}%")
print(f"{'input address':<50}{'matched address':<50}{'correct address'}")
for non_match in non_matches:
    a = "" if non_match[0] is None else str(non_match[0])
    b = "" if non_match[1] is None else str(non_match[1])
    c = "" if non_match[2] is None else str(non_match[2])
    print(f"{a[:48]:<50}{b[:48]:<50}{c[:48]}")

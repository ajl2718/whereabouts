# Example of basic geocoding
from whereabouts import Matcher

# Create a matcher for the Australian state of Victoria
matcher = Matcher('au_vic_all')

# Match a single address
match = matcher.geocode('1 Spring Street, Melbourne')
print(match)

# Match a list of addresses
matches = matcher.geocode([
    '1 Spring Street, Melbourne',
    '2 Spring Street, Melbourne',
    '3 Spring Street, Melbourne'
])
print(matches)
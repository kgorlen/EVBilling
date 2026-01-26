"""
This script checks if a set of PG&E account numbers are valid using various check digit algorithms.
"""

from checkdigit import gs1, isbn, luhn, verhoeff

accounts = (
    "3750712318-2", # Palace BEV-1
    "8675852614-8", # Palace E1 TB (incorrect)
    "0347802911-3", # Palace B1
    "8582169278-8", # Unit 404
)

for method in [gs1, isbn, luhn, verhoeff]:
    ok = [method.validate(account.replace("-", "")) for account in accounts]
    if all(ok):
        print(f'{method.__name__} is valid for all accounts')
    else:
        print(f'{method.__name__} fails on {sum(1 for _ in ok if not _)} of {len(ok)} accounts')

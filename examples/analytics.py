"""Analytics examples for ratios and compare endpoints."""

import os

from sahmk import SahmkClient


def main():
    client = SahmkClient(os.environ["SAHMK_API_KEY"])

    ratios = client.ratios("1120")
    print("Ratios keys:", list(ratios.keys()))
    print("Ratios meta:", ratios.get("meta", {}))

    compare = client.compare(["1120", "1180", "1010"])
    print("Compare keys:", list(compare.keys()))
    print("Compare count:", compare.get("count"))
    print("Compare meta:", compare.get("meta", {}))


if __name__ == "__main__":
    main()

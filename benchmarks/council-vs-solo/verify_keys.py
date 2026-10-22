#!/usr/bin/env python3
"""Check the answer keys: every planted bug reproduces, every decoy is correct, every math answer is right.

  python verify_keys.py      exit 1 if any check fails
"""
from datetime import datetime, timedelta
from decimal import Decimal
from fractions import Fraction
import json
from pathlib import Path
import sys
import time

import bench

CASES = {c["id"]: c for c in bench.load_cases()}


def module(case_id):
    ns = {}
    exec("\n".join(bench.MARK.sub("", line) for line in CASES[case_id]["code"]), ns)
    return ns


def raises(fn, exc):
    try:
        fn()
    except exc:
        return True
    return False


def review_utils():
    m = module("review-utils")
    first = m["add_tag"]("a")
    return {"chunk": m["chunk"]([1, 2, 3, 4, 5], 2) != [[1, 2], [3, 4], [5]],
            "default": m["add_tag"]("b") is first,
            "median": raises(lambda: m["median"]([1, 2]), IndexError),
            "adult": m["is_adult"](18) is False,
            "last": m["last_n"]([1, 2, 3], 0) != []}, [m["safe_div"](1, 0) == 0]


def review_hard():
    m = module("review-hard")
    c1, c2 = m["Counter"](), m["Counter"]()
    c1.add("x")
    a = m["stamp"]({})
    time.sleep(0.01)
    g = [[1]]
    copy = m["copy_grid"](g)
    copy[0][0] = 9
    xs = [-1, -2, 3]
    m["remove_negatives"](xs)
    bugs = {"shared": c2.counts.get("x") == 1, "stamp": a["at"] == m["stamp"]({})["at"],
            "closure": [f(1) for f in m["make_multipliers"]()] != [0, 1, 2], "anchor": m["is_valid_id"]("ABC12345"),
            "bsearch": m["find"]([5], 5) == -1, "iterate": xs != [3], "float": m["total_cents"](["0.29"]) != 29,
            "shallow": g[0][0] == 9}
    decoys = [m["clamp"](5, 0, 3) == 3 and m["clamp"](-1, 0, 3) == 0, m["chunks_of"]("abcde", 2) == ["ab", "cd", "e"],
              m["same_object"](g, g) and not m["same_object"]([1], [1]),
              m["first_word"]("  hi there") == "hi" and m["first_word"]("  ") == ""]
    return bugs, decoys


def review_large():
    m = module("review-large")
    now = datetime(2026, 10, 22)

    def order(sku="A", qty=1, status="paid", created=now):
        return m["Order"](sku, qty, Decimal("1.00"), status, created)
    groups = m["empty_groups"](["a", "b"])
    groups["a"].append(1)
    xs = [order(created=now - timedelta(days=2)), order(created=now)]
    first = xs[0]
    m["newest_first"](xs)
    bugs = {"page": m["page"](list(range(10)), 1, 3) != [0, 1, 2],
            "round": m["to_cents"](Decimal("2.675")) != Decimal("2.68"),
            "datesort": [r["date"] for r in m["by_date"]([{"date": "10/1/2026"}, {"date": "9/1/2026"}])][0] != "9/1/2026",
            "fromkeys": groups["b"] == [1],
            "swallow": not raises(lambda: m["parse_rows"](["a,1", "bad"]), ValueError),
            "expiry": m["is_expired"](order(created=now - timedelta(days=30)), now) is False,
            "case": m["find_sku"]([order(sku="abc")], "ABC") == [],
            "floordiv": m["mean_qty"]([order(qty=1), order(qty=2)]) != 1.5,
            "allany": m["all_paid"]([order(), order(status="open")]) is True,
            "inplace": xs[0] is not first,
            "window": len(m["window"]([order(created=now + timedelta(days=1))], now, 1)) == 1,
            "below": m["restock_list"]({"x": 5}, 5) == ["x"]}
    tagged = [order()]
    m["tag_all"](tagged, "t")
    m["tag_all"](tagged, "t")
    decoys = [m["paid_share"]([order(), order(status="open")]) == 0.5 and m["paid_share"]([]) == 0.0,
              m["available"](3, 5) == 0 and m["available"](5, 3) == 2, tagged[0].tags == ["t"],
              m["total_qty_by_sku"]([order(sku="Ab", qty=2), order(sku="aB", qty=3)]) == {"ab": 5},
              m["first_paid"]([order(status="open"), order(sku="Z")]).sku == "Z"]
    return bugs, decoys


def math_traps():
    a, b = 1, 2
    for _ in range(8):
        a, b = b, a + b
    angle = abs(30 * 3 + 0.5 * 40 - 6 * 40)
    got = {"1": pow(7, 2026, 100), "2": sum(2026 // 5 ** k for k in range(1, 6)), "3": sum(map(int, str(2 ** 20))),
           "4": b, "5": sum(1 for i in range(1, 10000) if sum(map(int, str(i))) == 9),
           "6": sum(Fraction(6, k) for k in range(1, 7)), "7": sum(1 for n in range(1, 101) if (n * n + 1) % 5 == 0),
           "8": int(min(angle, 360 - angle)), "9": 20 * 17 // 2, "10": (10 ** 100 // 7) % 10}
    return {q: Fraction(str(v)) == Fraction(CASES["math-traps"]["answers"][q]) for q, v in got.items()}


def main():
    ok = True
    for name, check in (("review-utils", review_utils), ("review-hard", review_hard), ("review-large", review_large)):
        bugs, decoys = check()
        planted = set(bench.review_key(CASES[name])[1])
        good = all(bugs.values()) and all(decoys) and set(bugs) == planted
        ok &= good
        print(f"{'ok  ' if good else 'FAIL'} {name}: {sum(bugs.values())}/{len(planted)} bugs reproduce, "
              f"{sum(decoys)}/{len(decoys)} decoys correct")
    m = math_traps()
    ok &= all(m.values())
    print(f"{'ok  ' if all(m.values()) else 'FAIL'} math-traps: {sum(m.values())}/{len(m)} answers verified")
    print("claims: checked by hand; the wrong ones are 3 (10 is 25% relative), 4 (overlap is not a test), "
          "6 (0.8 x 1.2 = 0.96), 7 (p is not P(null)), 9 (SE falls by sqrt 2)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

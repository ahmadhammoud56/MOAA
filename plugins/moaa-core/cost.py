#!/usr/bin/env python3
"""AI cost calculator: the billing equations of the 2026-11-01 cost review (docs/research), standard library only.

  python cost.py blended --in I --out O [--read R] [--hit H] [--write-frac W --write-price P] [--input-share S]
  python cost.py breakeven --plan S --rate B            millions of blended tokens where a flat plan ties pay-as-you-go
  python cost.py bundle --plan S --credit K --eligible B [--ineligible X]   plan with API credits: real monthly cash
  python cost.py local --price C --resale F --energy E [--maintenance M] --tokens T   $/M of a bought machine
  python cost.py cloud --hourly P --duty U --prefill TP --decode TD   $/M of a rented GPU at a duty cycle
  python cost.py success --cost C --rate P              cost per successful task (C/p)
  python cost.py rewarm --tokens N --write W --read R   re-writing a cold prompt cache vs reading a warm one
  python cost.py selftest

Units: prices in $ per million tokens; a "blended" million is 80% input, 20% output unless --input-share says
otherwise; tokens in millions per month. Cache hits (h) and charged cache writes (w) are disjoint shares of input.
Prices are inputs, never built in: a calculator should not go stale with a price list. Off: there is nothing to turn
off, it runs only when called.
"""
import argparse
import sys


def blended(i, o, read=None, hit=0.0, write_frac=0.0, write_price=None, input_share=0.8):
    """$ per million blended tokens: s[(1-h-w)I + hR + wW] + (1-s)O."""
    if hit + write_frac > 1:
        raise ValueError("cache hits and writes are shares of the same input; together at most 1")
    read = i if read is None else read
    write_price = i if write_price is None else write_price
    return input_share * ((1 - hit - write_frac) * i + hit * read + write_frac * write_price) + (1 - input_share) * o


def break_even(plan, rate):
    """Millions of blended tokens a month at which a flat plan ties pay-as-you-go at `rate` $/M."""
    return plan / rate


def bundle(plan, credit, eligible, ineligible=0.0):
    """Monthly cash of a plan that includes `credit` $ of API credit, for `eligible` $ of API work it covers."""
    return plan + max(0.0, eligible - credit) + ineligible


def local_per_million(price, resale_fraction, energy, tokens_m, maintenance=0.0, months=36):
    """$ per million delivered tokens of a bought machine: (price - resale)/months + energy + maintenance, over the
    tokens it really delivers, not its theoretical 24/7 capacity."""
    if tokens_m <= 0:
        raise ValueError("delivered tokens must be positive")
    return (price * (1 - resale_fraction) / months + energy + maintenance) / tokens_m


def cloud_per_million(hourly, duty, prefill_tps, decode_tps, input_share=0.8):
    """$ per million blended tokens of a rented GPU billed by the hour but busy only `duty` of the time."""
    seconds = 1e6 * (input_share / prefill_tps + (1 - input_share) / decode_tps)
    return hourly * seconds / 3600 / duty


def per_success(cost, success_rate):
    """Cost per successful task: a cheap route that fails often can cost more than a dear one that works."""
    if not 0 < success_rate <= 1:
        raise ValueError("success rate must be in (0, 1]")
    return cost / success_rate


def rewarm(tokens, write, read):
    """(cost to re-write a cold cache, cost to read it warm, the difference) in $ for `tokens` prompt tokens."""
    cold, warm = tokens * write / 1e6, tokens * read / 1e6
    return cold, warm, cold - warm


def selftest():
    assert abs(blended(2, 10) - 3.60) < 1e-9
    assert abs(blended(2, 10, read=0.1, hit=0.5) - 2.84) < 1e-9
    assert abs(blended(2, 10, read=0.1, hit=0.5, write_frac=0.5, write_price=2.5) - 3.04) < 1e-9
    assert abs(blended(0.06, 0.18, read=0.015, hit=0.5) - 0.066) < 1e-9
    assert abs(break_even(25, 0.066) - 378.788) < 1e-3
    assert bundle(100, 100, 150) == 150 and bundle(200, 200, 150) == 200
    assert abs(local_per_million(2289, 0.35, 0.0684, 1.037) - 39.91) < 0.02  # the review rounds
    assert abs(cloud_per_million(0.59, 0.10, 1e12, 50) - 6.556) < 1e-3  # decode-only (prefill free) as in the review
    assert abs(per_success(0.20, 0.5) - 0.40) < 1e-9
    cold, warm, extra = rewarm(412_000, 6.25, 0.5)
    assert abs(cold - 2.575) < 1e-9 and abs(extra - 2.369) < 1e-9
    return "cost.py selftest: ok"


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("blended")
    a.add_argument("--in", dest="i", type=float, required=True); a.add_argument("--out", type=float, required=True)
    a.add_argument("--read", type=float); a.add_argument("--hit", type=float, default=0.0)
    a.add_argument("--write-frac", type=float, default=0.0); a.add_argument("--write-price", type=float)
    a.add_argument("--input-share", type=float, default=0.8)
    a = sub.add_parser("breakeven"); a.add_argument("--plan", type=float, required=True); a.add_argument("--rate", type=float, required=True)
    a = sub.add_parser("bundle")
    for k in ("plan", "credit", "eligible"):
        a.add_argument(f"--{k}", type=float, required=True)
    a.add_argument("--ineligible", type=float, default=0.0)
    a = sub.add_parser("local")
    for k in ("price", "resale", "energy", "tokens"):
        a.add_argument(f"--{k}", type=float, required=True)
    a.add_argument("--maintenance", type=float, default=0.0)
    a = sub.add_parser("cloud")
    for k in ("hourly", "duty", "prefill", "decode"):
        a.add_argument(f"--{k}", type=float, required=True)
    a = sub.add_parser("success"); a.add_argument("--cost", type=float, required=True); a.add_argument("--rate", type=float, required=True)
    a = sub.add_parser("rewarm")
    for k in ("tokens", "write", "read"):
        a.add_argument(f"--{k}", type=float, required=True)
    sub.add_parser("selftest")
    x = p.parse_args(argv)
    try:
        if x.cmd == "blended":
            print(f"${blended(x.i, x.out, x.read, x.hit, x.write_frac, x.write_price, x.input_share):.4f} per million blended tokens")
        elif x.cmd == "breakeven":
            print(f"{break_even(x.plan, x.rate):.3f}M blended tokens a month")
        elif x.cmd == "bundle":
            print(f"${bundle(x.plan, x.credit, x.eligible, x.ineligible):.2f} a month")
        elif x.cmd == "local":
            print(f"${local_per_million(x.price, x.resale, x.energy, x.tokens, x.maintenance):.2f} per million delivered tokens")
        elif x.cmd == "cloud":
            print(f"${cloud_per_million(x.hourly, x.duty, x.prefill, x.decode):.3f} per million blended tokens")
        elif x.cmd == "success":
            print(f"${per_success(x.cost, x.rate):.4f} per successful task")
        elif x.cmd == "rewarm":
            cold, warm, extra = rewarm(x.tokens, x.write, x.read)
            print(f"cold re-write ${cold:.2f}, warm read ${warm:.2f}, keeping it warm saves ${extra:.2f} per prompt")
        else:
            print(selftest())
    except (ValueError, AssertionError) as e:
        print(f"cost: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

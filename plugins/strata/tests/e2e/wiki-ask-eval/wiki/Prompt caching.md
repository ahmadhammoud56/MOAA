# Prompt caching

A cache read costs about a tenth of the base input price, while a five-minute cache write costs 1.25 times the base
input price. A cached prefix must match the earlier request exactly, so stable instructions belong first and changing
text last. With half of the input tokens served from the cache, the total bill falls by about a fifth, because output
tokens are still paid in full.

Sources: raw/anthropic-pricing.md

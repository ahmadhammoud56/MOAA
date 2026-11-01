# Gated DeltaNet

Gated DeltaNet combines an exponential decay gate with a delta-rule write that corrects the value stored for a key.
Its recurrent state has a fixed size, so decoding memory does not grow with the length of the context. Hybrid models
interleave three Gated DeltaNet layers with one attention layer to keep exact retrieval.

Sources: raw/gdn-paper.md

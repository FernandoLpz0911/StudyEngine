"""
Deep Knowledge Tracing (DKT) — optional ML layer on top of FSRS.

Only activates once DKT_MIN_INTERACTIONS have been logged AND the latest
checkpoint achieves val_AUC >= DKT_MIN_AUC (both set in engine/config.py).

Modules
-------
model         DKT LSTM architecture (PyTorch).
train         Training loop with early stopping; saves best checkpoint to disk.
infer         predict() returns P(correct) per concept from interaction history.
concept_index Maps concept_id strings to integer LSTM input indices.
"""

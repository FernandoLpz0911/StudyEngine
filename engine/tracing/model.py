"""P5.2 — DKT LSTM model (Piech et al., NeurIPS 2015)."""
from __future__ import annotations

import torch
import torch.nn as nn


class DKT(nn.Module):
    def __init__(
        self,
        n_concepts: int,
        hidden: int = 128,
        layers: int = 1,
        dropout: float = 0.2,
        n_features: int = 0,
    ) -> None:
        super().__init__()
        self.n = n_concepts
        self.n_features = n_features
        self.lstm = nn.LSTM(
            2 * n_concepts + n_features,
            hidden,
            num_layers=layers,
            batch_first=True,
            dropout=dropout if layers > 1 else 0.0,
        )
        self.out = nn.Linear(hidden, n_concepts)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """x: (B, T, 2M + n_features) → (B, T, M) predicted P(correct) per concept."""
        h, _ = self.lstm(x)
        return torch.sigmoid(self.out(h))

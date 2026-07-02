"""Fit personal FSRS parameters: python -m engine.cli.fsrs_fit [--force].

Re-fits the 21 FSRS weights to your own review log (needs FSRS_MIN_REVIEWS graded
answers). The fitted weights persist in the database and take effect on the next
review. Run occasionally — e.g. once per few hundred new reviews.
"""
from __future__ import annotations

import argparse

import engine.subjects  # noqa: F401  (registers generators; ensures concepts load)
from engine.db.seed import load_all
from engine.scheduler import optimize


def main() -> None:
    parser = argparse.ArgumentParser(description="Fit personal FSRS weights.")
    parser.add_argument(
        "--verbose", action="store_true", help="show optimizer progress"
    )
    args = parser.parse_args()

    load_all()
    current = optimize.stored_parameters()
    print(f"Current weights: {'personal fit' if current else 'py-fsrs defaults'}")

    result = optimize.fit(verbose=args.verbose)
    if not result["fitted"]:
        print(
            f"Not enough graded reviews yet: {result['reviews']}/{result['gate']}. "
            "Keep studying — the fit unlocks automatically."
        )
        return
    params = ", ".join(f"{p:.4f}" for p in result["parameters"])
    print(f"Fitted on {result['reviews']} reviews. New weights:\n  [{params}]")
    print("Saved — intervals now match how you actually forget.")


if __name__ == "__main__":
    main()

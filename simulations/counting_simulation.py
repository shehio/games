"""Card counting simulation — measures effect of counting on house edge.

Combines card counting systems with betting strategies and sweeps across
shoe penetration thresholds to compare their performance.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from shared.models import Card

from simulations.betting import (
    BettingStrategy,
    FlatBetting,
    KellyBetting,
    MartingaleBetting,
    SpreadBetting,
)
from simulations.card_counting import (
    CardCounter,
    HiLoCounter,
    KOCounter,
    OmegaIICounter,
)
from simulations.shoe_penetration import BET, build_shoe, simulate_hand


@dataclass
class CountingResult:
    counter_name: str
    bettor_name: str
    threshold: int
    hands_played: int
    house_edge_pct: float
    avg_bet: float
    total_wagered: int
    total_net: int


def run_counting_simulation(
    counter: CardCounter,
    bettor: BettingStrategy,
    threshold: int = 78,
    num_hands: int = 100_000,
    seed: int = 42,
    num_decks: int = 6,
) -> CountingResult:
    """Run a counting simulation with the given counter and betting strategy."""
    rng = random.Random(seed)
    total_wagered = 0
    total_net = 0
    hands_played = 0

    shoe: list[Card] = []
    previous_net = 0

    while hands_played < num_hands:
        if len(shoe) <= threshold:
            shoe = build_shoe(num_decks)
            rng.shuffle(shoe)
            counter.reset()
            previous_net = 0

        bet = bettor.get_bet(counter.true_count, previous_net)
        bet = max(bet, bettor.min_bet)

        outcome = simulate_hand(shoe, bet=bet)
        if outcome.cards_used == 0:
            shoe = []
            continue

        for card in outcome.cards_dealt:
            counter.observe(card)

        hands_played += 1
        total_wagered += bet
        total_net += outcome.net
        previous_net = outcome.net

    house_edge = (-total_net / total_wagered * 100) if total_wagered > 0 else 0.0
    avg_bet = total_wagered / hands_played if hands_played > 0 else 0.0

    return CountingResult(
        counter_name=type(counter).__name__,
        bettor_name=type(bettor).__name__,
        threshold=threshold,
        hands_played=hands_played,
        house_edge_pct=round(house_edge, 4),
        avg_bet=round(avg_bet, 2),
        total_wagered=total_wagered,
        total_net=total_net,
    )


def sweep_strategies(
    thresholds: list[int] | None = None,
    num_hands: int = 50_000,
    seed: int = 42,
) -> list[CountingResult]:
    """Cross-product of counters x bettors x thresholds."""
    if thresholds is None:
        thresholds = [52, 78, 130]

    counters: list[tuple[str, type[CardCounter]]] = [
        ("Hi-Lo", HiLoCounter),
        ("Omega II", OmegaIICounter),
        ("KO", KOCounter),
    ]
    bettors: list[tuple[str, type[BettingStrategy]]] = [
        ("Flat", FlatBetting),
        ("Spread", SpreadBetting),
        ("Kelly", KellyBetting),
        ("Martingale", MartingaleBetting),
    ]

    results: list[CountingResult] = []
    for threshold in thresholds:
        for _cname, counter_cls in counters:
            for _bname, bettor_cls in bettors:
                result = run_counting_simulation(
                    counter=counter_cls(),
                    bettor=bettor_cls(base_bet=BET),
                    threshold=threshold,
                    num_hands=num_hands,
                    seed=seed,
                )
                results.append(result)
    return results


def main() -> None:
    """Run strategy sweep and print comparison table."""
    print("Card Counting Strategy Comparison")
    print("=" * 85)
    print(
        f"{'Counter':<16} {'Bettor':<18} {'Threshold':>9} "
        f"{'House Edge %':>13} {'Avg Bet':>9} {'Net':>10}"
    )
    print("-" * 85)

    results = sweep_strategies(num_hands=50_000, seed=42)

    for r in results:
        print(
            f"{r.counter_name:<16} {r.bettor_name:<18} {r.threshold:>9} "
            f"{r.house_edge_pct:>13.4f} {r.avg_bet:>9.2f} {r.total_net:>10}"
        )

    print("-" * 85)

    # Show best result by house edge
    best = min(results, key=lambda r: r.house_edge_pct)
    print(f"\nBest combination: {best.counter_name} + {best.bettor_name}")
    print(f"  Threshold: {best.threshold} cards remaining")
    print(f"  House edge: {best.house_edge_pct:.4f}%")
    print(f"  Avg bet: ${best.avg_bet:.2f}")


if __name__ == "__main__":
    main()

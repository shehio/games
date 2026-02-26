"""Monte Carlo simulation for blackjack shoe penetration analysis.

Sweeps reshuffle thresholds across a 6-deck shoe to empirically determine
the optimal point at which to reshuffle, measuring house edge, hands per
shoe, and blackjack frequency.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from shared.models import Action, Card, Rank, Suit, best_total, is_blackjack

# ---------------------------------------------------------------------------
# Basic strategy tables
# ---------------------------------------------------------------------------
# Key format: (player_total, dealer_upcard_value)
# Values: H=hit, S=stand, D=double (hit if can't), P=split
#
# Dealer upcard values: 2-9 map directly, 10 covers 10/J/Q/K, 11 = Ace.
# Tables encode standard basic strategy for 6-deck, dealer stands on soft 17.

# Hard totals: rows 5-21, columns dealer 2-11
_HARD = {
    5: "HHHHHHHHHH",
    6: "HHHHHHHHHH",
    7: "HHHHHHHHHH",
    8: "HHHHHHHHHH",
    9: "HHDDHHHHHH",
    10: "DDDDDDDDHH",
    11: "DDDDDDDDDH",
    12: "HHSSHHHHHH",
    13: "SSSSHHHHHH",
    14: "SSSSHHHHHH",
    15: "SSSSHHHHHH",
    16: "SSSSHHHHHH",
    17: "SSSSSSSSSS",
    18: "SSSSSSSSSS",
    19: "SSSSSSSSSS",
    20: "SSSSSSSSSS",
    21: "SSSSSSSSSS",
}

# Soft totals (Ace counted as 11): rows A+2..A+9 (13..20)
_SOFT = {
    13: "HHHHHHHHHH",
    14: "HHHHHHHHHH",
    15: "HHHDHHHHHH",
    16: "HHHDHHHHHH",
    17: "HHDDDHHHHH",
    18: "SDDDDSSHHH",
    19: "SSSSSSSSSS",
    20: "SSSSSSSSSS",
}

# Pair splits: row is the card value (2..11 where 11=A)
_PAIR = {
    2: "PPHPPPHHHHH"[:10],  # trim to 10
    3: "PPHPPPHHHHH"[:10],
    4: "HHHHHHHHHH",
    5: "DDDDDDDDHH",
    6: "PPPPPHHHHH",
    7: "PPPPPPHHHH",
    8: "PPPPPPPPPP",
    9: "PPPPPSPPSS",
    10: "SSSSSSSSSS",
    11: "PPPPPPPPPP",
}

# Fix pair table entries to be exactly 10 chars
_PAIR[2] = "PPPPPPHHHH"
_PAIR[3] = "PPPPPPHHHH"

_DEALER_COLS = [2, 3, 4, 5, 6, 7, 8, 9, 10, 11]  # 11 = Ace


def _card_value(rank: Rank) -> int:
    """Return the numeric value of a rank for strategy lookup (Ace=11)."""
    if rank == Rank.ACE:
        return 11
    if rank in (Rank.JACK, Rank.QUEEN, Rank.KING):
        return 10
    return int(rank.value)


def _dealer_col(upcard: Card) -> int:
    """Return the dealer column index (0-9) for strategy lookup."""
    v = _card_value(upcard.rank)
    return _DEALER_COLS.index(v)


def _is_soft(cards: list[Card]) -> bool:
    """Check if the hand is soft (has an Ace counted as 11)."""
    total = 0
    aces = 0
    for c in cards:
        v = _card_value(c.rank)
        if v == 11:
            aces += 1
            total += 11
        else:
            total += v
    # Soft means at least one ace is still 11 and total <= 21
    return aces > 0 and total <= 21


def basic_strategy_decision(
    player_cards: list[Card],
    dealer_upcard: Card,
    can_split: bool,
    can_double: bool,
) -> Action:
    """Return the basic strategy action for the given situation."""
    col = _dealer_col(dealer_upcard)
    p_total = best_total(player_cards)

    # Pair splitting
    if can_split and len(player_cards) == 2:
        v1 = _card_value(player_cards[0].rank)
        v2 = _card_value(player_cards[1].rank)
        if v1 == v2 and v1 in _PAIR:
            code = _PAIR[v1][col]
            if code == "P":
                return Action.SPLIT

    # Soft totals
    if _is_soft(player_cards) and 13 <= p_total <= 20:
        code = _SOFT[p_total][col]
        if code == "D":
            return Action.DOUBLE if can_double else Action.HIT
        return Action.HIT if code == "H" else Action.STAND

    # Hard totals
    if p_total in _HARD:
        code = _HARD[p_total][col]
        if code == "D":
            return Action.DOUBLE if can_double else Action.HIT
        return Action.HIT if code == "H" else Action.STAND

    # Fallback: 4 or below hit, everything else already covered
    if p_total <= 4:
        return Action.HIT
    return Action.STAND


# ---------------------------------------------------------------------------
# Shoe builder
# ---------------------------------------------------------------------------


def build_shoe(num_decks: int = 6) -> list[Card]:
    """Build and shuffle a shoe of the given number of decks."""
    shoe = [Card(rank=r, suit=s) for _ in range(num_decks) for s in Suit for r in Rank]
    return shoe


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------

BET = 100  # fixed flat bet for simulation


@dataclass
class HandOutcome:
    net: int  # net payout (positive = player won)
    is_blackjack: bool
    cards_used: int  # how many cards were consumed from the shoe
    cards_dealt: list[Card] = field(default_factory=list)  # all cards dealt this hand


def simulate_hand(shoe: list[Card], bet: int = BET) -> HandOutcome:
    """Simulate one hand of blackjack using basic strategy. Returns outcome.

    Draws cards from the front of `shoe` (mutates it in place).
    """
    start_len = len(shoe)
    if len(shoe) < 10:
        # Not enough cards to play a hand
        return HandOutcome(net=0, is_blackjack=False, cards_used=0)

    dealt: list[Card] = []

    def draw() -> Card:
        card = shoe.pop(0)
        dealt.append(card)
        return card

    # Deal
    player_cards = [draw(), draw()]
    dealer_cards = [draw(), draw()]

    # Check naturals
    player_bj = is_blackjack(player_cards)
    dealer_bj = is_blackjack(dealer_cards)

    if player_bj or dealer_bj:
        if player_bj and dealer_bj:
            return HandOutcome(
                net=0, is_blackjack=True, cards_used=start_len - len(shoe), cards_dealt=dealt
            )
        if player_bj:
            return HandOutcome(
                net=int(bet * 1.5),
                is_blackjack=True,
                cards_used=start_len - len(shoe),
                cards_dealt=dealt,
            )
        # dealer bj
        return HandOutcome(
            net=-bet, is_blackjack=False, cards_used=start_len - len(shoe), cards_dealt=dealt
        )

    # Player hands (support single split)
    hands: list[tuple[list[Card], int]] = [(player_cards, bet)]
    final_hands: list[tuple[list[Card], int, bool]] = []  # cards, hand_bet, busted

    i = 0
    while i < len(hands):
        cards, hand_bet = hands[i]
        can_split = (
            len(cards) == 2
            and len(hands) == 1
            and _card_value(cards[0].rank) == _card_value(cards[1].rank)
            and len(final_hands) == 0
        )
        can_double = len(cards) == 2

        while True:
            if len(shoe) == 0:
                break
            action = basic_strategy_decision(cards, dealer_cards[0], can_split, can_double)

            if action == Action.STAND:
                break

            if action == Action.SPLIT:
                c1, c2 = cards
                hand1 = [c1, draw()]
                hand2 = [c2, draw()]
                hands[i] = (hand1, bet)
                hands.append((hand2, bet))
                cards, hand_bet = hands[i]
                can_split = False
                can_double = len(cards) == 2
                continue

            if action == Action.DOUBLE:
                cards.append(draw())
                hand_bet *= 2
                hands[i] = (cards, hand_bet)
                break

            if action == Action.HIT:
                cards.append(draw())
                can_split = False
                can_double = False
                if best_total(cards) > 21:
                    break

        final_hands.append((cards, hand_bet, best_total(cards) > 21))
        i += 1

    # Dealer plays (only if not all player hands busted)
    all_busted = all(b for _, _, b in final_hands)
    if not all_busted:
        while best_total(dealer_cards) < 17 and len(shoe) > 0:
            dealer_cards.append(draw())

    dealer_total = best_total(dealer_cards)
    dealer_bust = dealer_total > 21

    # Resolve
    total_net = 0
    for cards, hand_bet, busted in final_hands:
        if busted:
            total_net -= hand_bet
        elif dealer_bust:
            total_net += hand_bet
        else:
            pt = best_total(cards)
            if pt > dealer_total:
                total_net += hand_bet
            elif pt < dealer_total:
                total_net -= hand_bet
            # else push: net 0

    cards_used = start_len - len(shoe)
    return HandOutcome(net=total_net, is_blackjack=False, cards_used=cards_used, cards_dealt=dealt)


def run_simulation(
    threshold: int,
    num_hands: int = 100_000,
    seed: int = 42,
    num_decks: int = 6,
) -> dict:
    """Run num_hands at the given reshuffle threshold.

    Returns dict with: threshold, hands_played, house_edge_pct,
    avg_hands_per_shoe, blackjack_rate_pct.
    """
    rng = random.Random(seed)
    total_wagered = 0
    total_net = 0
    blackjacks = 0
    hands_played = 0
    shoes_used = 0

    shoe: list[Card] = []

    while hands_played < num_hands:
        # Reshuffle when remaining cards <= threshold
        if len(shoe) <= threshold:
            shoe = build_shoe(num_decks)
            rng.shuffle(shoe)
            shoes_used += 1

        outcome = simulate_hand(shoe)
        if outcome.cards_used == 0:
            # Shoe too depleted, force reshuffle
            shoe = []
            continue

        hands_played += 1
        total_wagered += BET
        total_net += outcome.net
        if outcome.is_blackjack:
            blackjacks += 1

    house_edge = (-total_net / total_wagered * 100) if total_wagered > 0 else 0.0
    avg_hands = hands_played / shoes_used if shoes_used > 0 else 0.0
    bj_rate = (blackjacks / hands_played * 100) if hands_played > 0 else 0.0

    return {
        "threshold": threshold,
        "hands_played": hands_played,
        "house_edge_pct": round(house_edge, 4),
        "avg_hands_per_shoe": round(avg_hands, 2),
        "blackjack_rate_pct": round(bj_rate, 4),
        "total_wagered": total_wagered,
        "total_net": total_net,
    }


def sweep_thresholds(
    thresholds: list[int] | None = None,
    num_hands: int = 100_000,
    seed: int = 42,
) -> list[dict]:
    """Sweep multiple reshuffle thresholds and return results."""
    if thresholds is None:
        thresholds = list(range(26, 235, 26))  # [26, 52, 78, ..., 234]
    return [run_simulation(t, num_hands, seed) for t in thresholds]


def main() -> None:
    """Run the sweep and print a formatted results table."""
    print("Monte Carlo Shoe Penetration Analysis")
    print("=" * 70)
    print(f"{'Threshold':>10} {'Hands/Shoe':>12} {'House Edge %':>14} {'BJ Rate %':>11}")
    print("-" * 70)

    results = sweep_thresholds(num_hands=100_000, seed=42)

    best = min(results, key=lambda r: r["house_edge_pct"])

    for r in results:
        marker = " <-- best" if r["threshold"] == best["threshold"] else ""
        print(
            f"{r['threshold']:>10} "
            f"{r['avg_hands_per_shoe']:>12.1f} "
            f"{r['house_edge_pct']:>14.4f} "
            f"{r['blackjack_rate_pct']:>11.4f}"
            f"{marker}"
        )

    print("-" * 70)
    print(f"\nOptimal threshold: {best['threshold']} cards remaining")
    print(f"  House edge: {best['house_edge_pct']:.4f}%")
    print(f"  Avg hands per shoe: {best['avg_hands_per_shoe']:.1f}")
    print(f"\nSimulation: 100,000 hands per threshold, 6-deck shoe, flat ${BET} bet")
    print("Strategy: Basic strategy (stand on soft 17 rules)")


if __name__ == "__main__":
    main()

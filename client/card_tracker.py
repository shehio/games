"""Live card tracking for interactive play using Hi-Lo counting."""

from shared.models import Card, card_from_dict
from simulations.card_counting import HiLoCounter


class CardTracker:
    """Tracks cards seen during interactive play to maintain a running count.

    Uses position-based deduplication to prevent double-counting when the
    same snapshot is observed multiple times.
    """

    def __init__(self, num_decks: int = 6) -> None:
        self._counter = HiLoCounter(num_decks=num_decks)
        self._seen: set[tuple] = set()

    def _observe_card(self, card: Card, position: tuple) -> None:
        if position not in self._seen:
            self._seen.add(position)
            self._counter.observe(card)

    def observe_snapshot(self, snap_dict: dict) -> None:
        """Extract visible cards from a snapshot and observe new ones."""
        # Dealer face-up card (index 0 is always visible)
        dealer_cards = snap_dict.get("dealer_cards", [])
        if dealer_cards:
            card = card_from_dict(dealer_cards[0])
            self._observe_card(card, ("dealer", 0))

        # If dealer is not hidden, observe all dealer cards
        if not snap_dict.get("dealer_hidden", True):
            for idx, cd in enumerate(dealer_cards):
                card = card_from_dict(cd)
                self._observe_card(card, ("dealer", idx))

        # Player cards
        for hand_idx, hand in enumerate(snap_dict.get("player_hands", [])):
            for card_idx, cd in enumerate(hand.get("cards", [])):
                card = card_from_dict(cd)
                self._observe_card(card, ("player", hand_idx, card_idx))

    def observe_result(self, result_dict: dict) -> None:
        """Extract all cards from a final result and observe new ones."""
        final_snap = result_dict.get("final_snapshot", {})
        # Observe all dealer cards (now fully revealed)
        for idx, cd in enumerate(final_snap.get("dealer_cards", [])):
            card = card_from_dict(cd)
            self._observe_card(card, ("dealer", idx))

        # Observe all player cards
        for hand_idx, hand in enumerate(final_snap.get("player_hands", [])):
            for card_idx, cd in enumerate(hand.get("cards", [])):
                card = card_from_dict(cd)
                self._observe_card(card, ("player", hand_idx, card_idx))

    def reset(self) -> None:
        """Reset counter and seen set for a new shoe."""
        self._counter.reset()
        self._seen.clear()

    @property
    def running_count(self) -> int:
        return self._counter.running_count

    @property
    def true_count(self) -> float:
        return self._counter.true_count

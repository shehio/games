"""Live card tracking for interactive play using Hi-Lo counting."""

from shared.models import Card, card_from_dict
from simulations.card_counting import HiLoCounter


class CardTracker:
    """Tracks cards seen during interactive play to maintain a running count.

    Uses position + card identity deduplication to prevent double-counting
    when the same snapshot is observed multiple times. Positions repeat from
    one hand to the next, so call start_hand() at the start of each hand to
    clear position tracking while keeping the running count.
    """

    def __init__(self, num_decks: int = 6) -> None:
        self._counter = HiLoCounter(num_decks=num_decks)
        self._seen: set[tuple] = set()
        self._num_hands: int = 1

    def start_hand(self) -> None:
        """Clear per-hand position tracking for a new hand; the count is kept."""
        self._seen.clear()
        self._num_hands = 1

    def _observe_card(self, card: Card, position: tuple) -> None:
        key = (*position, str(card))
        if key not in self._seen:
            self._seen.add(key)
            self._counter.observe(card)

    def _observe_player_hands(self, player_hands: list[dict]) -> None:
        # A split moves the original second card into the new hand's first
        # slot - mark it as seen so it isn't counted twice.
        if len(player_hands) > self._num_hands:
            for hand_idx in range(self._num_hands, len(player_hands)):
                cards = player_hands[hand_idx].get("cards", [])
                if cards:
                    card = card_from_dict(cards[0])
                    self._seen.add(("player", hand_idx, 0, str(card)))
            self._num_hands = len(player_hands)

        for hand_idx, hand in enumerate(player_hands):
            for card_idx, cd in enumerate(hand.get("cards", [])):
                card = card_from_dict(cd)
                self._observe_card(card, ("player", hand_idx, card_idx))

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
        self._observe_player_hands(snap_dict.get("player_hands", []))

    def observe_result(self, result_dict: dict) -> None:
        """Extract all cards from a final result and observe new ones."""
        final_snap = result_dict.get("final_snapshot", {})
        # Observe all dealer cards (now fully revealed)
        for idx, cd in enumerate(final_snap.get("dealer_cards", [])):
            card = card_from_dict(cd)
            self._observe_card(card, ("dealer", idx))

        # Observe all player cards
        self._observe_player_hands(final_snap.get("player_hands", []))

    def reset(self) -> None:
        """Reset counter and seen set for a new shoe."""
        self._counter.reset()
        self._seen.clear()
        self._num_hands = 1

    @property
    def running_count(self) -> int:
        return self._counter.running_count

    @property
    def true_count(self) -> float:
        return self._counter.true_count

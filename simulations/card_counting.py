"""Card counting systems for blackjack simulation.

Implements three well-known counting systems:
- Hi-Lo: Most popular balanced system
- Omega II: Multi-level balanced system
- KO (Knock-Out): Unbalanced system (uses running count only)
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from shared.models import Card, Rank


class CardCounter(ABC):
    """Abstract base class for card counting systems."""

    def __init__(self, num_decks: int = 6) -> None:
        self.num_decks = num_decks
        self._running_count = 0
        self._cards_seen = 0

    @abstractmethod
    def card_value(self, card: Card) -> int:
        """Return the counting value for a given card."""

    def observe(self, card: Card) -> None:
        """Observe a dealt card and update the running count."""
        self._running_count += self.card_value(card)
        self._cards_seen += 1

    def reset(self) -> None:
        """Reset counts for a new shoe."""
        self._running_count = 0
        self._cards_seen = 0

    @property
    def running_count(self) -> int:
        return self._running_count

    @property
    def true_count(self) -> float:
        """Running count divided by estimated decks remaining."""
        decks_remaining = max((self.num_decks * 52 - self._cards_seen) / 52, 0.5)
        return self._running_count / decks_remaining


class HiLoCounter(CardCounter):
    """Hi-Lo counting system (balanced).

    2-6 = +1, 7-9 = 0, 10-A = -1
    """

    _VALUES = {
        Rank.TWO: 1,
        Rank.THREE: 1,
        Rank.FOUR: 1,
        Rank.FIVE: 1,
        Rank.SIX: 1,
        Rank.SEVEN: 0,
        Rank.EIGHT: 0,
        Rank.NINE: 0,
        Rank.TEN: -1,
        Rank.JACK: -1,
        Rank.QUEEN: -1,
        Rank.KING: -1,
        Rank.ACE: -1,
    }

    def card_value(self, card: Card) -> int:
        return self._VALUES[card.rank]


class OmegaIICounter(CardCounter):
    """Omega II counting system (multi-level balanced).

    2,3,7 = +1; 4,5,6 = +2; 8,A = 0; 9 = -1; 10-K = -2
    """

    _VALUES = {
        Rank.TWO: 1,
        Rank.THREE: 1,
        Rank.FOUR: 2,
        Rank.FIVE: 2,
        Rank.SIX: 2,
        Rank.SEVEN: 1,
        Rank.EIGHT: 0,
        Rank.NINE: -1,
        Rank.TEN: -2,
        Rank.JACK: -2,
        Rank.QUEEN: -2,
        Rank.KING: -2,
        Rank.ACE: 0,
    }

    def card_value(self, card: Card) -> int:
        return self._VALUES[card.rank]


class KOCounter(CardCounter):
    """KO (Knock-Out) counting system (unbalanced).

    2-7 = +1, 8-9 = 0, 10-A = -1
    Uses running count only. Initial running count = 4 - 4 * num_decks.
    """

    _VALUES = {
        Rank.TWO: 1,
        Rank.THREE: 1,
        Rank.FOUR: 1,
        Rank.FIVE: 1,
        Rank.SIX: 1,
        Rank.SEVEN: 1,
        Rank.EIGHT: 0,
        Rank.NINE: 0,
        Rank.TEN: -1,
        Rank.JACK: -1,
        Rank.QUEEN: -1,
        Rank.KING: -1,
        Rank.ACE: -1,
    }

    def __init__(self, num_decks: int = 6) -> None:
        super().__init__(num_decks)
        self._initial_rc = 4 - 4 * num_decks
        self._running_count = self._initial_rc

    def card_value(self, card: Card) -> int:
        return self._VALUES[card.rank]

    def reset(self) -> None:
        super().reset()
        self._running_count = self._initial_rc

    @property
    def true_count(self) -> float:
        """KO is unbalanced — true count is just the running count."""
        return float(self._running_count)

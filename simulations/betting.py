"""Betting strategies for blackjack simulation.

Implements four strategies:
- Flat: Constant bet (baseline)
- Spread: Scales linearly with true count
- Kelly: Bets proportional to estimated edge
- Martingale: Doubles after loss, resets after win (cautionary example)
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class BettingStrategy(ABC):
    """Abstract base class for betting strategies."""

    def __init__(self, base_bet: int = 100, min_bet: int = 10) -> None:
        self.base_bet = base_bet
        self.min_bet = min_bet

    @abstractmethod
    def get_bet(self, true_count: float, previous_net: int) -> int:
        """Return the bet size given current true count and previous hand net."""

    def reset(self) -> None:
        """Reset strategy state for a new shoe."""


class FlatBetting(BettingStrategy):
    """Always bets the base amount."""

    def get_bet(self, true_count: float, previous_net: int) -> int:
        return self.base_bet


class SpreadBetting(BettingStrategy):
    """Scales bet linearly with true count, capped at max_spread * base_bet.

    Bets base_bet when true count <= 1, then increases by base_bet per
    true count point up to the cap.
    """

    def __init__(
        self, base_bet: int = 100, min_bet: int = 10, max_spread: int = 8
    ) -> None:
        super().__init__(base_bet, min_bet)
        self.max_spread = max_spread

    def get_bet(self, true_count: float, previous_net: int) -> int:
        if true_count <= 1:
            return self.base_bet
        spread = min(int(true_count), self.max_spread)
        return self.base_bet * spread


class KellyBetting(BettingStrategy):
    """Bets proportional to estimated edge using Kelly criterion.

    Edge estimate: ~0.5% per true count point above 0.
    Kelly fraction of bankroll = edge / odds (simplified to edge for even money).
    """

    def __init__(
        self, base_bet: int = 100, min_bet: int = 10, bankroll: int = 10_000
    ) -> None:
        super().__init__(base_bet, min_bet)
        self.bankroll = bankroll
        self._initial_bankroll = bankroll

    def get_bet(self, true_count: float, previous_net: int) -> int:
        self.bankroll += previous_net
        edge = 0.005 * true_count  # 0.5% per true count point
        if edge <= 0:
            return self.min_bet
        bet = int(self.bankroll * edge)
        return max(self.min_bet, min(bet, self.bankroll // 2))

    def reset(self) -> None:
        self.bankroll = self._initial_bankroll


class MartingaleBetting(BettingStrategy):
    """Doubles bet after a loss, resets to base after a win.

    Included as a cautionary example — does not overcome house edge.
    """

    def __init__(
        self, base_bet: int = 100, min_bet: int = 10, max_bet: int = 10_000
    ) -> None:
        super().__init__(base_bet, min_bet)
        self.max_bet = max_bet
        self._current_bet = base_bet

    def get_bet(self, true_count: float, previous_net: int) -> int:
        if previous_net < 0:
            self._current_bet = min(self._current_bet * 2, self.max_bet)
        else:
            self._current_bet = self.base_bet
        return self._current_bet

    def reset(self) -> None:
        self._current_bet = self.base_bet

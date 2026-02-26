"""Tests for card counting systems."""

import pytest

from shared.models import Card, Rank, Suit
from simulations.card_counting import (
    HiLoCounter,
    KOCounter,
    OmegaIICounter,
)


class TestHiLo:
    def test_low_cards_positive(self):
        counter = HiLoCounter()
        for rank in (Rank.TWO, Rank.THREE, Rank.FOUR, Rank.FIVE, Rank.SIX):
            assert counter.card_value(Card(rank, Suit.SPADES)) == 1

    def test_neutral_cards_zero(self):
        counter = HiLoCounter()
        for rank in (Rank.SEVEN, Rank.EIGHT, Rank.NINE):
            assert counter.card_value(Card(rank, Suit.SPADES)) == 0

    def test_high_cards_negative(self):
        counter = HiLoCounter()
        for rank in (Rank.TEN, Rank.JACK, Rank.QUEEN, Rank.KING, Rank.ACE):
            assert counter.card_value(Card(rank, Suit.SPADES)) == -1

    def test_running_count_accumulates(self):
        counter = HiLoCounter()
        counter.observe(Card(Rank.TWO, Suit.SPADES))   # +1
        counter.observe(Card(Rank.FIVE, Suit.HEARTS))   # +1
        counter.observe(Card(Rank.ACE, Suit.CLUBS))     # -1
        assert counter.running_count == 1

    def test_true_count_divides_by_decks_remaining(self):
        counter = HiLoCounter(num_decks=6)
        # Observe 5 low cards at start: RC = +5, ~6 decks remain
        for _ in range(5):
            counter.observe(Card(Rank.TWO, Suit.SPADES))
        # True count should be ~5/6 ≈ 0.83
        assert 0.7 < counter.true_count < 1.0

    def test_reset_clears_counts(self):
        counter = HiLoCounter()
        counter.observe(Card(Rank.TWO, Suit.SPADES))
        counter.reset()
        assert counter.running_count == 0
        assert counter.true_count == 0.0

    def test_balanced_full_shoe(self):
        """A balanced system sums to 0 over a complete shoe."""
        counter = HiLoCounter(num_decks=6)
        for _ in range(6):
            for suit in Suit:
                for rank in Rank:
                    counter.observe(Card(rank, suit))
        assert counter.running_count == 0


class TestOmegaII:
    def test_card_values(self):
        counter = OmegaIICounter()
        cases = [
            (Rank.TWO, 1), (Rank.THREE, 1), (Rank.SEVEN, 1),
            (Rank.FOUR, 2), (Rank.FIVE, 2), (Rank.SIX, 2),
            (Rank.EIGHT, 0), (Rank.ACE, 0),
            (Rank.NINE, -1),
            (Rank.TEN, -2), (Rank.JACK, -2), (Rank.QUEEN, -2), (Rank.KING, -2),
        ]
        for rank, expected in cases:
            assert counter.card_value(Card(rank, Suit.HEARTS)) == expected, (
                f"{rank} should be {expected}"
            )

    def test_running_count_accumulates(self):
        counter = OmegaIICounter()
        counter.observe(Card(Rank.FIVE, Suit.SPADES))   # +2
        counter.observe(Card(Rank.KING, Suit.HEARTS))    # -2
        counter.observe(Card(Rank.THREE, Suit.CLUBS))    # +1
        assert counter.running_count == 1

    def test_balanced_full_shoe(self):
        """Omega II is balanced — sums to 0 over a complete shoe."""
        counter = OmegaIICounter(num_decks=6)
        for _ in range(6):
            for suit in Suit:
                for rank in Rank:
                    counter.observe(Card(rank, suit))
        assert counter.running_count == 0


class TestKO:
    def test_card_values(self):
        counter = KOCounter()
        # 2-7 = +1
        for rank in (Rank.TWO, Rank.THREE, Rank.FOUR, Rank.FIVE, Rank.SIX, Rank.SEVEN):
            assert counter.card_value(Card(rank, Suit.SPADES)) == 1
        # 8-9 = 0
        for rank in (Rank.EIGHT, Rank.NINE):
            assert counter.card_value(Card(rank, Suit.SPADES)) == 0
        # 10-A = -1
        for rank in (Rank.TEN, Rank.JACK, Rank.QUEEN, Rank.KING, Rank.ACE):
            assert counter.card_value(Card(rank, Suit.SPADES)) == -1

    def test_initial_running_count(self):
        counter = KOCounter(num_decks=6)
        assert counter.running_count == 4 - 4 * 6  # -20

    def test_unbalanced_full_shoe(self):
        """KO is unbalanced — does NOT sum to 0 over a full shoe."""
        counter = KOCounter(num_decks=6)
        initial = counter.running_count
        for _ in range(6):
            for suit in Suit:
                for rank in Rank:
                    counter.observe(Card(rank, suit))
        # 6 decks × (6 low cards extra vs Hi-Lo: the 7) × 4 suits = +24
        # So final = initial + 24
        assert counter.running_count != 0
        assert counter.running_count == initial + 24

    def test_true_count_is_running_count(self):
        """KO uses running count directly as true count."""
        counter = KOCounter(num_decks=6)
        counter.observe(Card(Rank.TWO, Suit.SPADES))
        assert counter.true_count == float(counter.running_count)

    def test_reset_restores_initial_rc(self):
        counter = KOCounter(num_decks=6)
        initial = counter.running_count
        counter.observe(Card(Rank.TWO, Suit.SPADES))
        counter.reset()
        assert counter.running_count == initial

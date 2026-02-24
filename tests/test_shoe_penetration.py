"""Tests for the Monte Carlo shoe penetration simulation."""

import pytest

from shared.models import Card, Rank, Suit, best_total, is_blackjack
from simulations.shoe_penetration import (
    basic_strategy_decision,
    build_shoe,
    run_simulation,
    simulate_hand,
    BET,
    Action,
)


class TestBuildShoe:
    def test_shoe_has_312_cards(self):
        shoe = build_shoe(num_decks=6)
        assert len(shoe) == 312

    def test_single_deck_has_52_cards(self):
        shoe = build_shoe(num_decks=1)
        assert len(shoe) == 52

    def test_shoe_has_correct_rank_distribution(self):
        shoe = build_shoe(num_decks=6)
        # Each rank appears 4 times per deck * 6 decks = 24 times
        for rank in Rank:
            count = sum(1 for c in shoe if c.rank == rank)
            assert count == 24, f"{rank} count was {count}, expected 24"

    def test_shoe_has_correct_suit_distribution(self):
        shoe = build_shoe(num_decks=6)
        # Each suit appears 13 times per deck * 6 decks = 78 times
        for suit in Suit:
            count = sum(1 for c in shoe if c.suit == suit)
            assert count == 78, f"{suit} count was {count}, expected 78"


class TestBlackjackPayouts:
    # Pad shoes with filler cards so len >= 10 (simulate_hand guard)
    _filler = [Card(Rank.TWO, Suit.DIAMONDS)] * 10

    def test_player_blackjack_pays_3_to_2(self):
        shoe = [
            Card(Rank.ACE, Suit.SPADES),     # player 1
            Card(Rank.KING, Suit.HEARTS),    # player 2
            Card(Rank.SEVEN, Suit.HEARTS),   # dealer 1
            Card(Rank.SEVEN, Suit.CLUBS),    # dealer 2
        ] + self._filler
        outcome = simulate_hand(shoe)
        assert outcome.is_blackjack is True
        assert outcome.net == int(BET * 1.5)  # 3:2 payout

    def test_both_blackjack_is_push(self):
        shoe = [
            Card(Rank.ACE, Suit.SPADES),     # player 1
            Card(Rank.KING, Suit.HEARTS),    # player 2
            Card(Rank.ACE, Suit.HEARTS),     # dealer 1
            Card(Rank.QUEEN, Suit.CLUBS),    # dealer 2
        ] + self._filler
        outcome = simulate_hand(shoe)
        assert outcome.is_blackjack is True
        assert outcome.net == 0

    def test_dealer_blackjack_player_loses(self):
        shoe = [
            Card(Rank.SEVEN, Suit.SPADES),   # player 1
            Card(Rank.EIGHT, Suit.HEARTS),   # player 2
            Card(Rank.ACE, Suit.HEARTS),     # dealer 1
            Card(Rank.KING, Suit.CLUBS),     # dealer 2
        ] + self._filler
        outcome = simulate_hand(shoe)
        assert outcome.is_blackjack is False
        assert outcome.net == -BET


class TestBasicStrategy:
    def test_hard_16_vs_dealer_10_hits(self):
        cards = [Card(Rank.TEN, Suit.SPADES), Card(Rank.SIX, Suit.HEARTS)]
        dealer = Card(Rank.TEN, Suit.CLUBS)
        assert basic_strategy_decision(cards, dealer, False, True) == Action.HIT

    def test_hard_17_stands(self):
        cards = [Card(Rank.TEN, Suit.SPADES), Card(Rank.SEVEN, Suit.HEARTS)]
        dealer = Card(Rank.TEN, Suit.CLUBS)
        assert basic_strategy_decision(cards, dealer, False, True) == Action.STAND

    def test_11_doubles_vs_6(self):
        cards = [Card(Rank.SIX, Suit.SPADES), Card(Rank.FIVE, Suit.HEARTS)]
        dealer = Card(Rank.SIX, Suit.CLUBS)
        assert basic_strategy_decision(cards, dealer, False, True) == Action.DOUBLE

    def test_11_hits_when_cant_double(self):
        cards = [Card(Rank.SIX, Suit.SPADES), Card(Rank.FIVE, Suit.HEARTS)]
        dealer = Card(Rank.SIX, Suit.CLUBS)
        assert basic_strategy_decision(cards, dealer, False, False) == Action.HIT

    def test_pair_of_8s_splits(self):
        cards = [Card(Rank.EIGHT, Suit.SPADES), Card(Rank.EIGHT, Suit.HEARTS)]
        dealer = Card(Rank.SIX, Suit.CLUBS)
        assert basic_strategy_decision(cards, dealer, True, True) == Action.SPLIT

    def test_pair_of_10s_stands(self):
        cards = [Card(Rank.TEN, Suit.SPADES), Card(Rank.TEN, Suit.HEARTS)]
        dealer = Card(Rank.SIX, Suit.CLUBS)
        assert basic_strategy_decision(cards, dealer, True, True) == Action.STAND


class TestSimulation:
    def test_deterministic_with_seed(self):
        r1 = run_simulation(threshold=78, num_hands=1000, seed=123)
        r2 = run_simulation(threshold=78, num_hands=1000, seed=123)
        assert r1["house_edge_pct"] == r2["house_edge_pct"]
        assert r1["avg_hands_per_shoe"] == r2["avg_hands_per_shoe"]
        assert r1["blackjack_rate_pct"] == r2["blackjack_rate_pct"]

    def test_different_seeds_give_different_results(self):
        r1 = run_simulation(threshold=78, num_hands=10000, seed=1)
        r2 = run_simulation(threshold=78, num_hands=10000, seed=2)
        # Very unlikely to be exactly equal with different seeds
        assert r1["total_net"] != r2["total_net"]

    def test_house_edge_in_reasonable_range(self):
        result = run_simulation(threshold=78, num_hands=50000, seed=42)
        # Basic strategy house edge should be roughly 0-5%
        assert 0 <= result["house_edge_pct"] <= 5, (
            f"House edge {result['house_edge_pct']}% outside expected range"
        )

    def test_blackjack_rate_reasonable(self):
        result = run_simulation(threshold=78, num_hands=50000, seed=42)
        # Theoretical BJ rate ~4.75%, allow wide range
        assert 3 <= result["blackjack_rate_pct"] <= 7, (
            f"BJ rate {result['blackjack_rate_pct']}% outside expected range"
        )

    def test_hands_played_matches_requested(self):
        result = run_simulation(threshold=78, num_hands=1000, seed=42)
        assert result["hands_played"] == 1000

    def test_higher_threshold_means_fewer_hands_per_shoe(self):
        r_low = run_simulation(threshold=26, num_hands=10000, seed=42)
        r_high = run_simulation(threshold=234, num_hands=10000, seed=42)
        assert r_high["avg_hands_per_shoe"] < r_low["avg_hands_per_shoe"]

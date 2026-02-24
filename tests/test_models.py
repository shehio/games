"""Tests for shared/models.py — Card logic, best_total, is_blackjack, serialization."""

import pytest

from shared.models import (
    Card,
    HandResult,
    HandSnapshot,
    HandState,
    HandResultInfo,
    Rank,
    Suit,
    best_total,
    card_from_dict,
    card_to_dict,
    hand_state_from_dict,
    hand_state_to_dict,
    is_blackjack,
    result_info_from_dict,
    result_info_to_dict,
    snapshot_from_dict,
    snapshot_to_dict,
)


# ---------------------------------------------------------------------------
# Card.value()
# ---------------------------------------------------------------------------

class TestCardValue:
    def test_face_cards_return_10(self):
        for rank in (Rank.JACK, Rank.QUEEN, Rank.KING):
            card = Card(rank=rank, suit=Suit.SPADES)
            assert card.value() == [10]

    def test_ace_returns_1_and_11(self):
        card = Card(rank=Rank.ACE, suit=Suit.HEARTS)
        assert card.value() == [1, 11]

    def test_numeric_cards(self):
        expected = {
            Rank.TWO: [2], Rank.THREE: [3], Rank.FOUR: [4],
            Rank.FIVE: [5], Rank.SIX: [6], Rank.SEVEN: [7],
            Rank.EIGHT: [8], Rank.NINE: [9], Rank.TEN: [10],
        }
        for rank, val in expected.items():
            assert Card(rank=rank, suit=Suit.DIAMONDS).value() == val

    def test_card_str(self):
        card = Card(rank=Rank.ACE, suit=Suit.HEARTS)
        assert str(card) == "A♥"


# ---------------------------------------------------------------------------
# best_total()
# ---------------------------------------------------------------------------

class TestBestTotal:
    def test_simple_hand(self):
        cards = [Card(Rank.FIVE, Suit.HEARTS), Card(Rank.THREE, Suit.CLUBS)]
        assert best_total(cards) == 8

    def test_soft_ace(self):
        cards = [Card(Rank.ACE, Suit.HEARTS), Card(Rank.SIX, Suit.CLUBS)]
        assert best_total(cards) == 17  # A=11

    def test_hard_ace(self):
        cards = [
            Card(Rank.ACE, Suit.HEARTS),
            Card(Rank.NINE, Suit.CLUBS),
            Card(Rank.FIVE, Suit.DIAMONDS),
        ]
        assert best_total(cards) == 15  # A=1

    def test_multiple_aces(self):
        cards = [Card(Rank.ACE, Suit.HEARTS), Card(Rank.ACE, Suit.CLUBS)]
        assert best_total(cards) == 12  # one 11 + one 1

    def test_three_aces(self):
        cards = [
            Card(Rank.ACE, Suit.HEARTS),
            Card(Rank.ACE, Suit.CLUBS),
            Card(Rank.ACE, Suit.DIAMONDS),
        ]
        assert best_total(cards) == 13  # 11+1+1

    def test_bust(self):
        cards = [
            Card(Rank.TEN, Suit.HEARTS),
            Card(Rank.EIGHT, Suit.CLUBS),
            Card(Rank.FIVE, Suit.DIAMONDS),
        ]
        assert best_total(cards) == 23

    def test_blackjack_21(self):
        cards = [Card(Rank.ACE, Suit.HEARTS), Card(Rank.KING, Suit.SPADES)]
        assert best_total(cards) == 21

    def test_empty_hand(self):
        assert best_total([]) == 0


# ---------------------------------------------------------------------------
# is_blackjack()
# ---------------------------------------------------------------------------

class TestIsBlackjack:
    @pytest.mark.parametrize("face_rank", [Rank.TEN, Rank.JACK, Rank.QUEEN, Rank.KING])
    def test_natural_blackjack(self, face_rank):
        cards = [Card(Rank.ACE, Suit.HEARTS), Card(face_rank, Suit.SPADES)]
        assert is_blackjack(cards) is True

    def test_not_blackjack_three_cards(self):
        cards = [
            Card(Rank.SEVEN, Suit.HEARTS),
            Card(Rank.FOUR, Suit.CLUBS),
            Card(Rank.TEN, Suit.DIAMONDS),
        ]
        assert best_total(cards) == 21
        assert is_blackjack(cards) is False

    def test_not_blackjack_under_21(self):
        cards = [Card(Rank.TEN, Suit.HEARTS), Card(Rank.FIVE, Suit.CLUBS)]
        assert is_blackjack(cards) is False


# ---------------------------------------------------------------------------
# Serialization round-trips
# ---------------------------------------------------------------------------

class TestSerialization:
    def test_card_round_trip(self):
        card = Card(Rank.ACE, Suit.HEARTS)
        d = card_to_dict(card)
        assert d == {"rank": "A", "suit": "♥"}
        assert card_from_dict(d) == card

    def test_hand_state_round_trip(self):
        hs = HandState(
            cards=[Card(Rank.TEN, Suit.SPADES), Card(Rank.ACE, Suit.HEARTS)],
            bet=100,
            is_done=True,
            is_doubled=False,
            result=HandResult.BLACKJACK,
            payout=250,
        )
        d = hand_state_to_dict(hs)
        restored = hand_state_from_dict(d)
        assert restored.bet == hs.bet
        assert restored.is_done is True
        assert restored.result == HandResult.BLACKJACK
        assert restored.payout == 250
        assert len(restored.cards) == 2

    def test_hand_state_round_trip_no_result(self):
        hs = HandState(cards=[], bet=10)
        d = hand_state_to_dict(hs)
        restored = hand_state_from_dict(d)
        assert restored.result is None

    def test_snapshot_round_trip(self):
        snap = HandSnapshot(
            player_hands=[HandState(cards=[Card(Rank.FIVE, Suit.CLUBS)], bet=50)],
            dealer_cards=[Card(Rank.KING, Suit.DIAMONDS)],
            dealer_hidden=True,
            hand_over=False,
            message="Your turn",
        )
        d = snapshot_to_dict(snap)
        restored = snapshot_from_dict(d)
        assert restored.dealer_hidden is True
        assert restored.hand_over is False
        assert restored.message == "Your turn"
        assert len(restored.player_hands) == 1
        assert len(restored.dealer_cards) == 1

    def test_result_info_round_trip(self):
        ri = HandResultInfo(
            net_payout=150,
            result_description="Blackjack! You win!",
            final_snapshot=HandSnapshot(
                player_hands=[HandState(cards=[Card(Rank.ACE, Suit.HEARTS), Card(Rank.KING, Suit.SPADES)], bet=100, result=HandResult.BLACKJACK, payout=250, is_done=True)],
                dealer_cards=[Card(Rank.SEVEN, Suit.CLUBS), Card(Rank.NINE, Suit.DIAMONDS)],
                dealer_hidden=False,
                hand_over=True,
                message="Blackjack! You win!",
            ),
        )
        d = result_info_to_dict(ri)
        restored = result_info_from_dict(d)
        assert restored.net_payout == 150
        assert restored.result_description == "Blackjack! You win!"
        assert restored.final_snapshot.hand_over is True

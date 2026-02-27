"""Tests for client/card_tracker.py — CardTracker with Hi-Lo counting."""

from client.card_tracker import CardTracker
from shared.models import Card, HandState, Rank, Suit, card_to_dict, hand_state_to_dict


def make_snap(
    dealer_cards: list[Card],
    player_hands: list[list[Card]],
    dealer_hidden: bool = True,
) -> dict:
    """Build a snapshot dict for testing."""
    return {
        "dealer_cards": [card_to_dict(c) for c in dealer_cards],
        "player_hands": [
            hand_state_to_dict(HandState(cards=cards, bet=100)) for cards in player_hands
        ],
        "dealer_hidden": dealer_hidden,
        "hand_over": not dealer_hidden,
        "message": "",
        "insurance_offered": False,
        "insurance_result": "",
    }


def make_result(dealer_cards: list[Card], player_hands: list[list[Card]]) -> dict:
    """Build a result dict for testing."""
    return {
        "net_payout": 0,
        "result_description": "test",
        "final_snapshot": make_snap(dealer_cards, player_hands, dealer_hidden=False),
        "remaining_shoe": [],
    }


class TestCardTracker:
    def test_initial_snapshot_counts_visible_cards(self):
        """Dealer face-up + player cards should be counted."""
        tracker = CardTracker()
        # Dealer: Ace(face-up) + hidden. Player: 5, 6
        # Hi-Lo: Ace=-1, 5=+1, 6=+1 → RC=+1
        snap = make_snap(
            dealer_cards=[Card(Rank.ACE, Suit.HEARTS), Card(Rank.TEN, Suit.SPADES)],
            player_hands=[[Card(Rank.FIVE, Suit.CLUBS), Card(Rank.SIX, Suit.DIAMONDS)]],
            dealer_hidden=True,
        )
        tracker.observe_snapshot(snap)
        assert tracker.running_count == 1  # A(-1) + 5(+1) + 6(+1) = +1

    def test_same_snapshot_twice_no_double_count(self):
        """Observing the same snapshot again should not change the count."""
        tracker = CardTracker()
        snap = make_snap(
            dealer_cards=[Card(Rank.ACE, Suit.HEARTS), Card(Rank.TEN, Suit.SPADES)],
            player_hands=[[Card(Rank.FIVE, Suit.CLUBS), Card(Rank.SIX, Suit.DIAMONDS)]],
            dealer_hidden=True,
        )
        tracker.observe_snapshot(snap)
        rc1 = tracker.running_count
        tracker.observe_snapshot(snap)
        assert tracker.running_count == rc1

    def test_hit_adds_new_card(self):
        """After a hit, the new card should be counted."""
        tracker = CardTracker()
        # Initial: dealer 7(visible), player 10+8
        # Hi-Lo: 7(0) + 10(-1) + 8(0) = -1
        snap1 = make_snap(
            dealer_cards=[Card(Rank.SEVEN, Suit.HEARTS), Card(Rank.NINE, Suit.SPADES)],
            player_hands=[[Card(Rank.TEN, Suit.CLUBS), Card(Rank.EIGHT, Suit.DIAMONDS)]],
        )
        tracker.observe_snapshot(snap1)
        assert tracker.running_count == -1

        # After hit: player now has 10+8+3
        # Hi-Lo for 3: +1, so RC = -1 + 1 = 0
        snap2 = make_snap(
            dealer_cards=[Card(Rank.SEVEN, Suit.HEARTS), Card(Rank.NINE, Suit.SPADES)],
            player_hands=[
                [
                    Card(Rank.TEN, Suit.CLUBS),
                    Card(Rank.EIGHT, Suit.DIAMONDS),
                    Card(Rank.THREE, Suit.HEARTS),
                ]
            ],
        )
        tracker.observe_snapshot(snap2)
        assert tracker.running_count == 0

    def test_result_reveals_hidden_dealer_card(self):
        """Result should count the previously hidden dealer card."""
        tracker = CardTracker()
        # Initial: dealer K(visible), hidden. Player: 10+9
        snap = make_snap(
            dealer_cards=[Card(Rank.KING, Suit.HEARTS), Card(Rank.FIVE, Suit.SPADES)],
            player_hands=[[Card(Rank.TEN, Suit.CLUBS), Card(Rank.NINE, Suit.DIAMONDS)]],
            dealer_hidden=True,
        )
        tracker.observe_snapshot(snap)
        # K(-1) + 10(-1) + 9(0) = -2
        assert tracker.running_count == -2

        # Result reveals dealer's hidden 5
        result = make_result(
            dealer_cards=[Card(Rank.KING, Suit.HEARTS), Card(Rank.FIVE, Suit.SPADES)],
            player_hands=[[Card(Rank.TEN, Suit.CLUBS), Card(Rank.NINE, Suit.DIAMONDS)]],
        )
        tracker.observe_result(result)
        # 5(+1) now counted: -2 + 1 = -1
        assert tracker.running_count == -1

    def test_reset_clears_everything(self):
        tracker = CardTracker()
        snap = make_snap(
            dealer_cards=[Card(Rank.ACE, Suit.HEARTS), Card(Rank.TEN, Suit.SPADES)],
            player_hands=[[Card(Rank.FIVE, Suit.CLUBS), Card(Rank.SIX, Suit.CLUBS)]],
            dealer_hidden=True,
        )
        tracker.observe_snapshot(snap)
        # A(-1) + 5(+1) + 6(+1) = +1
        assert tracker.running_count != 0
        tracker.reset()
        assert tracker.running_count == 0
        assert len(tracker._seen) == 0

    def test_true_count_calculation(self):
        """True count = running count / decks remaining."""
        tracker = CardTracker(num_decks=6)
        # Observe 4 low cards: 2,3,4,5 → RC = +4
        snap = make_snap(
            dealer_cards=[Card(Rank.TWO, Suit.HEARTS), Card(Rank.THREE, Suit.SPADES)],
            player_hands=[[Card(Rank.FOUR, Suit.CLUBS), Card(Rank.FIVE, Suit.DIAMONDS)]],
            dealer_hidden=False,
        )
        tracker.observe_snapshot(snap)
        assert tracker.running_count == 4
        # 4 cards seen out of 312 → decks remaining ≈ (312-4)/52 ≈ 5.923
        # TC ≈ 4 / 5.923 ≈ 0.675
        tc = tracker.true_count
        assert 0.5 < tc < 0.8

"""Tests for betting strategies."""

from simulations.betting import (
    FlatBetting,
    KellyBetting,
    MartingaleBetting,
    SpreadBetting,
)


class TestFlat:
    def test_always_returns_base_bet(self):
        b = FlatBetting(base_bet=100)
        assert b.get_bet(true_count=0, previous_net=0) == 100
        assert b.get_bet(true_count=5, previous_net=-100) == 100
        assert b.get_bet(true_count=-3, previous_net=200) == 100

    def test_reset_is_noop(self):
        b = FlatBetting(base_bet=100)
        b.get_bet(true_count=0, previous_net=0)
        b.reset()
        assert b.get_bet(true_count=0, previous_net=0) == 100


class TestSpread:
    def test_base_bet_at_low_count(self):
        b = SpreadBetting(base_bet=100, max_spread=8)
        assert b.get_bet(true_count=0, previous_net=0) == 100
        assert b.get_bet(true_count=1, previous_net=0) == 100
        assert b.get_bet(true_count=-2, previous_net=0) == 100

    def test_scales_with_true_count(self):
        b = SpreadBetting(base_bet=100, max_spread=8)
        assert b.get_bet(true_count=2, previous_net=0) == 200
        assert b.get_bet(true_count=3, previous_net=0) == 300
        assert b.get_bet(true_count=5, previous_net=0) == 500

    def test_capped_at_max_spread(self):
        b = SpreadBetting(base_bet=100, max_spread=8)
        assert b.get_bet(true_count=10, previous_net=0) == 800
        assert b.get_bet(true_count=20, previous_net=0) == 800

    def test_reset_is_noop(self):
        b = SpreadBetting(base_bet=100)
        b.reset()
        assert b.get_bet(true_count=3, previous_net=0) == 300


class TestKelly:
    def test_min_bet_at_negative_count(self):
        b = KellyBetting(base_bet=100, min_bet=10, bankroll=10_000)
        assert b.get_bet(true_count=-2, previous_net=0) == 10
        assert b.get_bet(true_count=0, previous_net=0) == 10

    def test_scales_with_edge(self):
        b = KellyBetting(base_bet=100, min_bet=10, bankroll=10_000)
        bet = b.get_bet(true_count=4, previous_net=0)
        # edge = 0.005 * 4 = 0.02, bankroll = 10000, bet = 200
        assert bet == 200

    def test_tracks_bankroll(self):
        b = KellyBetting(base_bet=100, min_bet=10, bankroll=10_000)
        # Win 500: bankroll becomes 10500
        bet = b.get_bet(true_count=4, previous_net=500)
        # edge = 0.02, bankroll = 10500, bet = 210
        assert bet == 210

    def test_reset_restores_bankroll(self):
        b = KellyBetting(base_bet=100, min_bet=10, bankroll=10_000)
        b.get_bet(true_count=4, previous_net=-5000)
        b.reset()
        bet = b.get_bet(true_count=4, previous_net=0)
        assert bet == 200  # back to original bankroll


class TestMartingale:
    def test_base_bet_after_win(self):
        b = MartingaleBetting(base_bet=100)
        assert b.get_bet(true_count=0, previous_net=100) == 100

    def test_doubles_after_loss(self):
        b = MartingaleBetting(base_bet=100)
        assert b.get_bet(true_count=0, previous_net=-100) == 200
        assert b.get_bet(true_count=0, previous_net=-200) == 400

    def test_resets_after_win(self):
        b = MartingaleBetting(base_bet=100)
        b.get_bet(true_count=0, previous_net=-100)  # 200
        b.get_bet(true_count=0, previous_net=-200)  # 400
        assert b.get_bet(true_count=0, previous_net=400) == 100  # win resets

    def test_capped_at_max_bet(self):
        b = MartingaleBetting(base_bet=100, max_bet=500)
        b.get_bet(true_count=0, previous_net=-100)  # 200
        b.get_bet(true_count=0, previous_net=-200)  # 400
        assert b.get_bet(true_count=0, previous_net=-400) == 500  # capped

    def test_reset_restores_base(self):
        b = MartingaleBetting(base_bet=100)
        b.get_bet(true_count=0, previous_net=-100)  # 200
        b.reset()
        assert b.get_bet(true_count=0, previous_net=0) == 100

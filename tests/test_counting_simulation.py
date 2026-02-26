"""Tests for the counting simulation module."""

from simulations.betting import FlatBetting, SpreadBetting
from simulations.card_counting import HiLoCounter
from simulations.counting_simulation import (
    run_counting_simulation,
    sweep_strategies,
)


class TestRunCountingSimulation:
    def test_deterministic_with_seed(self):
        r1 = run_counting_simulation(
            counter=HiLoCounter(), bettor=FlatBetting(), num_hands=1000, seed=123
        )
        r2 = run_counting_simulation(
            counter=HiLoCounter(), bettor=FlatBetting(), num_hands=1000, seed=123
        )
        assert r1.house_edge_pct == r2.house_edge_pct
        assert r1.total_net == r2.total_net

    def test_flat_bet_house_edge_reasonable(self):
        """Flat bet with counting should have similar house edge to original sim."""
        result = run_counting_simulation(
            counter=HiLoCounter(),
            bettor=FlatBetting(base_bet=100),
            num_hands=50_000,
            seed=42,
        )
        # Basic strategy house edge should be roughly 0-5%
        assert -2 <= result.house_edge_pct <= 5

    def test_flat_bet_avg_is_base(self):
        result = run_counting_simulation(
            counter=HiLoCounter(),
            bettor=FlatBetting(base_bet=100),
            num_hands=1000,
            seed=42,
        )
        assert result.avg_bet == 100.0

    def test_spread_has_higher_avg_bet_than_flat(self):
        flat = run_counting_simulation(
            counter=HiLoCounter(),
            bettor=FlatBetting(base_bet=100),
            num_hands=10_000,
            seed=42,
        )
        spread = run_counting_simulation(
            counter=HiLoCounter(),
            bettor=SpreadBetting(base_bet=100),
            num_hands=10_000,
            seed=42,
        )
        assert spread.avg_bet > flat.avg_bet

    def test_hands_played_matches_requested(self):
        result = run_counting_simulation(
            counter=HiLoCounter(), bettor=FlatBetting(), num_hands=500, seed=42
        )
        assert result.hands_played == 500


class TestSweepStrategies:
    def test_returns_correct_count(self):
        results = sweep_strategies(
            thresholds=[78], num_hands=1000, seed=42
        )
        # 1 threshold × 3 counters × 4 bettors = 12
        assert len(results) == 12

    def test_all_results_have_expected_fields(self):
        results = sweep_strategies(
            thresholds=[78], num_hands=1000, seed=42
        )
        for r in results:
            assert r.threshold == 78
            assert r.hands_played == 1000
            assert isinstance(r.house_edge_pct, float)
            assert isinstance(r.avg_bet, float)

"""Tests for worker/activities/deck.py — shuffle_deck activity."""

import pytest
from temporalio.testing import ActivityEnvironment

from worker.activities.deck import shuffle_deck
from shared.constants import NUM_DECKS
from shared.models import Rank, Suit


@pytest.fixture
def activity_env():
    return ActivityEnvironment()


@pytest.mark.asyncio
async def test_shoe_has_312_cards(activity_env):
    result = await activity_env.run(shuffle_deck)
    assert len(result) == NUM_DECKS * 52  # 6 * 52 = 312


@pytest.mark.asyncio
async def test_contains_all_unique_cards_times_six(activity_env):
    result = await activity_env.run(shuffle_deck)

    # Count occurrences of each (rank, suit) pair
    counts: dict[tuple[str, str], int] = {}
    for card_dict in result:
        key = (card_dict["rank"], card_dict["suit"])
        counts[key] = counts.get(key, 0) + 1

    # Should have exactly 52 unique (rank, suit) combos, each appearing NUM_DECKS times
    assert len(counts) == 52
    for key, count in counts.items():
        assert count == NUM_DECKS, f"{key} appeared {count} times, expected {NUM_DECKS}"


@pytest.mark.asyncio
async def test_cards_have_rank_and_suit_keys(activity_env):
    result = await activity_env.run(shuffle_deck)
    for card_dict in result:
        assert "rank" in card_dict
        assert "suit" in card_dict


@pytest.mark.asyncio
async def test_rank_and_suit_values_are_valid(activity_env):
    result = await activity_env.run(shuffle_deck)
    valid_ranks = {r.value for r in Rank}
    valid_suits = {s.value for s in Suit}
    for card_dict in result:
        assert card_dict["rank"] in valid_ranks
        assert card_dict["suit"] in valid_suits


@pytest.mark.asyncio
async def test_two_shuffles_differ(activity_env):
    result1 = await activity_env.run(shuffle_deck)
    result2 = await activity_env.run(shuffle_deck)
    # Extremely unlikely (1/312! chance) that two shuffles match
    assert result1 != result2

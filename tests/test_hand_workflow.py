"""Tests for BlackjackHandWorkflow via Temporal test environment."""

import pytest
import pytest_asyncio
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from shared.constants import TASK_QUEUE
from shared.models import Card, Rank, Suit, card_to_dict
from worker.workflows.blackjack_hand import BlackjackHandWorkflow


def c(rank: Rank, suit: Suit = Suit.SPADES) -> dict:
    """Helper to create a card dict."""
    return card_to_dict(Card(rank, suit))


def make_input(
    bet: int,
    player: list[dict],
    dealer: list[dict],
    shoe: list[dict] | None = None,
) -> dict:
    """Build the hand workflow input dict."""
    if shoe is None:
        # Provide a default shoe with enough cards for dealer draws
        shoe = [
            c(Rank.TWO),
            c(Rank.THREE),
            c(Rank.FOUR),
            c(Rank.FIVE),
            c(Rank.SIX),
            c(Rank.SEVEN),
            c(Rank.EIGHT),
            c(Rank.NINE),
            c(Rank.TEN),
            c(Rank.TWO, Suit.HEARTS),
            c(Rank.THREE, Suit.HEARTS),
            c(Rank.FOUR, Suit.HEARTS),
            c(Rank.FIVE, Suit.HEARTS),
        ]
    return {
        "bet": bet,
        "player_cards": player,
        "dealer_cards": dealer,
        "shoe": shoe,
    }


@pytest_asyncio.fixture
async def env():
    async with await WorkflowEnvironment.start_time_skipping() as env:
        yield env


@pytest_asyncio.fixture
async def run_hand(env: WorkflowEnvironment):
    """Returns an async callable that starts the hand workflow and returns the result."""

    async def _run(input_data: dict, task_id: str = "test-hand"):
        async with Worker(
            env.client,
            task_queue=TASK_QUEUE,
            workflows=[BlackjackHandWorkflow],
        ):
            result = await env.client.execute_workflow(
                BlackjackHandWorkflow.run,
                input_data,
                id=task_id,
                task_queue=TASK_QUEUE,
            )
            return result

    return _run


# ---------------------------------------------------------------------------
# Natural blackjack scenarios (resolve immediately, no player actions needed)
# ---------------------------------------------------------------------------


class TestNaturalBlackjack:
    @pytest.mark.asyncio
    async def test_player_blackjack(self, run_hand):
        inp = make_input(
            bet=100,
            player=[c(Rank.ACE), c(Rank.KING)],
            dealer=[c(Rank.SEVEN), c(Rank.NINE)],
        )
        result = await run_hand(inp)
        assert result["net_payout"] == 150  # bet*1.5
        assert "Blackjack" in result["result_description"]

    @pytest.mark.asyncio
    async def test_dealer_blackjack(self, env: WorkflowEnvironment):
        inp = make_input(
            bet=100,
            player=[c(Rank.TEN), c(Rank.NINE)],
            dealer=[c(Rank.ACE), c(Rank.TEN)],
        )
        async with Worker(env.client, task_queue=TASK_QUEUE, workflows=[BlackjackHandWorkflow]):
            handle = await env.client.start_workflow(
                BlackjackHandWorkflow.run,
                inp,
                id="dealer-bj",
                task_queue=TASK_QUEUE,
            )
            # Dealer shows Ace → decline insurance
            await handle.execute_update(
                BlackjackHandWorkflow.insurance_action,
                {"take": False},
            )
            result = await handle.result()
        assert result["net_payout"] == -100
        assert "Dealer" in result["result_description"]

    @pytest.mark.asyncio
    async def test_both_blackjack_push(self, env: WorkflowEnvironment):
        inp = make_input(
            bet=100,
            player=[c(Rank.ACE), c(Rank.KING)],
            dealer=[c(Rank.ACE), c(Rank.QUEEN)],
        )
        async with Worker(env.client, task_queue=TASK_QUEUE, workflows=[BlackjackHandWorkflow]):
            handle = await env.client.start_workflow(
                BlackjackHandWorkflow.run,
                inp,
                id="both-bj-push",
                task_queue=TASK_QUEUE,
            )
            # Dealer shows Ace → decline insurance
            await handle.execute_update(
                BlackjackHandWorkflow.insurance_action,
                {"take": False},
            )
            result = await handle.result()
        assert result["net_payout"] == 0
        assert "Push" in result["result_description"]


# ---------------------------------------------------------------------------
# Player actions
# ---------------------------------------------------------------------------


class TestPlayerBust:
    @pytest.mark.asyncio
    async def test_player_busts(self, env: WorkflowEnvironment):
        # Player: 10+6=16, shoe has K so hit -> 26 bust
        inp = make_input(
            bet=100,
            player=[c(Rank.TEN), c(Rank.SIX)],
            dealer=[c(Rank.SEVEN), c(Rank.EIGHT)],
            shoe=[c(Rank.KING)],
        )
        async with Worker(env.client, task_queue=TASK_QUEUE, workflows=[BlackjackHandWorkflow]):
            handle = await env.client.start_workflow(
                BlackjackHandWorkflow.run,
                inp,
                id="bust-test",
                task_queue=TASK_QUEUE,
            )
            await handle.execute_update(
                BlackjackHandWorkflow.player_action,
                {"action": "hit", "hand_index": 0},
            )
            result = await handle.result()
        assert result["net_payout"] == -100
        assert "Bust" in result["result_description"]


class TestDealerBust:
    @pytest.mark.asyncio
    async def test_dealer_busts(self, env: WorkflowEnvironment):
        # Player: 10+8=18, stand.
        # Dealer: 6+5=11, draws 5->16, draws K->26 bust
        inp = make_input(
            bet=100,
            player=[c(Rank.TEN), c(Rank.EIGHT)],
            dealer=[c(Rank.SIX), c(Rank.FIVE)],
            shoe=[c(Rank.FIVE, Suit.HEARTS), c(Rank.KING)],
        )
        async with Worker(env.client, task_queue=TASK_QUEUE, workflows=[BlackjackHandWorkflow]):
            handle = await env.client.start_workflow(
                BlackjackHandWorkflow.run,
                inp,
                id="dealer-bust",
                task_queue=TASK_QUEUE,
            )
            await handle.execute_update(
                BlackjackHandWorkflow.player_action,
                {"action": "stand", "hand_index": 0},
            )
            result = await handle.result()
        assert result["net_payout"] == 100
        assert "bust" in result["result_description"].lower()


class TestPlayerWins:
    @pytest.mark.asyncio
    async def test_player_higher_total(self, env: WorkflowEnvironment):
        # Player: 10+9=19, stand. Dealer: 10+7=17, stands.
        inp = make_input(
            bet=100,
            player=[c(Rank.TEN), c(Rank.NINE)],
            dealer=[c(Rank.TEN, Suit.HEARTS), c(Rank.SEVEN)],
        )
        async with Worker(env.client, task_queue=TASK_QUEUE, workflows=[BlackjackHandWorkflow]):
            handle = await env.client.start_workflow(
                BlackjackHandWorkflow.run,
                inp,
                id="player-wins",
                task_queue=TASK_QUEUE,
            )
            await handle.execute_update(
                BlackjackHandWorkflow.player_action,
                {"action": "stand", "hand_index": 0},
            )
            result = await handle.result()
        assert result["net_payout"] == 100
        assert "Win" in result["result_description"]


class TestPlayerLoses:
    @pytest.mark.asyncio
    async def test_player_lower_total(self, env: WorkflowEnvironment):
        # Player: 10+7=17, stand. Dealer: 10+9=19, stands.
        inp = make_input(
            bet=100,
            player=[c(Rank.TEN), c(Rank.SEVEN)],
            dealer=[c(Rank.TEN, Suit.HEARTS), c(Rank.NINE)],
        )
        async with Worker(env.client, task_queue=TASK_QUEUE, workflows=[BlackjackHandWorkflow]):
            handle = await env.client.start_workflow(
                BlackjackHandWorkflow.run,
                inp,
                id="player-loses",
                task_queue=TASK_QUEUE,
            )
            await handle.execute_update(
                BlackjackHandWorkflow.player_action,
                {"action": "stand", "hand_index": 0},
            )
            result = await handle.result()
        assert result["net_payout"] == -100
        assert "Lose" in result["result_description"]


class TestPush:
    @pytest.mark.asyncio
    async def test_equal_totals(self, env: WorkflowEnvironment):
        # Player: 10+8=18, stand. Dealer: 10+8=18, stands.
        inp = make_input(
            bet=100,
            player=[c(Rank.TEN), c(Rank.EIGHT)],
            dealer=[c(Rank.TEN, Suit.HEARTS), c(Rank.EIGHT, Suit.HEARTS)],
        )
        async with Worker(env.client, task_queue=TASK_QUEUE, workflows=[BlackjackHandWorkflow]):
            handle = await env.client.start_workflow(
                BlackjackHandWorkflow.run,
                inp,
                id="push-test",
                task_queue=TASK_QUEUE,
            )
            await handle.execute_update(
                BlackjackHandWorkflow.player_action,
                {"action": "stand", "hand_index": 0},
            )
            result = await handle.result()
        assert result["net_payout"] == 0
        assert "Push" in result["result_description"]


class TestDoubleDown:
    @pytest.mark.asyncio
    async def test_double_down(self, env: WorkflowEnvironment):
        # Player: 5+6=11, double. Shoe has 10 -> 21. Dealer: 10+7=17, stands.
        inp = make_input(
            bet=100,
            player=[c(Rank.FIVE), c(Rank.SIX)],
            dealer=[c(Rank.TEN, Suit.HEARTS), c(Rank.SEVEN)],
            shoe=[c(Rank.TEN)],
        )
        async with Worker(env.client, task_queue=TASK_QUEUE, workflows=[BlackjackHandWorkflow]):
            handle = await env.client.start_workflow(
                BlackjackHandWorkflow.run,
                inp,
                id="double-test",
                task_queue=TASK_QUEUE,
            )
            await handle.execute_update(
                BlackjackHandWorkflow.player_action,
                {"action": "double", "hand_index": 0},
            )
            result = await handle.result()
        # Doubled bet = 200, won -> payout 400, net = 400 - 200 = 200
        assert result["net_payout"] == 200
        assert "Win" in result["result_description"]


class TestSplit:
    @pytest.mark.asyncio
    async def test_split(self, env: WorkflowEnvironment):
        # Player: 8+8, split. Shoe: [K, Q, ...]. Hand1: 8+K=18, Hand2: 8+Q=18.
        # Dealer: 10+6=16, shoe after split: [5] -> 21. Dealer wins both.
        inp = make_input(
            bet=100,
            player=[c(Rank.EIGHT), c(Rank.EIGHT, Suit.HEARTS)],
            dealer=[c(Rank.TEN, Suit.HEARTS), c(Rank.SIX)],
            shoe=[c(Rank.KING), c(Rank.QUEEN), c(Rank.FIVE, Suit.HEARTS)],
        )
        async with Worker(env.client, task_queue=TASK_QUEUE, workflows=[BlackjackHandWorkflow]):
            handle = await env.client.start_workflow(
                BlackjackHandWorkflow.run,
                inp,
                id="split-test",
                task_queue=TASK_QUEUE,
            )
            # Split
            await handle.execute_update(
                BlackjackHandWorkflow.player_action,
                {"action": "split", "hand_index": 0},
            )
            # Stand on first hand (8+K=18)
            await handle.execute_update(
                BlackjackHandWorkflow.player_action,
                {"action": "stand", "hand_index": 0},
            )
            # Stand on second hand (8+Q=18)
            await handle.execute_update(
                BlackjackHandWorkflow.player_action,
                {"action": "stand", "hand_index": 1},
            )
            result = await handle.result()
        # Dealer: 10+6+5=21, both player hands lose (18 vs 21)
        assert result["net_payout"] == -200  # lost both 100 bets


class TestDealerStandsOn17:
    @pytest.mark.asyncio
    async def test_dealer_stands_on_17(self, env: WorkflowEnvironment):
        # Player: 10+8=18, stand. Dealer: 10+7=17, should NOT draw more.
        inp = make_input(
            bet=100,
            player=[c(Rank.TEN), c(Rank.EIGHT)],
            dealer=[c(Rank.TEN, Suit.HEARTS), c(Rank.SEVEN)],
            shoe=[c(Rank.ACE)],  # Dealer should not draw this
        )
        async with Worker(env.client, task_queue=TASK_QUEUE, workflows=[BlackjackHandWorkflow]):
            handle = await env.client.start_workflow(
                BlackjackHandWorkflow.run,
                inp,
                id="dealer-17",
                task_queue=TASK_QUEUE,
            )
            await handle.execute_update(
                BlackjackHandWorkflow.player_action,
                {"action": "stand", "hand_index": 0},
            )
            result = await handle.result()
        # Dealer stayed at 17, player wins with 18
        assert result["net_payout"] == 100
        # Shoe should still have the ace (dealer didn't draw)
        assert len(result["remaining_shoe"]) == 1


# ---------------------------------------------------------------------------
# Insurance scenarios
# ---------------------------------------------------------------------------


class TestInsurance:
    @pytest.mark.asyncio
    async def test_insurance_offered_when_dealer_shows_ace(self, env: WorkflowEnvironment):
        """Insurance should be offered when dealer's face-up card is Ace."""
        inp = make_input(
            bet=100,
            player=[c(Rank.TEN), c(Rank.NINE)],
            dealer=[c(Rank.ACE), c(Rank.SEVEN)],
        )
        async with Worker(env.client, task_queue=TASK_QUEUE, workflows=[BlackjackHandWorkflow]):
            handle = await env.client.start_workflow(
                BlackjackHandWorkflow.run,
                inp,
                id="ins-offered",
                task_queue=TASK_QUEUE,
            )
            offered = await handle.query(BlackjackHandWorkflow.is_insurance_offered)
            assert offered is True
            # Decline insurance and finish the hand
            await handle.execute_update(
                BlackjackHandWorkflow.insurance_action,
                {"take": False},
            )
            await handle.execute_update(
                BlackjackHandWorkflow.player_action,
                {"action": "stand", "hand_index": 0},
            )
            await handle.result()

    @pytest.mark.asyncio
    async def test_insurance_not_offered_when_dealer_shows_non_ace(self, env: WorkflowEnvironment):
        """Insurance should NOT be offered when dealer shows a non-Ace."""
        inp = make_input(
            bet=100,
            player=[c(Rank.TEN), c(Rank.NINE)],
            dealer=[c(Rank.TEN, Suit.HEARTS), c(Rank.SEVEN)],
        )
        async with Worker(env.client, task_queue=TASK_QUEUE, workflows=[BlackjackHandWorkflow]):
            handle = await env.client.start_workflow(
                BlackjackHandWorkflow.run,
                inp,
                id="ins-not-offered",
                task_queue=TASK_QUEUE,
            )
            offered = await handle.query(BlackjackHandWorkflow.is_insurance_offered)
            assert offered is False
            await handle.execute_update(
                BlackjackHandWorkflow.player_action,
                {"action": "stand", "hand_index": 0},
            )
            result = await handle.result()
        assert result.get("insurance_bet", 0) == 0

    @pytest.mark.asyncio
    async def test_insurance_taken_dealer_has_bj_breakeven(self, env: WorkflowEnvironment):
        """Take insurance, dealer has BJ → insurance pays 2:1, hand loses → net ~0."""
        inp = make_input(
            bet=100,
            player=[c(Rank.TEN), c(Rank.NINE)],
            dealer=[c(Rank.ACE), c(Rank.TEN)],
            shoe=[c(Rank.TWO)],
        )
        inp["available_bankroll"] = 500
        async with Worker(env.client, task_queue=TASK_QUEUE, workflows=[BlackjackHandWorkflow]):
            handle = await env.client.start_workflow(
                BlackjackHandWorkflow.run,
                inp,
                id="ins-taken-dbj",
                task_queue=TASK_QUEUE,
            )
            await handle.execute_update(
                BlackjackHandWorkflow.insurance_action,
                {"take": True, "amount": 50},
            )
            result = await handle.result()
        # Hand loses: -100. Insurance wins: 50*3 - 50 = +100. Net = 0.
        assert result["net_payout"] == 0
        assert result["insurance_bet"] == 50
        assert result["insurance_payout"] == 150

    @pytest.mark.asyncio
    async def test_insurance_taken_dealer_no_bj_play_continues(self, env: WorkflowEnvironment):
        """Take insurance, dealer has no BJ → insurance lost, normal play continues."""
        inp = make_input(
            bet=100,
            player=[c(Rank.TEN), c(Rank.NINE)],
            dealer=[c(Rank.ACE), c(Rank.SEVEN)],
            shoe=[c(Rank.TWO)],
        )
        inp["available_bankroll"] = 500
        async with Worker(env.client, task_queue=TASK_QUEUE, workflows=[BlackjackHandWorkflow]):
            handle = await env.client.start_workflow(
                BlackjackHandWorkflow.run,
                inp,
                id="ins-taken-no-dbj",
                task_queue=TASK_QUEUE,
            )
            await handle.execute_update(
                BlackjackHandWorkflow.insurance_action,
                {"take": True, "amount": 50},
            )
            # Player stands with 19, dealer has A+7=18 (soft 18, stands at 18)
            await handle.execute_update(
                BlackjackHandWorkflow.player_action,
                {"action": "stand", "hand_index": 0},
            )
            result = await handle.result()
        # Hand wins: +100. Insurance lost: -50. Net = +50.
        assert result["net_payout"] == 50
        assert result["insurance_bet"] == 50
        assert result["insurance_payout"] == 0

    @pytest.mark.asyncio
    async def test_insurance_declined_dealer_has_bj(self, env: WorkflowEnvironment):
        """Decline insurance, dealer has BJ → full loss."""
        inp = make_input(
            bet=100,
            player=[c(Rank.TEN), c(Rank.NINE)],
            dealer=[c(Rank.ACE), c(Rank.TEN)],
        )
        async with Worker(env.client, task_queue=TASK_QUEUE, workflows=[BlackjackHandWorkflow]):
            handle = await env.client.start_workflow(
                BlackjackHandWorkflow.run,
                inp,
                id="ins-declined-dbj",
                task_queue=TASK_QUEUE,
            )
            await handle.execute_update(
                BlackjackHandWorkflow.insurance_action,
                {"take": False},
            )
            result = await handle.result()
        assert result["net_payout"] == -100
        assert result["insurance_bet"] == 0

    @pytest.mark.asyncio
    async def test_even_money_player_bj_takes_insurance(self, env: WorkflowEnvironment):
        """Player BJ + takes insurance → even money, guaranteed 1:1 payout."""
        inp = make_input(
            bet=100,
            player=[c(Rank.ACE), c(Rank.KING)],
            dealer=[c(Rank.ACE), c(Rank.TEN)],
        )
        inp["available_bankroll"] = 500
        async with Worker(env.client, task_queue=TASK_QUEUE, workflows=[BlackjackHandWorkflow]):
            handle = await env.client.start_workflow(
                BlackjackHandWorkflow.run,
                inp,
                id="even-money",
                task_queue=TASK_QUEUE,
            )
            await handle.execute_update(
                BlackjackHandWorkflow.insurance_action,
                {"take": True, "amount": 50},
            )
            result = await handle.result()
        # Even money: net = bet = 100 (hand pays 2x bet = 200, - bet = +100,
        # insurance refunded so insurance_net = 0)
        assert result["net_payout"] == 100
        assert "Even Money" in result["result_description"]

    @pytest.mark.asyncio
    async def test_player_bj_declines_insurance_dealer_bj_push(self, env: WorkflowEnvironment):
        """Player BJ + declines insurance + dealer BJ → push."""
        inp = make_input(
            bet=100,
            player=[c(Rank.ACE), c(Rank.KING)],
            dealer=[c(Rank.ACE), c(Rank.QUEEN)],
        )
        async with Worker(env.client, task_queue=TASK_QUEUE, workflows=[BlackjackHandWorkflow]):
            handle = await env.client.start_workflow(
                BlackjackHandWorkflow.run,
                inp,
                id="bj-decline-push",
                task_queue=TASK_QUEUE,
            )
            await handle.execute_update(
                BlackjackHandWorkflow.insurance_action,
                {"take": False},
            )
            result = await handle.result()
        assert result["net_payout"] == 0
        assert "Push" in result["result_description"]

    @pytest.mark.asyncio
    async def test_player_bj_declines_insurance_dealer_no_bj(self, env: WorkflowEnvironment):
        """Player BJ + declines insurance + dealer no BJ → 3:2 payout."""
        inp = make_input(
            bet=100,
            player=[c(Rank.ACE), c(Rank.KING)],
            dealer=[c(Rank.ACE), c(Rank.SEVEN)],
        )
        async with Worker(env.client, task_queue=TASK_QUEUE, workflows=[BlackjackHandWorkflow]):
            handle = await env.client.start_workflow(
                BlackjackHandWorkflow.run,
                inp,
                id="bj-decline-no-dbj",
                task_queue=TASK_QUEUE,
            )
            await handle.execute_update(
                BlackjackHandWorkflow.insurance_action,
                {"take": False},
            )
            result = await handle.result()
        # Player BJ pays 3:2 = 150
        assert result["net_payout"] == 150
        assert "Blackjack" in result["result_description"]

    @pytest.mark.asyncio
    async def test_insurance_bet_validation(self, env: WorkflowEnvironment):
        """Insurance amount > bet//2 should be rejected."""
        inp = make_input(
            bet=100,
            player=[c(Rank.TEN), c(Rank.NINE)],
            dealer=[c(Rank.ACE), c(Rank.SEVEN)],
        )
        inp["available_bankroll"] = 500
        async with Worker(env.client, task_queue=TASK_QUEUE, workflows=[BlackjackHandWorkflow]):
            handle = await env.client.start_workflow(
                BlackjackHandWorkflow.run,
                inp,
                id="ins-validation",
                task_queue=TASK_QUEUE,
            )
            # Try to bet more than half the original bet
            snap = await handle.execute_update(
                BlackjackHandWorkflow.insurance_action,
                {"take": True, "amount": 60},  # max is 50 (100//2)
            )
            # Should still be waiting for valid insurance
            assert snap.get("insurance_offered") is True
            offered = await handle.query(BlackjackHandWorkflow.is_insurance_offered)
            assert offered is True
            # Now send valid amount
            await handle.execute_update(
                BlackjackHandWorkflow.insurance_action,
                {"take": True, "amount": 50},
            )
            await handle.execute_update(
                BlackjackHandWorkflow.player_action,
                {"action": "stand", "hand_index": 0},
            )
            result = await handle.result()
        assert result["insurance_bet"] == 50

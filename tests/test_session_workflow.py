"""Tests for BlackjackSessionWorkflow via Temporal test environment."""

import asyncio

import pytest
import pytest_asyncio
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from shared.constants import MIN_BET, STARTING_BANKROLL, TASK_QUEUE
from worker.activities.deck import shuffle_deck
from worker.workflows.blackjack_hand import BlackjackHandWorkflow
from worker.workflows.blackjack_session import BlackjackSessionWorkflow


@pytest_asyncio.fixture
async def env():
    async with await WorkflowEnvironment.start_time_skipping() as env:
        yield env


@pytest.fixture
def worker_args():
    return dict(
        task_queue=TASK_QUEUE,
        workflows=[BlackjackSessionWorkflow, BlackjackHandWorkflow],
        activities=[shuffle_deck],
    )


async def complete_hand(client, session_handle, timeout: float = 10.0):
    """Wait for the child hand workflow, send 'stand' if needed, and wait for it to resolve."""
    # Wait for active_hand_workflow_id to be set
    hand_wf_id = None
    for _ in range(100):
        state = await session_handle.query(BlackjackSessionWorkflow.get_session_state)
        if state["waiting_for_bet"] or state["session_over"]:
            return state  # Hand already resolved (e.g., blackjack)
        wf_id = state.get("active_hand_workflow_id")
        if wf_id and wf_id != "pending":
            hand_wf_id = wf_id
            break
        await asyncio.sleep(0.05)

    if hand_wf_id is None:
        # Hand resolved before we could get ID
        state = await session_handle.query(BlackjackSessionWorkflow.get_session_state)
        return state

    hand_handle = client.get_workflow_handle(hand_wf_id)

    # Send stand to complete the hand (if it hasn't already resolved)
    for _ in range(50):
        state = await session_handle.query(BlackjackSessionWorkflow.get_session_state)
        if state["waiting_for_bet"] or state["session_over"]:
            return state
        try:
            actions = await hand_handle.query(BlackjackHandWorkflow.get_available_actions)
            if actions:
                await hand_handle.execute_update(
                    BlackjackHandWorkflow.player_action,
                    {"action": "stand", "hand_index": 0},
                )
        except Exception:
            pass  # Hand may have already completed
        await asyncio.sleep(0.05)

    # Final state
    state = await session_handle.query(BlackjackSessionWorkflow.get_session_state)
    return state


# ---------------------------------------------------------------------------
# place_bet validations
# ---------------------------------------------------------------------------


class TestPlaceBet:
    @pytest.mark.asyncio
    async def test_valid_bet_accepted(self, env: WorkflowEnvironment, worker_args):
        async with Worker(env.client, **worker_args):
            handle = await env.client.start_workflow(
                BlackjackSessionWorkflow.run,
                id="bet-ok",
                task_queue=TASK_QUEUE,
            )
            result = await handle.execute_update(
                BlackjackSessionWorkflow.place_bet,
                {"amount": 100},
            )
            assert result["ok"] is True
            assert result["error"] is None

            state = await handle.query(BlackjackSessionWorkflow.get_session_state)
            assert state["total_wagered"] == 100

            # Complete the hand so session can proceed
            await complete_hand(env.client, handle)

            await handle.signal(BlackjackSessionWorkflow.cash_out)
            await handle.result()

    @pytest.mark.asyncio
    async def test_bet_exceeds_bankroll(self, env: WorkflowEnvironment, worker_args):
        async with Worker(env.client, **worker_args):
            handle = await env.client.start_workflow(
                BlackjackSessionWorkflow.run,
                id="bet-over",
                task_queue=TASK_QUEUE,
            )
            result = await handle.execute_update(
                BlackjackSessionWorkflow.place_bet,
                {"amount": STARTING_BANKROLL + 1},
            )
            assert result["ok"] is False
            assert "Not enough" in result["error"]

            await handle.signal(BlackjackSessionWorkflow.cash_out)
            await handle.result()

    @pytest.mark.asyncio
    async def test_bet_below_minimum(self, env: WorkflowEnvironment, worker_args):
        async with Worker(env.client, **worker_args):
            handle = await env.client.start_workflow(
                BlackjackSessionWorkflow.run,
                id="bet-low",
                task_queue=TASK_QUEUE,
            )
            result = await handle.execute_update(
                BlackjackSessionWorkflow.place_bet,
                {"amount": MIN_BET - 1},
            )
            assert result["ok"] is False
            assert "Minimum" in result["error"]

            await handle.signal(BlackjackSessionWorkflow.cash_out)
            await handle.result()

    @pytest.mark.asyncio
    async def test_bet_rejected_when_hand_in_progress(self, env: WorkflowEnvironment, worker_args):
        async with Worker(env.client, **worker_args):
            handle = await env.client.start_workflow(
                BlackjackSessionWorkflow.run,
                id="bet-dup",
                task_queue=TASK_QUEUE,
            )
            r1 = await handle.execute_update(
                BlackjackSessionWorkflow.place_bet,
                {"amount": 100},
            )
            assert r1["ok"] is True

            # Immediately try a second bet — should be rejected (hand in progress)
            r2 = await handle.execute_update(
                BlackjackSessionWorkflow.place_bet,
                {"amount": 100},
            )
            assert r2["ok"] is False
            assert "progress" in r2["error"].lower() or "already" in r2["error"].lower()

            # Complete the hand and clean up
            await complete_hand(env.client, handle)
            await handle.signal(BlackjackSessionWorkflow.cash_out)
            await handle.result()


# ---------------------------------------------------------------------------
# cash_out
# ---------------------------------------------------------------------------


class TestCashOut:
    @pytest.mark.asyncio
    async def test_cash_out_ends_session(self, env: WorkflowEnvironment, worker_args):
        async with Worker(env.client, **worker_args):
            handle = await env.client.start_workflow(
                BlackjackSessionWorkflow.run,
                id="cashout",
                task_queue=TASK_QUEUE,
            )
            await handle.signal(BlackjackSessionWorkflow.cash_out)
            summary = await handle.result()
            assert "final_bankroll" in summary
            assert summary["hands_played"] == 0
            assert summary["final_bankroll"] == STARTING_BANKROLL


# ---------------------------------------------------------------------------
# Stats tracking
# ---------------------------------------------------------------------------


class TestStatsTracking:
    @pytest.mark.asyncio
    async def test_stats_after_one_hand(self, env: WorkflowEnvironment, worker_args):
        async with Worker(env.client, **worker_args):
            handle = await env.client.start_workflow(
                BlackjackSessionWorkflow.run,
                id="stats",
                task_queue=TASK_QUEUE,
            )
            await handle.execute_update(
                BlackjackSessionWorkflow.place_bet,
                {"amount": 50},
            )
            await complete_hand(env.client, handle)

            state = await handle.query(BlackjackSessionWorkflow.get_session_state)
            assert state["hands_played"] == 1
            assert state["total_wagered"] == 50
            assert state["hands_won"] + state["hands_lost"] + state["hands_pushed"] == 1

            await handle.signal(BlackjackSessionWorkflow.cash_out)
            summary = await handle.result()
            assert summary["hands_played"] == 1
            assert summary["starting_bankroll"] == STARTING_BANKROLL

    @pytest.mark.asyncio
    async def test_bankroll_high_tracked(self, env: WorkflowEnvironment, worker_args):
        async with Worker(env.client, **worker_args):
            handle = await env.client.start_workflow(
                BlackjackSessionWorkflow.run,
                id="high",
                task_queue=TASK_QUEUE,
            )

            for _i in range(3):
                state = await handle.query(BlackjackSessionWorkflow.get_session_state)
                if state["session_over"]:
                    break
                if state["waiting_for_bet"] and state["bankroll"] >= MIN_BET:
                    await handle.execute_update(
                        BlackjackSessionWorkflow.place_bet,
                        {"amount": MIN_BET},
                    )
                    await complete_hand(env.client, handle)

            await handle.signal(BlackjackSessionWorkflow.cash_out)
            summary = await handle.result()
            assert summary["bankroll_high"] >= STARTING_BANKROLL


# ---------------------------------------------------------------------------
# Bankruptcy
# ---------------------------------------------------------------------------


class TestBankruptcy:
    @pytest.mark.asyncio
    async def test_session_ends_on_bankruptcy(self, env: WorkflowEnvironment, worker_args):
        """Keep betting max until bankroll < MIN_BET. Session should auto-end."""
        async with Worker(env.client, **worker_args):
            handle = await env.client.start_workflow(
                BlackjackSessionWorkflow.run,
                id="bankrupt",
                task_queue=TASK_QUEUE,
            )

            for _ in range(200):  # Safety limit
                state = await handle.query(BlackjackSessionWorkflow.get_session_state)
                if state["session_over"]:
                    break
                if state["waiting_for_bet"]:
                    bankroll = state["bankroll"]
                    if bankroll < MIN_BET:
                        break
                    bet = min(bankroll, 500)
                    r = await handle.execute_update(
                        BlackjackSessionWorkflow.place_bet,
                        {"amount": bet},
                    )
                    if not r["ok"]:
                        break
                    await complete_hand(env.client, handle)

            summary = await handle.result()
            assert summary["final_bankroll"] < MIN_BET or summary["hands_played"] > 0

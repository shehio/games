"""Blackjack CLI client - connects to Temporal and plays interactively."""

import asyncio
import os
import uuid

from temporalio.client import Client

from shared.constants import MIN_BET, STARTING_BANKROLL, TASK_QUEUE
from shared.models import Action
from client.ui.renderer import (
    LINE,
    render_error,
    render_result,
    render_session_summary,
    render_snapshot,
    render_stats_bar,
    render_welcome,
)
from client.ui.prompts import confirm_cash_out, prompt_action, prompt_bet
from worker.workflows.blackjack_session import BlackjackSessionWorkflow
from worker.workflows.blackjack_hand import BlackjackHandWorkflow


async def wait_for_hand(handle, timeout: float = 10.0) -> str | None:
    """Poll session until active_hand_workflow_id is set, or hand is done."""
    elapsed = 0.0
    while elapsed < timeout:
        state = await handle.query(BlackjackSessionWorkflow.get_session_state)
        wf_id = state["active_hand_workflow_id"]
        if wf_id and wf_id != "pending":
            return wf_id
        if state["waiting_for_bet"]:
            return None
        await asyncio.sleep(0.2)
        elapsed += 0.2
    return None


async def wait_for_bet_ready(handle, timeout: float = 10.0) -> dict:
    """Poll session until it's ready for next bet."""
    elapsed = 0.0
    while elapsed < timeout:
        state = await handle.query(BlackjackSessionWorkflow.get_session_state)
        if state["waiting_for_bet"] or state["session_over"]:
            return state
        await asyncio.sleep(0.2)
        elapsed += 0.2
    return await handle.query(BlackjackSessionWorkflow.get_session_state)


async def main():
    temporal_host = os.environ.get("TEMPORAL_HOST", "temporal:7233")
    print(f"Connecting to Temporal at {temporal_host}...")

    client = await Client.connect(temporal_host)
    print("Connected!")

    render_welcome()

    player_name = input("  Enter your name: ").strip()
    if not player_name:
        player_name = "Player"
    print()

    short_id = uuid.uuid4().hex[:4]
    session_id = f"casino-{player_name.lower()}-{short_id}"

    handle = await client.start_workflow(
        BlackjackSessionWorkflow.run,
        id=session_id,
        task_queue=TASK_QUEUE,
    )

    print(f"  Welcome, {player_name}! Starting bankroll: ${STARTING_BANKROLL}")
    print(f"  Session: {session_id}")
    print()

    try:
        while True:
            state = await handle.query(BlackjackSessionWorkflow.get_session_state)

            if state["session_over"]:
                print("  Session over!")
                break

            if state["bankroll"] < MIN_BET:
                print("  You're broke! Game over.")
                break

            render_stats_bar(state)

            bet = prompt_bet(state["bankroll"], MIN_BET)
            if bet is None:
                if confirm_cash_out():
                    await handle.signal(BlackjackSessionWorkflow.cash_out)
                    break
                continue

            # Place bet
            bet_result = await handle.execute_update(
                BlackjackSessionWorkflow.place_bet,
                {"amount": bet},
            )

            if not bet_result["ok"]:
                render_error(bet_result["error"])
                continue

            # Wait for child hand workflow to start (or finish instantly)
            hand_wf_id = await wait_for_hand(handle)

            if hand_wf_id is None:
                # Hand already completed (blackjack / dealer blackjack)
                last = await handle.query(BlackjackSessionWorkflow.get_last_hand_result)
                if last:
                    render_result(last)
                continue

            hand_handle = client.get_workflow_handle(hand_wf_id)

            # Show initial deal
            try:
                snap = await hand_handle.query(BlackjackHandWorkflow.get_snapshot)
                render_snapshot(snap)
            except Exception as e:
                print(f"  (Could not load initial deal: {e})")

            # Check if hand needs player input
            try:
                available = await hand_handle.query(
                    BlackjackHandWorkflow.get_available_actions
                )
            except Exception as e:
                print(f"  (Could not query actions: {e})")
                available = []

            if not available:
                # Hand resolved without player input (blackjack)
                state = await wait_for_bet_ready(handle)
                last = await handle.query(BlackjackSessionWorkflow.get_last_hand_result)
                if last:
                    render_result(last)
                continue

            # Player action loop
            while available:
                action = prompt_action(available)

                try:
                    snap = await hand_handle.execute_update(
                        BlackjackHandWorkflow.player_action,
                        {"action": action.value, "hand_index": 0},
                    )
                except Exception as e:
                    render_error(f"Action failed: {e}")
                    break

                if not snap.get("hand_over", False):
                    render_snapshot(snap)

                if snap.get("hand_over", False):
                    break

                try:
                    available = await hand_handle.query(
                        BlackjackHandWorkflow.get_available_actions
                    )
                except Exception as e:
                    print(f"  (Could not query actions: {e})")
                    break

                if not available:
                    break

            # Show "Dealer is playing..." then result
            print()
            print(LINE)
            print("  Dealer is playing...")

            state = await wait_for_bet_ready(handle)
            last = await handle.query(BlackjackSessionWorkflow.get_last_hand_result)
            if last:
                render_result(last)

    except KeyboardInterrupt:
        print("\n  Interrupted! Cashing out...")
        try:
            await handle.signal(BlackjackSessionWorkflow.cash_out)
        except Exception as e:
            print(f"  (Could not signal cash out: {e})")

    # Final summary
    try:
        result = await handle.result()
        render_session_summary(result, player_name, session_id)
    except Exception as e:
        print(f"\n  (Could not get session result: {e})")
        try:
            state = await handle.query(BlackjackSessionWorkflow.get_session_state)
            print(f"  Final bankroll: ${state['bankroll']}")
        except Exception:
            print("  (Could not retrieve final state)")


if __name__ == "__main__":
    asyncio.run(main())

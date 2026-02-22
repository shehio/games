"""Blackjack CLI client - connects to Temporal and plays interactively."""

import asyncio
import os
import sys
import uuid

from temporalio.client import Client

from shared.constants import MIN_BET, STARTING_BANKROLL, TASK_QUEUE
from shared.models import Action
from client.ui.renderer import (
    console,
    render_error,
    render_result,
    render_session_summary,
    render_snapshot,
    render_welcome,
)
from client.ui.prompts import confirm_cash_out, prompt_action, prompt_bet
from worker.workflows.blackjack_session import BlackjackSessionWorkflow
from worker.workflows.blackjack_hand import BlackjackHandWorkflow


async def main():
    temporal_host = os.environ.get("TEMPORAL_HOST", "temporal:7233")
    print(f"Connecting to Temporal at {temporal_host}...")

    client = await Client.connect(temporal_host)
    print("Connected!")

    session_id = f"blackjack-{uuid.uuid4().hex[:8]}"

    # Start session workflow
    handle = await client.start_workflow(
        BlackjackSessionWorkflow.run,
        id=session_id,
        task_queue=TASK_QUEUE,
    )

    render_welcome(STARTING_BANKROLL)

    try:
        while True:
            # Get current session state
            state = await handle.query(BlackjackSessionWorkflow.get_session_state)

            if state["session_over"]:
                print("  Session over!")
                break

            if state["bankroll"] < MIN_BET:
                print("  You're broke! Game over.")
                break

            # Prompt for bet
            bet = prompt_bet(state["bankroll"], MIN_BET)
            if bet is None:
                if confirm_cash_out():
                    await handle.signal(BlackjackSessionWorkflow.cash_out)
                    break
                continue

            # Place bet via update
            bet_result = await handle.execute_update(
                BlackjackSessionWorkflow.place_bet,
                {"amount": bet},
            )

            if not bet_result["ok"]:
                render_error(bet_result["error"])
                continue

            # Wait briefly for child workflow to start
            await asyncio.sleep(0.5)

            # Get the hand workflow id
            state = await handle.query(BlackjackSessionWorkflow.get_session_state)
            hand_wf_id = state["active_hand_workflow_id"]

            if not hand_wf_id:
                # Hand might have already completed (blackjack/dealer blackjack)
                await asyncio.sleep(0.5)
                state = await handle.query(BlackjackSessionWorkflow.get_session_state)
                hand_wf_id = state["active_hand_workflow_id"]

            hand_handle = client.get_workflow_handle(hand_wf_id)

            # Get initial snapshot - hand may have already completed (natural blackjack)
            try:
                snap = await hand_handle.query(BlackjackHandWorkflow.get_snapshot)
                render_snapshot(snap, state["bankroll"])
            except Exception:
                pass

            # Check if hand already resolved (blackjack etc.)
            try:
                available = await hand_handle.query(
                    BlackjackHandWorkflow.get_available_actions
                )
            except Exception:
                available = []

            if not available:
                # Hand already done (blackjack/dealer blackjack) - get result
                try:
                    hand_result = await hand_handle.result()
                    render_result(hand_result)
                    state = await handle.query(BlackjackSessionWorkflow.get_session_state)
                    print(f"  Bankroll: ${state['bankroll']}")
                except Exception:
                    pass
                print()
                continue

            # Play loop
            while available:
                action = prompt_action(available)

                try:
                    snap = await hand_handle.execute_update(
                        BlackjackHandWorkflow.player_action,
                        {"action": action.value, "hand_index": 0},
                    )
                except Exception as e:
                    break

                render_snapshot(snap, 0)

                if snap.get("hand_over", False):
                    break

                try:
                    available = await hand_handle.query(
                        BlackjackHandWorkflow.get_available_actions
                    )
                except Exception:
                    break

                if not available:
                    break

            # Wait for hand workflow to complete and show result
            try:
                hand_result = await hand_handle.result()
                render_result(hand_result)
                await asyncio.sleep(0.3)
                state = await handle.query(BlackjackSessionWorkflow.get_session_state)
                print(f"  Bankroll: ${state['bankroll']}")
            except Exception:
                pass

            print()

    except KeyboardInterrupt:
        print("\n  Interrupted! Cashing out...")
        try:
            await handle.signal(BlackjackSessionWorkflow.cash_out)
        except Exception:
            pass

    # Get final summary
    try:
        result = await handle.result()
        render_session_summary(result)
    except Exception:
        state = await handle.query(BlackjackSessionWorkflow.get_session_state)
        print(f"\n  Final bankroll: ${state['bankroll']}")

    print("  Thanks for playing!\n")


if __name__ == "__main__":
    asyncio.run(main())

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from shared.constants import (
        MIN_BET,
        RESHUFFLE_THRESHOLD,
        STARTING_BANKROLL,
        TASK_QUEUE,
    )
    from shared.models import (
        Card,
        card_from_dict,
        card_to_dict,
    )
    from worker.activities.deck import shuffle_deck
    from worker.workflows.blackjack_hand import BlackjackHandWorkflow


@workflow.defn
class BlackjackSessionWorkflow:
    """Parent workflow: manages bankroll, shoe, and spawns child hand workflows."""

    def __init__(self) -> None:
        self.bankroll: int = STARTING_BANKROLL
        self.shoe: list[Card] = []
        self.hands_played: int = 0
        self.hands_won: int = 0
        self.hands_lost: int = 0
        self.hands_pushed: int = 0
        self.blackjacks: int = 0
        self.total_wagered: int = 0
        self.net_winnings: int = 0
        self.biggest_win: int = 0
        self.bankroll_high: int = STARTING_BANKROLL
        self.active_hand_workflow_id: str | None = None
        self.waiting_for_bet: bool = True
        self.session_over: bool = False
        self.pending_bet: int | None = None
        self.cash_out_requested: bool = False
        self.last_hand_result: dict | None = None

    def _draw(self) -> Card:
        return self.shoe.pop(0)

    async def _ensure_shoe(self) -> None:
        if len(self.shoe) < RESHUFFLE_THRESHOLD:
            workflow.logger.info("Reshuffling shoe...")
            card_dicts = await workflow.execute_activity(
                shuffle_deck,
                start_to_close_timeout=timedelta(seconds=10),
                retry_policy=RetryPolicy(maximum_attempts=3),
            )
            self.shoe = [card_from_dict(d) for d in card_dicts]

    @workflow.signal
    async def cash_out(self) -> None:
        self.cash_out_requested = True
        self.session_over = True

    @workflow.update
    async def place_bet(self, inp: dict) -> dict:
        """Place a bet and start a new hand.

        Returns dict with ok, error, and hand_workflow_id.
        """
        if self.session_over:
            return {"ok": False, "error": "Session is over.", "hand_workflow_id": None}

        if not self.waiting_for_bet:
            return {"ok": False, "error": "Hand already in progress.", "hand_workflow_id": None}

        amount = inp["amount"]
        if amount < MIN_BET:
            return {"ok": False, "error": f"Minimum bet is ${MIN_BET}.", "hand_workflow_id": None}
        if amount > self.bankroll:
            return {
                "ok": False,
                "error": f"Not enough bankroll. You have ${self.bankroll}.",
                "hand_workflow_id": None,
            }

        self.waiting_for_bet = False
        self.bankroll -= amount
        self.total_wagered += amount
        self.pending_bet = amount
        return {"ok": True, "error": None, "hand_workflow_id": "pending"}

    @workflow.query
    def get_last_hand_result(self) -> dict | None:
        return self.last_hand_result

    @workflow.query
    def get_session_state(self) -> dict:
        return {
            "bankroll": self.bankroll,
            "hands_played": self.hands_played,
            "hands_won": self.hands_won,
            "hands_lost": self.hands_lost,
            "hands_pushed": self.hands_pushed,
            "blackjacks": self.blackjacks,
            "total_wagered": self.total_wagered,
            "net_winnings": self.net_winnings,
            "active_hand_workflow_id": self.active_hand_workflow_id,
            "waiting_for_bet": self.waiting_for_bet,
            "session_over": self.session_over,
            "shoe_cards_remaining": len(self.shoe),
        }

    @workflow.run
    async def run(self) -> dict:
        """Main session loop. Returns session summary."""
        # Initial shuffle
        await self._ensure_shoe()

        while not self.session_over:
            self.waiting_for_bet = True
            self.active_hand_workflow_id = None

            # Wait for a bet or cash out
            await workflow.wait_condition(
                lambda: self.pending_bet is not None or self.cash_out_requested
            )

            if self.cash_out_requested:
                break

            bet = self.pending_bet
            self.pending_bet = None

            # Ensure shoe has enough cards
            await self._ensure_shoe()

            # Deal initial cards
            player_cards = [self._draw(), self._draw()]
            dealer_cards = [self._draw(), self._draw()]

            # Start child workflow
            hand_wf_id = f"hand-{workflow.info().workflow_id}-{self.hands_played}"
            self.active_hand_workflow_id = hand_wf_id
            self.waiting_for_bet = False

            hand_input = {
                "bet": bet,
                "shoe": [card_to_dict(c) for c in self.shoe],
                "dealer_cards": [card_to_dict(c) for c in dealer_cards],
                "player_cards": [card_to_dict(c) for c in player_cards],
            }

            result = await workflow.execute_child_workflow(
                BlackjackHandWorkflow.run,
                hand_input,
                id=hand_wf_id,
                task_queue=TASK_QUEUE,
            )

            # Update shoe from child's remaining cards
            self.shoe = [card_from_dict(c) for c in result["remaining_shoe"]]

            # Store result for client to query
            self.last_hand_result = result

            # Process result
            net_payout = result["net_payout"]
            self.bankroll += bet + net_payout  # return bet + net
            self.net_winnings += net_payout
            self.hands_played += 1

            if net_payout > 0 and net_payout > self.biggest_win:
                self.biggest_win = net_payout
            if self.bankroll > self.bankroll_high:
                self.bankroll_high = self.bankroll

            desc = result["result_description"]
            if "Blackjack" in desc and "win" in desc.lower():
                self.blackjacks += 1
                self.hands_won += 1
            elif "Win" in desc or "win" in desc:
                self.hands_won += 1
            elif "Push" in desc or "push" in desc:
                self.hands_pushed += 1
            else:
                self.hands_lost += 1

            # Check bankruptcy
            if self.bankroll < MIN_BET:
                self.session_over = True

        return {
            "final_bankroll": self.bankroll,
            "hands_played": self.hands_played,
            "hands_won": self.hands_won,
            "hands_lost": self.hands_lost,
            "hands_pushed": self.hands_pushed,
            "blackjacks": self.blackjacks,
            "total_wagered": self.total_wagered,
            "net_winnings": self.net_winnings,
            "starting_bankroll": STARTING_BANKROLL,
            "biggest_win": self.biggest_win,
            "bankroll_high": self.bankroll_high,
        }

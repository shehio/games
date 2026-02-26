from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from shared.models import (
        Action,
        Card,
        HandResult,
        HandSnapshot,
        HandState,
        PlayerActionInput,
        best_total,
        card_from_dict,
        card_to_dict,
        is_blackjack,
        snapshot_to_dict,
    )


@workflow.defn
class BlackjackHandWorkflow:
    """Child workflow: manages a single blackjack hand."""

    def __init__(self) -> None:
        self.player_hands: list[HandState] = []
        self.dealer_cards: list[Card] = []
        self.shoe: list[Card] = []
        self.bet: int = 0
        self.pending_action: PlayerActionInput | None = None
        self.hand_over: bool = False
        self.active_hand_index: int = 0

    def _draw(self) -> Card:
        return self.shoe.pop(0)

    def _build_snapshot(self, message: str = "") -> HandSnapshot:
        return HandSnapshot(
            player_hands=self.player_hands,
            dealer_cards=self.dealer_cards,
            dealer_hidden=not self.hand_over,
            hand_over=self.hand_over,
            message=message,
        )

    def _available_actions(self) -> list[Action]:
        hand = self.player_hands[self.active_hand_index]
        if hand.is_done:
            return []
        actions = [Action.HIT, Action.STAND]
        if len(hand.cards) == 2 and not hand.is_doubled:
            actions.append(Action.DOUBLE)
        if (
            len(hand.cards) == 2
            and len(self.player_hands) == 1
            and hand.cards[0].rank == hand.cards[1].rank
        ):
            actions.append(Action.SPLIT)
        return actions

    @workflow.update
    async def player_action(self, inp: dict) -> dict:
        """Handle a player action (hit/stand/double/split). Returns snapshot dict."""
        action = Action(inp["action"])
        hand_idx = inp.get("hand_index", 0)

        if self.hand_over:
            return snapshot_to_dict(self._build_snapshot("Hand is already over."))

        if hand_idx != self.active_hand_index:
            return snapshot_to_dict(
                self._build_snapshot(f"Play hand {self.active_hand_index + 1} first.")
            )

        hand = self.player_hands[hand_idx]
        available = self._available_actions()

        if action not in available:
            return snapshot_to_dict(
                self._build_snapshot(
                    f"Invalid action. Choose from: {', '.join(a.value for a in available)}"
                )
            )

        if action == Action.HIT:
            hand.cards.append(self._draw())
            if best_total(hand.cards) > 21:
                hand.is_done = True
                hand.result = HandResult.BUST
                hand.payout = 0

        elif action == Action.STAND:
            hand.is_done = True

        elif action == Action.DOUBLE:
            hand.bet *= 2
            hand.is_doubled = True
            hand.cards.append(self._draw())
            hand.is_done = True
            if best_total(hand.cards) > 21:
                hand.result = HandResult.BUST
                hand.payout = 0

        elif action == Action.SPLIT:
            card1 = hand.cards[0]
            card2 = hand.cards[1]
            hand.cards = [card1, self._draw()]
            new_hand = HandState(cards=[card2, self._draw()], bet=self.bet)
            self.player_hands.append(new_hand)

        # Advance to next unfinished hand
        self._advance_active_hand()

        # Signal main loop if all hands done
        if all(h.is_done for h in self.player_hands):
            self.pending_action = inp  # wake up main loop

        return snapshot_to_dict(self._build_snapshot())

    def _advance_active_hand(self) -> None:
        while self.active_hand_index < len(self.player_hands):
            if not self.player_hands[self.active_hand_index].is_done:
                return
            self.active_hand_index += 1
        # all done - reset to 0
        self.active_hand_index = max(0, len(self.player_hands) - 1)

    @workflow.query
    def get_snapshot(self) -> dict:
        return snapshot_to_dict(self._build_snapshot())

    @workflow.query
    def get_available_actions(self) -> list[str]:
        return [a.value for a in self._available_actions()]

    @workflow.query
    def get_remaining_shoe_count(self) -> int:
        return len(self.shoe)

    @workflow.run
    async def run(self, input_data: dict) -> dict:
        """Run one hand of blackjack.

        input_data keys: bet, shoe, dealer_cards, player_cards (all card dicts).
        Returns: net_payout, result_description, final_snapshot, remaining_shoe.
        """
        self.bet = input_data["bet"]
        self.shoe = [card_from_dict(c) for c in input_data["shoe"]]
        self.dealer_cards = [card_from_dict(c) for c in input_data["dealer_cards"]]
        player_cards = [card_from_dict(c) for c in input_data["player_cards"]]

        self.player_hands = [HandState(cards=player_cards, bet=self.bet)]

        # Check for natural blackjack
        if is_blackjack(player_cards):
            if is_blackjack(self.dealer_cards):
                self.player_hands[0].result = HandResult.PUSH
                self.player_hands[0].payout = self.bet
                self.player_hands[0].is_done = True
                self.hand_over = True
                desc = "Both have Blackjack - Push!"
            else:
                self.player_hands[0].result = HandResult.BLACKJACK
                self.player_hands[0].payout = int(self.bet + self.bet * 1.5)
                self.player_hands[0].is_done = True
                self.hand_over = True
                desc = "Blackjack! You win!"

            return {
                "net_payout": sum(h.payout for h in self.player_hands)
                - sum(h.bet for h in self.player_hands),
                "result_description": desc,
                "final_snapshot": snapshot_to_dict(self._build_snapshot(desc)),
                "remaining_shoe": [card_to_dict(c) for c in self.shoe],
            }

        # Check dealer blackjack
        if is_blackjack(self.dealer_cards):
            self.player_hands[0].result = HandResult.LOSE
            self.player_hands[0].payout = 0
            self.player_hands[0].is_done = True
            self.hand_over = True
            desc = "Dealer has Blackjack. You lose."
            return {
                "net_payout": -self.bet,
                "result_description": desc,
                "final_snapshot": snapshot_to_dict(self._build_snapshot(desc)),
                "remaining_shoe": [card_to_dict(c) for c in self.shoe],
            }

        # Wait for player to finish all hands
        await workflow.wait_condition(lambda: all(h.is_done for h in self.player_hands))

        # Dealer plays
        self.hand_over = True
        all_busted = all(h.result == HandResult.BUST for h in self.player_hands)

        if not all_busted:
            while best_total(self.dealer_cards) < 17:
                self.dealer_cards.append(self._draw())

        dealer_total = best_total(self.dealer_cards)
        dealer_bust = dealer_total > 21

        # Resolve each hand
        descriptions = []
        for i, hand in enumerate(self.player_hands):
            prefix = f"Hand {i + 1}: " if len(self.player_hands) > 1 else ""
            player_total = best_total(hand.cards)

            if hand.result == HandResult.BUST:
                hand.payout = 0
                descriptions.append(f"{prefix}Bust ({player_total}) - Lose")
            elif dealer_bust:
                hand.result = HandResult.WIN
                hand.payout = hand.bet * 2
                descriptions.append(f"{prefix}Win! Dealer busts ({dealer_total})")
            elif player_total > dealer_total:
                hand.result = HandResult.WIN
                hand.payout = hand.bet * 2
                descriptions.append(f"{prefix}Win! {player_total} vs {dealer_total}")
            elif player_total < dealer_total:
                hand.result = HandResult.LOSE
                hand.payout = 0
                descriptions.append(f"{prefix}Lose. {player_total} vs {dealer_total}")
            else:
                hand.result = HandResult.PUSH
                hand.payout = hand.bet
                descriptions.append(f"{prefix}Push. {player_total} vs {dealer_total}")

        total_bet = sum(h.bet for h in self.player_hands)
        total_payout = sum(h.payout for h in self.player_hands)
        net = total_payout - total_bet
        desc = " | ".join(descriptions)

        return {
            "net_payout": net,
            "result_description": desc,
            "final_snapshot": snapshot_to_dict(self._build_snapshot(desc)),
            "remaining_shoe": [card_to_dict(c) for c in self.shoe],
        }

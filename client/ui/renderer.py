"""Plain text CLI renderer for Blackjack."""

from shared.models import (
    Card,
    best_total,
    snapshot_from_dict,
)

LINE = "────────────────────────────────────────"
DOUBLE_LINE = "═══════════════════════════════════════"


def render_card(card: Card) -> list[str]:
    rank = card.rank.value.ljust(2)
    suit = card.suit.value
    return [
        "┌─────┐",
        f"│{rank}   │",
        "│     │",
        f"│  {suit}  │",
        "│     │",
        f"│   {rank}│",
        "└─────┘",
    ]


def render_hidden_card() -> list[str]:
    return [
        "┌─────┐",
        "│░░░░░│",
        "│░░░░░│",
        "│░░░░░│",
        "│░░░░░│",
        "│░░░░░│",
        "└─────┘",
    ]


def render_hand_str(cards: list[Card], hidden: bool = False) -> str:
    card_renders = []
    for i, card in enumerate(cards):
        if i == 1 and hidden:
            card_renders.append(render_hidden_card())
        else:
            card_renders.append(render_card(card))

    if not card_renders:
        return ""
    lines = []
    for row in range(7):
        line_parts = [cr[row] for cr in card_renders]
        lines.append(" ".join(line_parts))
    return "\n".join(lines)


def render_snapshot(
    snap_dict: dict,
    bankroll: int = 0,
    running_count: int = 0,
    true_count: float = 0.0,
) -> None:
    snap = snapshot_from_dict(snap_dict)
    print()
    print(LINE)

    # Dealer - only show face-up card during play
    if snap.dealer_hidden:
        print("  DEALER showing:")
        # Only render the first (face-up) card
        card_str = render_hand_str(snap.dealer_cards[:1])
    else:
        print("  DEALER'S HAND:")
        card_str = render_hand_str(snap.dealer_cards)

    for line in card_str.split("\n"):
        print(line)

    if not snap.dealer_hidden:
        print(f"  Value: {best_total(snap.dealer_cards)}")

    # Player hands
    for i, hand in enumerate(snap.player_hands):
        total = best_total(hand.cards)
        hand_str = render_hand_str(hand.cards)

        print()
        label = f"  HAND {i + 1}:" if len(snap.player_hands) > 1 else "  YOUR HAND:"
        if hand.is_doubled:
            label += " [DOUBLED]"
        print(label)

        for line in hand_str.split("\n"):
            print(line)

        print(f"  Value: {total}  |  Bet: ${hand.bet}")

    if running_count != 0 or true_count != 0.0:
        rc_sign = "+" if running_count >= 0 else ""
        tc_sign = "+" if true_count >= 0 else ""
        print(f"  Count: RC {rc_sign}{running_count} | TC {tc_sign}{true_count:.1f}")

    print(LINE)

    if snap.insurance_offered:
        print("  ** INSURANCE AVAILABLE **")
    if snap.insurance_result:
        print(f"  {snap.insurance_result}")

    if snap.message:
        print(f"  {snap.message}")
        print(LINE)


def render_result(hand_result: dict) -> None:
    snap = snapshot_from_dict(hand_result["final_snapshot"])
    print()
    print(LINE)

    # Dealer's full hand
    dealer_total = best_total(snap.dealer_cards)
    print("  DEALER'S HAND:")
    dealer_str = render_hand_str(snap.dealer_cards, hidden=False)
    for line in dealer_str.split("\n"):
        print(line)
    print(f"  Value: {dealer_total}")

    # Player hands
    for i, hand in enumerate(snap.player_hands):
        total = best_total(hand.cards)
        hand_str = render_hand_str(hand.cards)

        print()
        label = f"  HAND {i + 1}:" if len(snap.player_hands) > 1 else "  YOUR HAND:"
        print(label)

        for line in hand_str.split("\n"):
            print(line)

        print(f"  Value: {total}")

    # Result
    print()
    print(LINE)

    net = hand_result["net_payout"]
    total_bet = sum(h.bet for h in snap.player_hands)
    total_payout = total_bet + net

    if net > 0:
        print("  You WIN!")
        print(f"  Payout: ${total_payout} (net +${net})")
    elif net < 0:
        print("  You LOSE.")
        print(f"  Lost: ${abs(net)}")
    else:
        print("  PUSH.")
        print(f"  Bet returned: ${total_bet}")

    print(LINE)


def render_stats_bar(state: dict, running_count: int = 0, true_count: float = 0.0) -> None:
    """Show running stats between hands."""
    print()
    print(DOUBLE_LINE)
    print(f"  Bankroll: ${state['bankroll']}")
    print(f"  Hands played: {state['hands_played']}")
    rc_sign = "+" if running_count >= 0 else ""
    tc_sign = "+" if true_count >= 0 else ""
    print(f"  Count: RC {rc_sign}{running_count} | TC {tc_sign}{true_count:.1f}")
    print(DOUBLE_LINE)
    print()


def render_session_summary(summary: dict, player_name: str, session_id: str) -> None:
    print()
    w = 42
    print("╔" + "═" * w + "╗")
    title = "SESSION SUMMARY"
    pad = (w - len(title)) // 2
    print("║" + " " * pad + title + " " * (w - pad - len(title)) + "║")
    print("╚" + "═" * w + "╝")

    print(f"  Player: {player_name}")
    print(f"  Final bankroll: ${summary['final_bankroll']}")
    print(f"  Hands played: {summary['hands_played']}")
    won, lost, pushed = summary["hands_won"], summary["hands_lost"], summary["hands_pushed"]
    print(f"  Won: {won}  |  Lost: {lost}  |  Pushed: {pushed}")
    print(f"  Biggest win: ${summary['biggest_win']}")
    print(f"  Bankroll high: ${summary['bankroll_high']}")
    print()
    print(f"  Thanks for playing, {player_name}!")
    print(f"  Session ID: {session_id}")
    print("  View in Temporal UI: http://localhost:8080")
    print()


def render_welcome() -> None:
    print()
    w = 42
    print("╔" + "═" * w + "╗")
    lines = [
        "♠ ♥ ♦ ♣  BLACKJACK CASINO  ♣ ♦ ♥ ♠",
        "",
        "Powered by Temporal Workflows",
        "Each hand is a child workflow!",
    ]
    for line in lines:
        pad = (w - len(line)) // 2
        print("║" + " " * pad + line + " " * (w - pad - len(line)) + "║")
    print("╚" + "═" * w + "╝")
    print()

    shoe = (
        "       ┌──────────────────────────┐\n"
        "      /│ ┌──┐┌──┐┌──┐┌──┐┌──┐┌──┐ │\n"
        "     / │ │♠ ││♥ ││♦ ││♣ ││♠ ││♥ │ │\n"
        "    /  │ │  ││  ││  ││  ││  ││  │ │\n"
        "   /   │ └──┘└──┘└──┘└──┘└──┘└──┘ │\n"
        "  /    │  312 cards · 6 decks     │\n"
        " /     │══════════════════════════│\n"
        "/______│  ←  cards dealt out here │\n"
        "       └──────────────────────────┘"
    )
    print(shoe)
    print()

    print('  The "shoe" is a dealing device used in')
    print("  casinos. It holds 6 shuffled decks (312")
    print("  cards) to make card counting harder.")
    print("  Cards slide out one at a time from the")
    print("  front slot as the dealer draws them.")
    print()


def render_error(message: str) -> None:
    print(f"  Error: {message}")

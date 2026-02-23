"""Plain text CLI renderer for Blackjack."""

from shared.models import (
    Card,
    HandResult,
    HandSnapshot,
    HandState,
    best_total,
    snapshot_from_dict,
)


def render_card(card: Card) -> list[str]:
    rank = card.rank.value.ljust(2)
    suit = card.suit.value
    return [
        "┌─────┐",
        f"│{rank}   │",
        f"│  {suit}  │",
        f"│   {rank}│",
        "└─────┘",
    ]


def render_hidden_card() -> list[str]:
    return [
        "┌─────┐",
        "│░░░░░│",
        "│░░░░░│",
        "│░░░░░│",
        "└─────┘",
    ]


def render_hand(cards: list[Card], hidden: bool = False) -> str:
    card_renders = []
    for i, card in enumerate(cards):
        if i == 1 and hidden:
            card_renders.append(render_hidden_card())
        else:
            card_renders.append(render_card(card))

    if not card_renders:
        return ""
    lines = []
    for row in range(5):
        line_parts = [cr[row] for cr in card_renders]
        lines.append(" ".join(line_parts))
    return "\n".join(lines)


def _box(lines: list[str], width: int = 48) -> str:
    """Wrap lines in a single-line box."""
    top = "┌" + "─" * width + "┐"
    bot = "└" + "─" * width + "┘"
    result = [top]
    for line in lines:
        padded = line.ljust(width)[:width]
        result.append(f"│{padded}│")
    result.append(bot)
    return "\n".join(result)


def render_snapshot(snap_dict: dict, bankroll: int = 0) -> None:
    snap = snapshot_from_dict(snap_dict)
    print()

    # Dealer
    dealer_hand_str = render_hand(snap.dealer_cards, hidden=snap.dealer_hidden)
    if snap.dealer_hidden:
        visible_total = best_total(snap.dealer_cards[:1])
        dealer_label = f"Dealer ({visible_total} + ?)"
    else:
        dealer_label = f"Dealer ({best_total(snap.dealer_cards)})"

    print(f"  --- {dealer_label} ---")
    for line in dealer_hand_str.split("\n"):
        print(f"  {line}")

    # Player hands
    for i, hand in enumerate(snap.player_hands):
        total = best_total(hand.cards)
        hand_str = render_hand(hand.cards)
        label = f"Your Hand ({total})"
        if len(snap.player_hands) > 1:
            label = f"Hand {i+1} ({total})"
        if hand.is_doubled:
            label += " [DOUBLED]"
        if hand.result:
            label += f" - {hand.result.value.upper()}"

        print()
        print(f"  --- {label} --- Bet: ${hand.bet}")
        for line in hand_str.split("\n"):
            print(f"  {line}")

    if snap.message:
        print()
        print(f"  >> {snap.message}")

    if bankroll > 0:
        print(f"  Bankroll: ${bankroll}")


def render_result(hand_result: dict) -> None:
    snap = snapshot_from_dict(hand_result["final_snapshot"])
    print()

    # Show dealer's full hand
    dealer_total = best_total(snap.dealer_cards)
    dealer_hand_str = render_hand(snap.dealer_cards, hidden=False)
    print(f"  --- Dealer ({dealer_total}) ---")
    for line in dealer_hand_str.split("\n"):
        print(f"  {line}")

    # Show player hands
    for i, hand in enumerate(snap.player_hands):
        total = best_total(hand.cards)
        hand_str = render_hand(hand.cards)
        label = f"Your Hand ({total})"
        if len(snap.player_hands) > 1:
            label = f"Hand {i+1} ({total})"
        if hand.is_doubled:
            label += " [DOUBLED]"
        if hand.result:
            label += f" - {hand.result.value.upper()}"
        print()
        print(f"  --- {label} --- Bet: ${hand.bet}")
        for line in hand_str.split("\n"):
            print(f"  {line}")

    # Result message
    desc = hand_result["result_description"]
    net = hand_result["net_payout"]
    if net > 0:
        net_str = f"+${net}"
    elif net < 0:
        net_str = f"-${abs(net)}"
    else:
        net_str = "$0"

    print()
    print(f"  >> {desc} ({net_str})")


def render_stats_bar(state: dict) -> None:
    """Show running stats between hands."""
    played = state["hands_played"]
    if played > 0:
        print(f"  Hands played: {played}")
        print("  ─────────────────────────────────────────")


def render_session_summary(summary: dict, player_name: str, session_id: str) -> None:
    print()
    lines = [
        "",
        "        SESSION SUMMARY",
        "",
        f"  Player: {player_name}",
        f"  Final bankroll: ${summary['final_bankroll']}",
        f"  Hands played: {summary['hands_played']}",
        f"  Won: {summary['hands_won']}  |  Lost: {summary['hands_lost']}  |  Pushed: {summary['hands_pushed']}",
        f"  Biggest win: ${summary['biggest_win']}",
        f"  Bankroll high: ${summary['bankroll_high']}",
        "",
        f"  Thanks for playing, {player_name}!",
        f"  Session ID: {session_id}",
        f"  View in Temporal UI: http://localhost:8080",
    ]
    print(_box(lines, 48))
    print()


def render_welcome() -> None:
    print()
    title_lines = [
        "",
        "    ♠ ♥ ♦ ♣  BLACKJACK CASINO  ♣ ♦ ♥ ♠",
        "",
        "  Powered by Temporal Workflows",
        "  Each hand is a child workflow!",
    ]
    print(_box(title_lines, 48))
    print()

    shoe = (
        "              ┌────────────────────────────────┐\n"
        "             /│ ┌──┐ ┌──┐ ┌──┐ ┌──┐ ┌──┐ ┌──┐  │\n"
        "            / │ │♠ │ │♥ │ │♦ │ │♣ │ │♠ │ │♥ │  │\n"
        "           /  │ └──┘ └──┘ └──┘ └──┘ └──┘ └──┘  │\n"
        "          /   │      312 cards · 6 decks       │\n"
        "         /    ├────────────────────────────────┤\n"
        "        /     │    ← cards dealt out here      │\n"
        "       /──────┴────────────────────────────────┘"
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

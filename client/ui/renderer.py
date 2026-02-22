"""Plain text CLI renderer for Blackjack."""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

from shared.models import (
    Card,
    HandResult,
    HandSnapshot,
    HandState,
    best_total,
    snapshot_from_dict,
)

console = Console(highlight=False)


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


def render_session_summary(summary: dict) -> None:
    print()
    print("  ================================")
    print("         SESSION SUMMARY")
    print("  ================================")

    starting = summary["starting_bankroll"]
    final = summary["final_bankroll"]
    net = summary["net_winnings"]
    net_str = f"+${net}" if net >= 0 else f"-${abs(net)}"

    print(f"  Starting Bankroll:  ${starting}")
    print(f"  Final Bankroll:     ${final}")
    print(f"  Net:                {net_str}")
    print()
    print(f"  Hands Played:       {summary['hands_played']}")
    print(f"  Wins:               {summary['hands_won']}")
    print(f"  Losses:             {summary['hands_lost']}")
    print(f"  Pushes:             {summary['hands_pushed']}")
    print(f"  Blackjacks:         {summary['blackjacks']}")
    print(f"  Total Wagered:      ${summary['total_wagered']}")
    print("  ================================")
    print()


def render_welcome(bankroll: int) -> None:
    print()
    print("  ================================")
    print("      ♠ ♥  BLACKJACK  ♦ ♣")
    print("  ================================")
    print("  6-deck shoe")
    print("  Dealer stands on 17")
    print("  Blackjack pays 3:2")
    print(f"  Starting bankroll: ${bankroll}")
    print(f"  Min bet: $10")
    print("  ================================")
    print()


def render_error(message: str) -> None:
    print(f"  Error: {message}")

"""CLI prompts for the Blackjack client."""

from shared.models import Action


def prompt_bet(bankroll: int, min_bet: int) -> int | None:
    """Ask player for bet amount. Returns None if they want to cash out."""
    print(f"  Bankroll: ${bankroll} | Min bet: ${min_bet}")
    response = input(f"  Place your bet (or 'q' to cash out) [{min_bet}]: ").strip()
    if not response:
        response = str(min_bet)
    if response.lower() in ("q", "quit", "exit", "cash out"):
        return None
    try:
        bet = int(response)
        if bet < min_bet:
            print(f"  Minimum bet is ${min_bet}")
            return prompt_bet(bankroll, min_bet)
        if bet > bankroll:
            print(f"  You only have ${bankroll}")
            return prompt_bet(bankroll, min_bet)
        return bet
    except ValueError:
        print("  Enter a number or 'q' to quit")
        return prompt_bet(bankroll, min_bet)


def prompt_action(available: list[str]) -> Action:
    """Ask player for their action."""
    action_map = {
        "h": Action.HIT,
        "hit": Action.HIT,
        "s": Action.STAND,
        "stand": Action.STAND,
        "d": Action.DOUBLE,
        "double": Action.DOUBLE,
        "p": Action.SPLIT,
        "split": Action.SPLIT,
    }

    shortcuts = []
    for a in available:
        if a == "hit":
            shortcuts.append("(H)it")
        elif a == "stand":
            shortcuts.append("(S)tand")
        elif a == "double":
            shortcuts.append("(D)ouble")
        elif a == "split":
            shortcuts.append("s(P)lit")

    print("  " + "  ".join(shortcuts))

    while True:
        response = input("  Action: ").strip().lower()
        if response in action_map and action_map[response].value in available:
            return action_map[response]
        print(f"  Choose from: {', '.join(available)}")


def confirm_cash_out() -> bool:
    response = input("  Cash out? (y/n) [y]: ").strip()
    if not response:
        return True
    return response.lower() in ("y", "yes")

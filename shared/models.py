from dataclasses import dataclass, field
from enum import StrEnum


class Suit(StrEnum):
    HEARTS = "♥"
    DIAMONDS = "♦"
    CLUBS = "♣"
    SPADES = "♠"


class Rank(StrEnum):
    TWO = "2"
    THREE = "3"
    FOUR = "4"
    FIVE = "5"
    SIX = "6"
    SEVEN = "7"
    EIGHT = "8"
    NINE = "9"
    TEN = "10"
    JACK = "J"
    QUEEN = "Q"
    KING = "K"
    ACE = "A"


class Action(StrEnum):
    HIT = "hit"
    STAND = "stand"
    DOUBLE = "double"
    SPLIT = "split"
    INSURANCE = "insurance"


class HandResult(StrEnum):
    WIN = "win"
    LOSE = "lose"
    PUSH = "push"
    BLACKJACK = "blackjack"
    BUST = "bust"
    SURRENDER = "surrender"


@dataclass
class Card:
    rank: Rank
    suit: Suit

    def __str__(self) -> str:
        return f"{self.rank.value}{self.suit.value}"

    def value(self) -> list[int]:
        if self.rank in (Rank.JACK, Rank.QUEEN, Rank.KING):
            return [10]
        if self.rank == Rank.ACE:
            return [1, 11]
        return [int(self.rank.value)]


@dataclass
class PlaceBetInput:
    amount: int


@dataclass
class PlayerActionInput:
    action: Action
    hand_index: int = 0  # for split hands


@dataclass
class HandState:
    cards: list[Card] = field(default_factory=list)
    bet: int = 0
    is_done: bool = False
    is_doubled: bool = False
    result: HandResult | None = None
    payout: int = 0
    insurance_bet: int = 0

    def display_cards(self) -> str:
        return " ".join(str(c) for c in self.cards)


@dataclass
class HandSnapshot:
    player_hands: list[HandState]
    dealer_cards: list[Card]
    dealer_hidden: bool = True
    hand_over: bool = False
    message: str = ""


@dataclass
class HandResultInfo:
    net_payout: int  # positive = player won, negative = lost
    result_description: str
    final_snapshot: HandSnapshot


@dataclass
class SessionState:
    bankroll: int = 0
    hands_played: int = 0
    hands_won: int = 0
    hands_lost: int = 0
    hands_pushed: int = 0
    blackjacks: int = 0
    total_wagered: int = 0
    net_winnings: int = 0
    active_hand_workflow_id: str | None = None
    waiting_for_bet: bool = True
    session_over: bool = False
    shoe_cards_remaining: int = 0


def best_total(cards: list[Card]) -> int:
    """Calculate the best (highest non-bust) total for a hand."""
    total = 0
    aces = 0
    for card in cards:
        if card.rank == Rank.ACE:
            aces += 1
            total += 11
        elif card.rank in (Rank.JACK, Rank.QUEEN, Rank.KING):
            total += 10
        else:
            total += int(card.rank.value)
    while total > 21 and aces > 0:
        total -= 10
        aces -= 1
    return total


def is_blackjack(cards: list[Card]) -> bool:
    return len(cards) == 2 and best_total(cards) == 21


def card_to_dict(card: Card) -> dict:
    return {"rank": card.rank.value, "suit": card.suit.value}


def card_from_dict(d: dict) -> Card:
    return Card(rank=Rank(d["rank"]), suit=Suit(d["suit"]))


def hand_state_to_dict(hs: HandState) -> dict:
    return {
        "cards": [card_to_dict(c) for c in hs.cards],
        "bet": hs.bet,
        "is_done": hs.is_done,
        "is_doubled": hs.is_doubled,
        "result": hs.result.value if hs.result else None,
        "payout": hs.payout,
        "insurance_bet": hs.insurance_bet,
    }


def hand_state_from_dict(d: dict) -> HandState:
    return HandState(
        cards=[card_from_dict(c) for c in d["cards"]],
        bet=d["bet"],
        is_done=d["is_done"],
        is_doubled=d["is_doubled"],
        result=HandResult(d["result"]) if d["result"] else None,
        payout=d["payout"],
        insurance_bet=d.get("insurance_bet", 0),
    )


def snapshot_to_dict(snap: HandSnapshot) -> dict:
    return {
        "player_hands": [hand_state_to_dict(h) for h in snap.player_hands],
        "dealer_cards": [card_to_dict(c) for c in snap.dealer_cards],
        "dealer_hidden": snap.dealer_hidden,
        "hand_over": snap.hand_over,
        "message": snap.message,
    }


def snapshot_from_dict(d: dict) -> HandSnapshot:
    return HandSnapshot(
        player_hands=[hand_state_from_dict(h) for h in d["player_hands"]],
        dealer_cards=[card_from_dict(c) for c in d["dealer_cards"]],
        dealer_hidden=d["dealer_hidden"],
        hand_over=d["hand_over"],
        message=d["message"],
    )


def result_info_to_dict(ri: HandResultInfo) -> dict:
    return {
        "net_payout": ri.net_payout,
        "result_description": ri.result_description,
        "final_snapshot": snapshot_to_dict(ri.final_snapshot),
    }


def result_info_from_dict(d: dict) -> HandResultInfo:
    return HandResultInfo(
        net_payout=d["net_payout"],
        result_description=d["result_description"],
        final_snapshot=snapshot_from_dict(d["final_snapshot"]),
    )

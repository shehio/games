import random

from temporalio import activity

from shared.constants import NUM_DECKS
from shared.models import Card, Rank, Suit, card_to_dict


@activity.defn
async def shuffle_deck() -> list[dict]:
    """Create and shuffle a 6-deck shoe. Returns list of card dicts."""
    shoe = []
    for _ in range(NUM_DECKS):
        for suit in Suit:
            for rank in Rank:
                shoe.append(Card(rank=rank, suit=suit))
    random.shuffle(shoe)
    activity.logger.info(f"Shuffled {len(shoe)}-card shoe")
    return [card_to_dict(c) for c in shoe]

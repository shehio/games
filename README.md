# Blackjack Casino

A fully Dockerized Blackjack game powered by [Temporal.io](https://temporal.io) workflows. Features insurance/even money, live Hi-Lo card counting, and Monte Carlo simulations.

## Quick Start

```bash
docker compose up -d                              # start Temporal + worker
docker compose --profile play run --rm client     # play!
```

## Gameplay

### Welcome & Betting

```
╔══════════════════════════════════════════╗
║    ♠ ♥ ♦ ♣  BLACKJACK CASINO  ♣ ♦ ♥ ♠    ║
║                                          ║
║      Powered by Temporal Workflows       ║
║      Each hand is a child workflow!      ║
╚══════════════════════════════════════════╝

       ┌──────────────────────────┐
      /│ ┌──┐┌──┐┌──┐┌──┐┌──┐┌──┐ │
     / │ │♠ ││♥ ││♦ ││♣ ││♠ ││♥ │ │
    /  │ │  ││  ││  ││  ││  ││  │ │
   /   │ └──┘└──┘└──┘└──┘└──┘└──┘ │
  /    │  312 cards · 6 decks     │
 /     │══════════════════════════│
/______│  ←  cards dealt out here │
       └──────────────────────────┘
```

The stats bar shows your bankroll, hands played, and the live Hi-Lo card count between hands:

```
═══════════════════════════════════════
  Bankroll: $1150
  Hands played: 5
  Count: RC +3 | TC +1.2
═══════════════════════════════════════
```

### Playing a Hand

Cards are dealt, and the running/true count updates after every card:

```
────────────────────────────────────────
  DEALER showing:
┌─────┐
│6    │
│     │
│  ♦  │
│     │
│   6 │
└─────┘

  YOUR HAND:
┌─────┐ ┌─────┐ ┌─────┐
│5    │ │6    │ │3    │
│     │ │     │ │     │
│  ♥  │ │  ♣  │ │  ♠  │
│     │ │     │ │     │
│   5 │ │   6 │ │   3 │
└─────┘ └─────┘ └─────┘
  Value: 14  |  Bet: $50
  Count: RC +5 | TC +2.1
────────────────────────────────────────
  Action? (h)it  (s)tand  (d)ouble:
```

### Insurance

When the dealer shows an Ace, you're offered insurance (a side bet up to half your wager that the dealer has Blackjack). If you have Blackjack yourself, it's offered as **even money** — a guaranteed 1:1 payout.

```
────────────────────────────────────────
  DEALER showing:
┌─────┐
│A    │
│     │
│  ♥  │
│     │
│   A │
└─────┘

  YOUR HAND:
┌─────┐ ┌─────┐
│10   │ │9    │
│     │ │     │
│  ♣  │ │  ♦  │
│     │ │     │
│   10│ │   9 │
└─────┘ └─────┘
  Value: 19  |  Bet: $100
  Count: RC +3 | TC +1.2
────────────────────────────────────────
  ** INSURANCE AVAILABLE **
  Insurance? (y/n) [n]:
```

If you take insurance and the dealer has Blackjack, insurance pays 2:1 — breaking even on the hand. If the dealer doesn't have Blackjack, you lose the insurance bet and play continues normally.

### Session Summary

```
╔══════════════════════════════════════════╗
║             SESSION SUMMARY              ║
╚══════════════════════════════════════════╝
  Player: Shehab
  Final bankroll: $1340
  Hands played: 23
  Won: 12  |  Lost: 8  |  Pushed: 3
  Biggest win: $250
  Bankroll high: $1450

  Thanks for playing, Shehab!
  Session ID: casino-shehab-a1b2
  View in Temporal UI: http://localhost:8080
```

## Game Rules

- 6-deck shoe, reshuffled when < 78 cards remain
- Blackjack pays 3:2
- Dealer stands on 17
- Split, double down, and insurance supported
- $1000 starting bankroll, $10 minimum bet

## Architecture

```
+-- Docker Compose -----------------------------------------------+
|                                                                  |
|  +----------+  updates, queries,  +------------------------+     |
|  |  Client  |<---- signals ------>|   Temporal Server      |     |
|  |  (CLI)   |                     |       ^                |     |
|  +----------+                     |       |  +----------+  |     |
|                                   |       |  | Postgres |  |     |
|                                   |       |  +----------+  |     |
|                                   +-------+----------------+     |
|                                           |                      |
|                                           v                      |
|                            +---------------------------------+   |
|                            |  Worker                         |   |
|                            |                                 |   |
|                            |  Session WF --spawns--> Hand WF |   |
|                            |      |                          |   |
|                            |      +--calls--> shuffle_deck() |   |
|                            +---------------------------------+   |
+------------------------------------------------------------------+
```

```
  Client                Session WF              Hand WF
    |                       |                       |
    |-- place_bet --------->|                       |
    |   (update)            |-- start child ------->|
    |                       |                       |
    |-- player_action ----->|---------------------->|
    |   (update)            |                       |
    |<----------------------|-------- snapshot -----|
    |                       |                       |
    |-- player_action ----->|---------------------->|
    |   (update)            |                       |
    |<----------------------|- snapshot (hand_over) |
    |                       |<-- hand result -------|
    |                       |                       |
    |-- query last result ->|                       |
    |<-- result ------------|                       |
    |                       |                       |
    |-- cash_out ---------->|                       |
    |   (signal)            |                       |
    |<-- session summary ---|                       |
    v                       v                       v
```

- **Parent workflow** (`BlackjackSessionWorkflow`) - Manages bankroll, 6-deck shoe, and session stats. Spawns one child workflow per hand.
- **Child workflow** (`BlackjackHandWorkflow`) - Handles a single hand: player actions (hit/stand/double/split) via Temporal update handlers, then runs dealer AI.
- **Activity** (`shuffle_deck`) - Shuffles a 6-deck (312 card) shoe.

## Simulations

### Shoe Penetration

A Monte Carlo simulation sweeps reshuffle thresholds across the 6-deck shoe to
find the optimal penetration depth. It plays 100,000 hands per threshold using
basic strategy and reports house edge, hands per shoe, and blackjack rate.

```bash
uv run python -m simulations.shoe_penetration
```

### Card Counting & Betting Strategies

Combines three card counting systems with four betting strategies and sweeps
across penetration thresholds to measure their effect on house edge.

**Counting systems:**
- **Hi-Lo** — balanced, single-level (2-6 = +1, 7-9 = 0, 10-A = -1)
- **Omega II** — balanced, multi-level (more precise but harder to use)
- **KO (Knock-Out)** — unbalanced (no true count conversion needed)

**Betting strategies:**
- **Flat** — constant bet (baseline)
- **Spread** — scales linearly with true count, capped at max spread
- **Kelly** — bets proportional to estimated edge (~0.5% per true count point)
- **Martingale** — doubles after loss (cautionary example)

```bash
uv run python -m simulations.counting_simulation
```

### Run Tests

```bash
uv run pytest tests/ -v
```

## Stack

- Python, Temporal Python SDK
- Postgres (Temporal persistence)
- Docker Compose

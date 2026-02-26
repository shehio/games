# Blackjack Casino

A fully Dockerized Blackjack game powered by [Temporal.io](https://temporal.io) workflows.

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

## Run

```bash
docker compose up -d
docker compose --profile play run --rm client
```

## Game Rules

- 6-deck shoe, reshuffled when low
- Blackjack pays 3:2
- Dealer stands on 17
- Split and double down supported
- $1000 starting bankroll, $10 minimum bet

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

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

## Simulation

A Monte Carlo simulation sweeps reshuffle thresholds across the 6-deck shoe to
find the optimal penetration depth. It plays 100,000 hands per threshold using
basic strategy and reports house edge, hands per shoe, and blackjack rate.

```bash
PYTHONPATH=. python -m simulations.shoe_penetration
```

Run the simulation tests:

```bash
PYTHONPATH=. pytest tests/test_shoe_penetration.py -v
```

## Stack

- Python, Temporal Python SDK
- Postgres (Temporal persistence)
- Docker Compose

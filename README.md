# Blackjack Casino

A fully Dockerized Blackjack game powered by [Temporal.io](https://temporal.io) workflows.

## Architecture

```mermaid
graph LR
    subgraph Docker Compose
        Client["Client (CLI)"]
        subgraph Temporal
            Server[Temporal Server]
            Postgres[(Postgres)]
        end
        subgraph Worker
            Session["Session WF (parent)"]
            Hand["Hand WF (child)"]
            Activity["shuffle_deck() (activity)"]
            Session -->|spawns| Hand
            Session -->|calls| Activity
        end
        Client <-->|updates, queries, signals| Server
        Server <--> Worker
    end
```

```mermaid
sequenceDiagram
    participant C as Client
    participant S as Session WF
    participant H as Hand WF

    C->>S: place_bet (update)
    S->>H: start child workflow
    C->>H: player_action (update)
    H-->>C: snapshot
    C->>H: player_action (update)
    H-->>C: snapshot (hand_over)
    H-->>S: hand result
    C->>S: query last result
    S-->>C: result
    C->>S: cash_out (signal)
    S-->>C: session summary
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

## Stack

- Python, Temporal Python SDK
- Postgres (Temporal persistence)
- Docker Compose

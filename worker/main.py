import asyncio
import os

from temporalio.client import Client
from temporalio.worker import Worker

from shared.constants import TASK_QUEUE
from worker.activities.deck import shuffle_deck
from worker.workflows.blackjack_hand import BlackjackHandWorkflow
from worker.workflows.blackjack_session import BlackjackSessionWorkflow


async def main():
    temporal_host = os.environ.get("TEMPORAL_HOST", "temporal:7233")
    print(f"Connecting to Temporal at {temporal_host}...")

    client = await Client.connect(temporal_host)
    print("Connected. Starting worker...")

    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[BlackjackSessionWorkflow, BlackjackHandWorkflow],
        activities=[shuffle_deck],
    )
    print(f"Worker listening on task queue: {TASK_QUEUE}")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())

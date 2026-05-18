# prefect/flows/kafka_to_delta.py
"""Consume from Kafka topic data.raw and persist to Delta Lake (parquet)."""
from prefect import flow, task
from prefect.client.schemas.schedules import CronSchedule
from kafka import KafkaConsumer
import json
import os
import pandas as pd
from datetime import datetime


KAFKA_BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP", "kafka:9092")
DELTA_PATH = os.environ.get("DELTA_PATH", "/opt/delta-lake/raw")


@task(retries=2, retry_delay_seconds=5)
def consume_and_process() -> list[dict]:
    consumer = KafkaConsumer(
        "data.raw",
        bootstrap_servers=KAFKA_BOOTSTRAP,
        auto_offset_reset="earliest",
        consumer_timeout_ms=5000,
        value_deserializer=lambda m: json.loads(m.decode()),
        group_id="lab28-prefect-consumer",
    )
    records = [msg.value for msg in consumer]
    consumer.close()
    print(f"Consumed {len(records)} records from Kafka")
    return records


@task
def save_to_delta(records: list[dict]) -> str | None:
    if not records:
        print("No records to save")
        return None
    df = pd.DataFrame(records)
    os.makedirs(DELTA_PATH, exist_ok=True)
    fname = f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}.parquet"
    out = os.path.join(DELTA_PATH, fname)
    df.to_parquet(out)
    print(f"Saved {len(df)} records to {out}")
    return out


@flow(name="Kafka to Delta Pipeline")
def kafka_to_delta_flow():
    records = consume_and_process()
    save_to_delta(records)


if __name__ == "__main__":
    # Local run for testing
    if os.environ.get("DEPLOY") == "1":
        kafka_to_delta_flow.serve(
            name="kafka-to-delta",
            schedule=CronSchedule(cron="*/5 * * * *"),
            tags=["lab28"],
        )
    else:
        kafka_to_delta_flow()

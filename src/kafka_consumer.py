import json

from kafka import KafkaConsumer


def get_broker_address() -> str:
    with open("kafka_broker.txt") as f:
        return f.read().strip()

def consume_priority_complaints():
    consumer = KafkaConsumer(
        "priority-complaints",
        bootstrap_servers=get_broker_address(),
        auto_offset_reset="earliest",
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        consumer_timeout_ms=10000,
    )
    print("Listening for priority complaints (10s timeout)...\n")
    count = 0
    for message in consumer:
        c = message.value
        print(f"ALERT: {c.get('complaint_type')} in {c.get('borough')} (key={c.get('unique_key')})")
        count += 1
    print(f"\nConsumed {count} messages.")

if __name__ == "__main__":
    consume_priority_complaints()
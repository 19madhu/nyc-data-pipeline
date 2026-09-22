import boto3
from dotenv import load_dotenv

load_dotenv()

FLOCI_ENDPOINT = "http://localhost:4566"
CLUSTER_NAME = "nyc311-priority-cluster"


def get_kafka_client():
    return boto3.client(
        "kafka",
        endpoint_url=FLOCI_ENDPOINT,
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )


def create_cluster():
    client = get_kafka_client()

    existing = client.list_clusters_v2()
    for cluster in existing.get("ClusterInfoList", []):
        if cluster["ClusterName"] == CLUSTER_NAME:
            print(f"Cluster '{CLUSTER_NAME}' already exists.")
            return cluster["ClusterArn"]

    response = client.create_cluster_v2(
        ClusterName=CLUSTER_NAME,
        Provisioned={
            "KafkaVersion": "3.6.1",
            "NumberOfBrokerNodes": 1,
            "BrokerNodeGroupInfo": {
                "InstanceType": "kafka.m5.large",
                "ClientSubnets": ["subnet-12345"],
            },
        },
    )
    print(f"Created cluster: {response['ClusterArn']}")
    return response["ClusterArn"]


def get_bootstrap_brokers(cluster_arn: str) -> str:
    client = get_kafka_client()
    response = client.get_bootstrap_brokers(ClusterArn=cluster_arn)
    brokers = response.get("BootstrapBrokerString")
    print(f"Bootstrap brokers: {brokers}")
    return brokers


if __name__ == "__main__":
    arn = create_cluster()
    print(f"\nCluster ARN: {arn}")
    print("Waiting a moment for the cluster to become ready...")

    import time
    time.sleep(5)

    brokers = get_bootstrap_brokers(arn)

    with open("kafka_broker.txt", "w") as f:
        f.write(brokers)
    print("\nBroker address saved to kafka_broker.txt")
# dispatch_notifier.py
"""Publishes a dispatch alert over SNS.

Two modes, switched by one env var (no code changes needed to move between them):
  - Build It (default): CIVICFLOW_USE_LOCALSTACK=1 -> talks to a local LocalStack
    SNS endpoint with mock credentials. No AWS account, no card, no bill.
  - Ship It: CIVICFLOW_USE_LOCALSTACK=0 -> talks to real AWS SNS using whatever
    credentials/IAM role is already available in the environment (EC2 instance
    profile, App Runner task role, etc.) — never hardcode real keys here.
"""
import json
import os

import boto3

# LocalStack (Build It) settings — override via env vars if your ports/region differ.
LOCALSTACK_ENDPOINT = os.getenv("LOCALSTACK_ENDPOINT", "http://localhost:4566")
LOCALSTACK_ACCESS_KEY = os.getenv("LOCALSTACK_ACCESS_KEY", "mock_key")
LOCALSTACK_SECRET_KEY = os.getenv("LOCALSTACK_SECRET_KEY", "mock_secret")

# Shared settings (both modes).
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
SNS_TOPIC_ARN = os.getenv(
    "CIVICFLOW_SNS_TOPIC_ARN",
    "arn:aws:sns:us-east-1:000000000000:civictech-dispatch-events",
)

# Mode switch. Defaults to LocalStack so `streamlit run app.py` keeps working
# out of the box with zero AWS setup (the Build It track's constraint).
USE_LOCALSTACK = os.getenv("CIVICFLOW_USE_LOCALSTACK", "1") == "1"


def trigger_localstack_notification(ticket_id: str, category: str, urgency: int, role: str) -> bool:
    """Publishes a dispatch alert to an SNS topic — LocalStack when running locally
    (the default), real AWS SNS when CIVICFLOW_USE_LOCALSTACK=0 and a real
    SNS_TOPIC_ARN is supplied for the Ship It track."""
    try:
        client_kwargs = {"region_name": AWS_REGION}
        if USE_LOCALSTACK:
            client_kwargs.update(
                endpoint_url=LOCALSTACK_ENDPOINT,
                aws_access_key_id=LOCALSTACK_ACCESS_KEY,
                aws_secret_access_key=LOCALSTACK_SECRET_KEY,
            )
        sns_client = boto3.client("sns", **client_kwargs)

        message_payload = {
            "ticket_id": ticket_id,
            "category": category,
            "urgency": urgency,
            "approved_by": role,
            "status": "DISPATCHED_TO_FIELD",
        }

        # Publish (locally via LocalStack, or to real SNS in Ship It mode)
        sns_client.publish(
            TopicArn=SNS_TOPIC_ARN,
            Message=json.dumps(message_payload),
            Subject=f"ALERT: Urgent Ticket Dispatched - {ticket_id}",
        )
        return True
    except Exception as e:
        # Graceful fallback if LocalStack/SNS is not reachable during a demo
        print(f"[SNS offline fallback]: event generated locally for ticket {ticket_id} ({e})")
        return False
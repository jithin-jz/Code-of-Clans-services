import os
import boto3
from botocore.exceptions import ClientError
from datetime import datetime
from django.conf import settings
import logging

DYNAMODB_URL = os.getenv("DYNAMODB_URL", "http://dynamodb:8000")
REGION_NAME = os.getenv("AWS_REGION", "us-west-2")
TABLE_NAME = "Notifications"
logger = logging.getLogger(__name__)

class DynamoNotificationClient:
    def __init__(self):
        self.resource = boto3.resource(
            "dynamodb",
            endpoint_url=DYNAMODB_URL,
            region_name=REGION_NAME,
            aws_access_key_id="dummy",
            aws_secret_access_key="dummy"
        )

    def create_table_if_not_exists(self):
        try:
            tables = [table.name for table in self.resource.tables.all()]
            if TABLE_NAME not in tables:
                self.resource.create_table(
                    TableName=TABLE_NAME,
                    KeySchema=[
                        {'AttributeName': 'user_id', 'KeyType': 'HASH'},  # Partition Key
                        {'AttributeName': 'timestamp', 'KeyType': 'RANGE'} # Sort Key
                    ],
                    AttributeDefinitions=[
                        {'AttributeName': 'user_id', 'AttributeType': 'S'},
                        {'AttributeName': 'timestamp', 'AttributeType': 'S'}
                    ],
                    ProvisionedThroughput={'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
                )
                logger.info("Table %s created.", TABLE_NAME)
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            if error_code == "ResourceInUseException":
                logger.info("Table %s already exists.", TABLE_NAME)
            else:
                logger.exception("Error creating table: %s", e)
        except Exception as e:
            logger.exception("Error creating table: %s", e)

    def save_notification(self, user_id: str, actor_username: str, verb: str, target_info: str = ""):
        try:
            table = self.resource.Table(TABLE_NAME)
            table.put_item(
                Item={
                    'user_id': str(user_id),
                    'timestamp': datetime.utcnow().isoformat(),
                    'actor': actor_username,
                    'verb': verb,
                    'target': target_info
                }
            )
        except Exception as e:
            logger.exception("Error saving notification to DynamoDB: %s", e)

    def get_notifications(self, user_id: str, limit: int = 20):
        try:
            table = self.resource.Table(TABLE_NAME)
            response = table.query(
                KeyConditionExpression=boto3.dynamodb.conditions.Key('user_id').eq(str(user_id)),
                ScanIndexForward=False, # Latest first
                Limit=limit
            )
            return response.get('Items', [])
        except Exception as e:
            logger.exception("Error fetching notifications from DynamoDB: %s", e)
            return []

dynamo_notification_client = DynamoNotificationClient()

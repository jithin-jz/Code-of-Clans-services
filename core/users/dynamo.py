import os
import boto3
from botocore.exceptions import ClientError
from datetime import datetime
import logging

DYNAMODB_URL = os.getenv("DYNAMODB_URL", "http://dynamodb:8000")
REGION_NAME = os.getenv("AWS_REGION", "us-west-2")
TABLE_NAME = "UserActivity"
logger = logging.getLogger(__name__)

class DynamoActivityClient:
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
                        {'AttributeName': 'date', 'KeyType': 'RANGE'}     # Sort Key (YYYY-MM-DD)
                    ],
                    AttributeDefinitions=[
                        {'AttributeName': 'user_id', 'AttributeType': 'S'},
                        {'AttributeName': 'date', 'AttributeType': 'S'}
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

    def log_activity(self, user_id: str):
        """
        Increments the contribution count for the user on the current date.
        """
        try:
            table = self.resource.Table(TABLE_NAME)
            today = datetime.utcnow().strftime('%Y-%m-%d')
            
            table.update_item(
                Key={
                    'user_id': str(user_id),
                    'date': today
                },
                UpdateExpression="ADD contribution_count :inc",
                ExpressionAttributeValues={':inc': 1},
                ReturnValues="UPDATED_NEW"
            )
        except Exception as e:
            logger.exception("Error logging activity to DynamoDB: %s", e)

    def get_contribution_history(self, user_id: str, days: int = 365):
        """
        Fetches contribution history for the last X days.
        """
        try:
            table = self.resource.Table(TABLE_NAME)
            response = table.query(
                KeyConditionExpression=boto3.dynamodb.conditions.Key('user_id').eq(str(user_id)),
                ScanIndexForward=False, # Latest first
                Limit=days
            )
            return response.get('Items', [])
        except Exception as e:
            logger.exception("Error fetching contribution history: %s", e)
            return []

dynamo_activity_client = DynamoActivityClient()

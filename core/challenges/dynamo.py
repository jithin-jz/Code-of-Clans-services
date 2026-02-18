import os
import boto3
from botocore.exceptions import ClientError
from datetime import datetime
import logging

DYNAMODB_URL = os.getenv("DYNAMODB_URL", "http://dynamodb:8000")
REGION_NAME = os.getenv("AWS_REGION", "us-west-2")
TABLE_NAME = "ChallengeProgress"
logger = logging.getLogger(__name__)

class DynamoChallengeClient:
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
                        {'AttributeName': 'challenge_slug', 'KeyType': 'RANGE'} # Sort Key
                    ],
                    AttributeDefinitions=[
                        {'AttributeName': 'user_id', 'AttributeType': 'S'},
                        {'AttributeName': 'challenge_slug', 'AttributeType': 'S'}
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

    def update_progress(self, user_id: str, challenge_slug: str, status: str, stars: int = 0):
        try:
            table = self.resource.Table(TABLE_NAME)
            table.put_item(
                Item={
                    'user_id': str(user_id),
                    'challenge_slug': challenge_slug,
                    'status': status,
                    'stars': stars,
                    'last_updated': datetime.utcnow().isoformat()
                }
            )
        except Exception as e:
            logger.exception("Error updating challenge progress in DynamoDB: %s", e)

    def get_user_progress(self, user_id: str):
        try:
            table = self.resource.Table(TABLE_NAME)
            response = table.query(
                KeyConditionExpression=boto3.dynamodb.conditions.Key('user_id').eq(str(user_id))
            )
            return response.get('Items', [])
        except Exception as e:
            logger.exception("Error fetching challenge progress from DynamoDB: %s", e)
            return []

dynamo_challenge_client = DynamoChallengeClient()

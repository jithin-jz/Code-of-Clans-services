import os
import aioboto3
from botocore.exceptions import ClientError
from datetime import datetime
import logging

# Credentials
DYNAMODB_URL = os.getenv("DYNAMODB_URL", "http://dynamodb:8000")
REGION_NAME = os.getenv("AWS_REGION", "us-west-2")
ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID", "dummy")
SECRET_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "dummy")
TABLE_NAME = "ChatMessages"
logger = logging.getLogger(__name__)

class DynamoClient:
    def __init__(self):
        self.session = aioboto3.Session()
        self.endpoint_url = DYNAMODB_URL
        # Explicit credentials block
        self.creds = {
            "aws_access_key_id": ACCESS_KEY,
            "aws_secret_access_key": SECRET_KEY,
            "region_name": REGION_NAME,
            "endpoint_url": self.endpoint_url
        }

    async def create_table_if_not_exists(self):
        try:
            async with self.session.resource("dynamodb", **self.creds) as dynamo:
                tables = [table.name async for table in dynamo.tables.all()]
                if TABLE_NAME not in tables:
                    await dynamo.create_table(
                        TableName=TABLE_NAME,
                        KeySchema=[
                            {'AttributeName': 'room_id', 'KeyType': 'HASH'},  # Partition Key
                            {'AttributeName': 'timestamp', 'KeyType': 'RANGE'} # Sort Key
                        ],
                        AttributeDefinitions=[
                            {'AttributeName': 'room_id', 'AttributeType': 'S'},
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

    async def save_message(self, room_id: str, sender: str, message: str, user_id: str = None):
        try:
            async with self.session.resource("dynamodb", **self.creds) as dynamo:
                table = await dynamo.Table(TABLE_NAME)
                await table.put_item(
                    Item={
                        'room_id': room_id,
                        'timestamp': datetime.utcnow().isoformat(),
                        'sender': sender,
                        'content': message
                    }
                )
                
                # Log contribution if user_id provided
                if user_id:
                    activity_table = await dynamo.Table("UserActivity")
                    today = datetime.utcnow().strftime('%Y-%m-%d')
                    await activity_table.update_item(
                        Key={'user_id': str(user_id), 'date': today},
                        UpdateExpression="ADD contribution_count :inc",
                        ExpressionAttributeValues={':inc': 1}
                    )
        except Exception as e:
            logger.exception("Error saving message to DynamoDB: %s", e)

    async def get_messages(self, room_id: str, limit: int = 50):
        try:
            async with self.session.resource("dynamodb", **self.creds) as dynamo:
                table = await dynamo.Table(TABLE_NAME)
                response = await table.query(
                    KeyConditionExpression=aioboto3.dynamodb.conditions.Key('room_id').eq(room_id),
                    ScanIndexForward=False, # Get latest first
                    Limit=limit
                )
                return response.get('Items', [])
        except Exception as e:
            logger.exception("Error fetching messages from DynamoDB: %s", e)
            return []

dynamo_client = DynamoClient()

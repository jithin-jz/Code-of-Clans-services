from django.apps import AppConfig


class UsersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "users"

    def ready(self):
        from .dynamo import dynamo_activity_client
        dynamo_activity_client.create_table_if_not_exists()

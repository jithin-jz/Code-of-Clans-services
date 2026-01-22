from django.core.management.base import BaseCommand
from store.models import StoreItem

class Command(BaseCommand):
    help = 'List all store items'

    def handle(self, *args, **kwargs):
        for item in StoreItem.objects.all():
            self.stdout.write(f"{item.id}: {item.name} ({item.category})")

from django.core.management.base import BaseCommand
from store.models import StoreItem

class Command(BaseCommand):
    help = 'Delete dummy store items'

    def handle(self, *args, **kwargs):
        # Delete XP Booster and Code Wizard Badge
        dummy_names = ['XP Booster', 'Code Wizard Badge', 'Test Item', 'Pro Badge']
        deleted_count = 0
        
        for name in dummy_names:
            items = StoreItem.objects.filter(name=name)
            for item in items:
                item.delete()
                deleted_count += 1
                self.stdout.write(self.style.SUCCESS(f"Deleted {name}"))
        
        if deleted_count == 0:
            self.stdout.write("No dummy items found.")

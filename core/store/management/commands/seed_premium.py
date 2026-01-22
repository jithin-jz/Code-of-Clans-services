from django.core.management.base import BaseCommand
from store.models import StoreItem

class Command(BaseCommand):
    help = 'Seed premium store items'

    def handle(self, *args, **kwargs):
        items = [
            # Fonts
            {
                "name": "Fira Code",
                "description": "A monospaced font with programming ligatures.",
                "cost": 100,
                "category": "FONT",
                "icon_name": "Type",
                "item_data": {"font_family": "Fira Code"}
            },
            {
                "name": "Robo Mono",
                "description": "A geometric monospaced font.",
                "cost": 300,
                "category": "FONT",
                "icon_name": "Type",
                "item_data": {"font_family": "Roboto Mono"}
            },
            
            # Effects
            {
                "name": "Fire Cursor",
                "description": "Set your code on fire!",
                "cost": 500,
                "category": "EFFECT",
                "icon_name": "Flame",
                "item_data": {"effect_key": "fire"}
            },
            {
                "name": "Rainbow Particles",
                "description": "Discover the magic of coding.",
                "cost": 500,
                "category": "EFFECT",
                "icon_name": "Sparkles",
                "item_data": {"effect_key": "rainbow"}
            },

            # Victory
            {
                "name": "Fireworks",
                "description": "Celebrate in style with fireworks.",
                "cost": 1000,
                "category": "VICTORY",
                "icon_name": "PartyPopper",
                "item_data": {"victory_key": "fireworks"}
            },
             {
                "name": "Gold Rush",
                "description": "Shower yourself in gold.",
                "cost": 2000,
                "category": "VICTORY",
                "icon_name": "Coins",
                "item_data": {"victory_key": "gold"}
            }
        ]

        for item_data in items:
            item, created = StoreItem.objects.get_or_create(
                name=item_data['name'],
                defaults=item_data
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created {item.name}"))
            else:
                 self.stdout.write(self.style.WARNING(f"{item.name} already exists"))

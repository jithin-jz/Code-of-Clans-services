from django.core.management.base import BaseCommand
from store.models import StoreItem


class Command(BaseCommand):
    help = "Seeds the store with cosmetic items."

    def handle(self, *args, **options):
        self.stdout.write("Seeding Store Items...")

        # Clear existing items (optional)
        StoreItem.objects.all().delete()

        items = [
            # --- THEMES ---
            {
                "name": "Dracula",
                "description": "Dark purple theme inspired by the classic Dracula color scheme.",
                "cost": 100,
                "icon_name": "Palette",
                "category": "THEME",
                "item_data": {
                    "theme_key": "dracula",
                    "colors": {"bg": "#282a36", "accent": "#bd93f9"},
                },
            },
            {
                "name": "Nord",
                "description": "Arctic, north-bluish clean theme with frost accents.",
                "cost": 100,
                "icon_name": "Palette",
                "category": "THEME",
                "item_data": {
                    "theme_key": "nord",
                    "colors": {"bg": "#2e3440", "accent": "#88c0d0"},
                },
            },
            {
                "name": "Monokai",
                "description": "Vibrant theme with warm colors, popular in many editors.",
                "cost": 150,
                "icon_name": "Palette",
                "category": "THEME",
                "item_data": {
                    "theme_key": "monokai",
                    "colors": {"bg": "#272822", "accent": "#f92672"},
                },
            },
            {
                "name": "Solarized Dark",
                "description": "Precision colors for machines and people.",
                "cost": 150,
                "icon_name": "Palette",
                "category": "THEME",
                "item_data": {
                    "theme_key": "solarized_dark",
                    "colors": {"bg": "#002b36", "accent": "#268bd2"},
                },
            },
            {
                "name": "Cyberpunk",
                "description": "Neon pink and cyan for that futuristic vibe.",
                "cost": 200,
                "icon_name": "Palette",
                "category": "THEME",
                "item_data": {
                    "theme_key": "cyberpunk",
                    "colors": {"bg": "#0d0d0d", "accent": "#ff007f"},
                },
            },
            # --- FONTS ---
            {
                "name": "Fira Code",
                "description": "Monospaced font with programming ligatures.",
                "cost": 50,
                "icon_name": "Type",
                "category": "FONT",
                "item_data": {"font_family": "Fira Code"},
            },
            {
                "name": "JetBrains Mono",
                "description": "A typeface made for developers.",
                "cost": 50,
                "icon_name": "Type",
                "category": "FONT",
                "item_data": {"font_family": "JetBrains Mono"},
            },
            {
                "name": "Comic Code",
                "description": "Comic Sans... but for coding. A fun twist!",
                "cost": 75,
                "icon_name": "Type",
                "category": "FONT",
                "item_data": {"font_family": "Comic Neue"},
            },
            {
                "name": "Cascadia Code",
                "description": "Microsoft's modern monospaced font.",
                "cost": 50,
                "icon_name": "Type",
                "category": "FONT",
                "item_data": {"font_family": "Cascadia Code"},
            },
            # --- CURSOR EFFECTS ---
            {
                "name": "Sparkle Trail",
                "description": "Leave a trail of sparkles as you type.",
                "cost": 250,
                "icon_name": "Sparkles",
                "category": "EFFECT",
                "item_data": {"effect_key": "sparkle"},
            },
            {
                "name": "Rainbow Trail",
                "description": "A colorful rainbow follows your cursor.",
                "cost": 300,
                "icon_name": "Rainbow",
                "category": "EFFECT",
                "item_data": {"effect_key": "rainbow"},
            },
            {
                "name": "Matrix Rain",
                "description": "Digital rain effect while coding.",
                "cost": 350,
                "icon_name": "Binary",
                "category": "EFFECT",
                "item_data": {"effect_key": "matrix"},
            },
            # --- VICTORY ANIMATIONS ---
            {
                "name": "Confetti Burst",
                "description": "Celebrate with colorful confetti on level complete!",
                "cost": 200,
                "icon_name": "PartyPopper",
                "category": "VICTORY",
                "item_data": {"victory_key": "confetti"},
            },
            {
                "name": "Fireworks",
                "description": "A spectacular fireworks display on success.",
                "cost": 300,
                "icon_name": "Flame",
                "category": "VICTORY",
                "item_data": {"victory_key": "fireworks"},
            },
            {
                "name": "Level Up!",
                "description": "Classic RPG level-up animation with sound.",
                "cost": 250,
                "icon_name": "TrendingUp",
                "category": "VICTORY",
                "item_data": {"victory_key": "levelup"},
            },
        ]

        for item in items:
            StoreItem.objects.create(**item)
            self.stdout.write(f"  + {item['name']}")

        self.stdout.write(
            self.style.SUCCESS(f"Successfully seeded {len(items)} store items.")
        )

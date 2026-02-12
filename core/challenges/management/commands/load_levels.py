"""
Django Management Command: Load Levels
Loads 53 challenges from levels.py into the database
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from challenges.models import Challenge
from challenges.levels import LEVELS


class Command(BaseCommand):
    help = 'Load 53 levels from levels.py into the database'

    def handle(self, *args, **options):
        self.stdout.write(self.style.HTTP_INFO(f'Loading {len(LEVELS)} levels...'))
        
        created_count = 0
        updated_count = 0

        with transaction.atomic():
            for level_data in LEVELS:
                # Create or update challenge
                challenge, created = Challenge.objects.update_or_create(
                    slug=level_data['slug'],
                    defaults={
                        'title': level_data['title'],
                        'description': level_data['description'],
                        'initial_code': level_data['initial_code'],
                        'test_code': level_data['test_code'],
                        'order': level_data['order'],
                        'xp_reward': level_data['xp_reward'],
                        'target_time_seconds': level_data['target_time_seconds'],
                        'created_for_user': None,  # Global challenge
                    }
                )

                if created:
                    created_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'  ✓ Created: {challenge.title}')
                    )
                else:
                    updated_count += 1
                    self.stdout.write(
                        self.style.WARNING(f'  ↻ Updated: {challenge.title}')
                    )

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 50))
        self.stdout.write(self.style.SUCCESS(f'✓ Levels Loading Complete!'))
        self.stdout.write(self.style.SUCCESS(f'  - Created: {created_count} challenges'))
        self.stdout.write(self.style.SUCCESS(f'  - Updated: {updated_count} challenges'))
        self.stdout.write(self.style.SUCCESS(f'  - Total: {created_count + updated_count} challenges'))
        self.stdout.write(self.style.SUCCESS('=' * 50))

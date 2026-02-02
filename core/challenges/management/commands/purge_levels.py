from django.core.management.base import BaseCommand
from challenges.models import Challenge, Hint, UserProgress, UserCertificate

class Command(BaseCommand):
    help = 'Wipe all challenge-related data for a fresh AI-generated start.'

    def handle(self, *args, **options):
        self.stdout.write("Purging all levels and progress...")
        
        # Order matters for foreign keys
        UserProgress.objects.all().delete()
        Hint.objects.all().delete()
        Challenge.objects.all().delete()
        UserCertificate.objects.all().delete()
        
        self.stdout.write(self.style.SUCCESS("Slate cleaned successfully. Ready for AI Generation."))

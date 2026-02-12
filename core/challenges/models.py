from django.db import models
from django.contrib.auth.models import User
import uuid


class Challenge(models.Model):
    """
    Represents a coding challenge/task.
    """

    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    description = models.TextField(help_text="Markdown supported problem description")
    initial_code = models.TextField(help_text="Starter code for the user")
    test_code = models.TextField(
        help_text="Hidden python code to assert the user solution"
    )
    order = models.IntegerField(default=0, help_text="Order in the campaign level map")
    
    # New Field: created_for_user
    # If null, it is a global level (e.g. Level 1)
    # If set, it is a personalized level for that user only
    created_for_user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name="personalized_challenges")

    xp_reward = models.IntegerField(default=50)
    time_limit = models.IntegerField(
        default=300, help_text="Suggested time in seconds for bonus"
    )
    
    # Star rating target time
    target_time_seconds = models.IntegerField(
        default=600,
        help_text="Target completion time for 3-star rating (10 minutes default)"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        user_str = f" [User: {self.created_for_user.username}]" if self.created_for_user else " [Global]"
        return f"{self.order}. {self.title}{user_str}"



class UserProgress(models.Model):
    """
    Tracks a user's progress on a challenge.
    """

    class Status(models.TextChoices):
        LOCKED = "LOCKED", "Locked"
        UNLOCKED = "UNLOCKED", "Unlocked"
        COMPLETED = "COMPLETED", "Completed"

    user = models.ForeignKey(
        User, related_name="challenge_progress", on_delete=models.CASCADE
    )
    challenge = models.ForeignKey(
        Challenge, related_name="user_progress", on_delete=models.CASCADE
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.LOCKED
    )
    stars = models.IntegerField(default=0, help_text="0-3 stars based on performance")
    ai_hints_purchased = models.IntegerField(
        default=0, help_text="Number of AI hints purchased for this level."
    )
    
    # Time tracking for star rating
    started_at = models.DateTimeField(
        null=True, blank=True,
        help_text="When user first accessed this challenge"
    )
    
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ["user", "challenge"]

    def __str__(self):
        return f"Progress: {self.user.username} - {self.challenge.title} ({self.status})"


class UserCertificate(models.Model):
    """
    Certificate issued when user completes all 53 challenges.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='certificate')
    certificate_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    issued_date = models.DateTimeField(auto_now_add=True)
    certificate_image = models.ImageField(upload_to='certificates/', null=True, blank=True)
    is_valid = models.BooleanField(default=True)
    completion_count = models.IntegerField(help_text="Number of challenges completed when certificate was issued")
    
    class Meta:
        ordering = ['-issued_date']
    
    def __str__(self):
        return f"Certificate for {self.user.username} - {self.certificate_id}"
    
    @property
    def verification_url(self):
        """Generate verification URL for QR code"""
        from django.conf import settings
        base_url = settings.FRONTEND_URL or 'http://localhost:5173'
        return f"{base_url}/verify/{self.certificate_id}"

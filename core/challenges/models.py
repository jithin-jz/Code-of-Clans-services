from django.db import models
from django.contrib.auth.models import User


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
    xp_reward = models.IntegerField(default=50)
    time_limit = models.IntegerField(
        default=300, help_text="Suggested time in seconds for bonus"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return f"{self.order}. {self.title}"


class Hint(models.Model):
    """
    Hints for a specific challenge.
    """

    challenge = models.ForeignKey(
        Challenge, related_name="hints", on_delete=models.CASCADE
    )
    content = models.TextField()
    cost = models.IntegerField(default=10, help_text="XP cost to unlock this hint")
    order = models.IntegerField(default=1, help_text="Sequence of the hint")

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return f"Hint {self.order} for {self.challenge.title}"


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
    ai_assist_used = models.BooleanField(
        default=False, help_text="True if user purchased AI help."
    )
    hints_unlocked = models.ManyToManyField(
        Hint, blank=True, related_name="unlocked_by"
    )
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ["user", "challenge"]

    def __str__(self):
        return f"{self.user.username} - {self.challenge.title} ({self.status})"


import uuid


class UserCertificate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="certificates"
    )
    certificate_image = models.ImageField(upload_to="certificates/")
    issued_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Certificate for {self.user.username}"

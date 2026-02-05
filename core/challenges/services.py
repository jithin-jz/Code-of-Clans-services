from django.utils import timezone
from django.db.models import Max, Q
from .models import Challenge, UserProgress, Hint
from users.models import UserProfile
from xpoint.services import XPService


class ChallengeService:
    """
    Service layer for handling Challenge interactions.
    Encapsulates logic for progression, locking, hints, and submissions.
    """

    @staticmethod
    def get_annotated_challenges(user, queryset=None):
        """
        Returns a list of challenges annotated with status and stars for the given user.
        Handles the implicit locking logic (Next level unlocked only if previous is completed).
        """
        if queryset is None:
            queryset = Challenge.objects.all()

        challenges = queryset.order_by("order")

        # optimized: fetch all progress in one query
        progress_map = {
            p.challenge_id: p for p in UserProgress.objects.filter(user=user)
        }

        results = []
        previous_completed = True  # Level 1 is always unlocked

        for challenge in challenges:
            p = progress_map.get(challenge.id)

            status = UserProgress.Status.LOCKED
            stars = 0

            if p:
                status = p.status
                stars = p.stars

            # Implicit unlocking logic
            if status == UserProgress.Status.LOCKED and previous_completed:
                status = UserProgress.Status.UNLOCKED

            # Prepare data object (similar to what serializer expects)
            # We preserve the model instance but attach dynamic fields
            challenge.user_status = status
            challenge.user_stars = stars

            results.append(challenge)

            # Update flag for next iteration
            previous_completed = status == UserProgress.Status.COMPLETED

        return results

    @staticmethod
    def get_challenge_details(user, challenge):
        """
        Retrieves detailed challenge info including unlocked hints and current status.
        """
        progress, _ = UserProgress.objects.get_or_create(user=user, challenge=challenge)

        # Use annotated list logic to determine if effectively unlocked if record exists but is locked
        # For simplicity, we assume if they can access the detail page, they likely can see it,
        # but strictly we might want to check the previous level here.

        return {
            "status": progress.status,
            "stars": progress.stars,
            "unlocked_hints": progress.hints_unlocked.all(),
            "ai_hints_purchased": progress.ai_hints_purchased,
        }

    @staticmethod
    def process_submission(user, challenge, passed=False):
        """
        Handles success/failure of a code submission.
        """
        if not passed:
            return {"status": "failed"}

        progress, _ = UserProgress.objects.get_or_create(user=user, challenge=challenge)

        # Calculate Stars
        # Calculate Stars
        # Option 3 (Balanced):
        # 0-1 Hints: 3 Stars (First one is free/safe)
        # 2 Hints: 2 Stars
        # 3 Hints: 1 Star
        stars = 3
        
        # Count total hints used (AI + Static) 
        # Assuming we want to treat them cumulatively, or just focus on AI as requested.
        # Let's focus on AI hints mainly but handle static as "1 usage" for simplicity if mixed.
        # For now, strict AI logic as requested:
        
        usage_count = progress.ai_hints_purchased
        
        if usage_count >= 3:
            stars = 1
        elif usage_count == 2:
            stars = 2
        else:
            # 0 or 1 AI hint
            stars = 3
            
            # Fallback: if they used static hints but 0 AI hints, maybe penalize?
            # Existing logic was: strict penalty. 
            # Let's align static hints to be "safe" for the first one too if we want consistency.
            if usage_count == 0 and progress.hints_unlocked.count() > 1:
                 stars = 2
        
        stars = max(1, stars)

        newly_completed = progress.status != UserProgress.Status.COMPLETED

        # Update Progress
        # If already completed, only update if we got more stars?
        # Typically we just keep the best result.
        if newly_completed or stars > progress.stars:
            progress.status = UserProgress.Status.COMPLETED
            progress.completed_at = timezone.now()
            progress.stars = max(progress.stars, stars)
            progress.save()

            # Award XP only on first completion
            xp_earned = 0
            if newly_completed:
                xp_earned = challenge.xp_reward
                XPService.add_xp(user, xp_earned, source="challenge_completion")

            next_slug = ChallengeService._get_next_level_slug(challenge, user)

            return {
                "status": "completed" if newly_completed else "already_completed",
                "xp_earned": xp_earned,
                "stars": stars,
                "next_level_slug": next_slug,
            }

        return {"status": "already_completed", "xp_earned": 0, "stars": progress.stars}

    @staticmethod
    def unlock_hint(user, challenge, hint_order):
        """
        Unlocks a specific hint for a user, deducting XP.
        Raises Hint.DoesNotExist or PermissionError.
        """
        hint = Hint.objects.get(challenge=challenge, order=hint_order)

        progress, _ = UserProgress.objects.get_or_create(user=user, challenge=challenge)

        if progress.hints_unlocked.filter(id=hint.id).exists():
            return hint  # Already unlocked

        if user.profile.xp >= hint.cost:
            XPService.add_xp(user, -hint.cost, source="hint_unlock")
            progress.hints_unlocked.add(hint)
            return hint
        else:
            raise PermissionError("Insufficient XP")

    @staticmethod
    def purchase_ai_assist(user, challenge):
        """
        Purchases the next AI hint level, deducting progressive XP.
        1st hint: 10 XP
        2nd hint: 20 XP
        ...
        """
        progress, _ = UserProgress.objects.get_or_create(
            user=user, challenge=challenge
        )
        
        if progress.ai_hints_purchased >= 3:
            raise PermissionError("Maximum of 3 AI hints allowed for this challenge.")
        
        current_count = progress.ai_hints_purchased
        cost = 10 * (current_count + 1)
        
        if user.profile.xp >= cost:
            XPService.add_xp(user, -cost, source="ai_assist")

            progress.ai_hints_purchased += 1
            progress.save()

            return user.profile.xp
        else:
            raise PermissionError("Insufficient XP")

    @staticmethod
    def create_initial_challenge(user):
        """
        Creates the Level 1 'Hello World' challenge for a new user.
        """
        # Ensure we don't duplicate Level 1 (check both global and user-specific)
        if Challenge.objects.filter(
            Q(created_for_user=user) | Q(created_for_user__isnull=True),
            order=1
        ).exists():
            return None

        challenge = Challenge.objects.create(
            title="Level 1: Hello World",
            slug=f"level-1-hello-world-{user.username}",
            description="Welcome to Clash of Code! Your first task is to print 'Hello, World!' to the console.",
            initial_code="print(\"\")",
            test_code="assert \"Hello, World!\" in output, \"You must print 'Hello, World!'\"",
            order=1,
            created_for_user=user,
            xp_reward=50
        )

        # Create implicit progress record
        UserProgress.objects.get_or_create(
            user=user,
            challenge=challenge,
            defaults={"status": UserProgress.Status.UNLOCKED}
        )

        return challenge

    @staticmethod
    def _get_next_level_slug(current_challenge, user):
        """Get the next level that belongs to this user or is global."""
        next_challenge = (
            Challenge.objects.filter(
                Q(created_for_user__isnull=True) | Q(created_for_user=user),
                order__gt=current_challenge.order
            )
            .order_by("order")
            .first()
        )
        return next_challenge.slug if next_challenge else None

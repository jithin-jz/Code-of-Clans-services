from rest_framework import serializers
from .models import Challenge, UserProgress, UserCertificate


class ChallengeSerializer(serializers.ModelSerializer):
    # Determine status/stars dynamically based on user context if needed,
    # but initially we might just return static data or use a separate serializer for list vs detail.
    class Meta:
        model = Challenge
        fields = [
            "id",
            "title",
            "slug",
            "description",
            "initial_code",
            "test_code",
            "order",
            "xp_reward",
            "time_limit",
            "created_for_user_id",
        ]
    
    created_for_user_id = serializers.IntegerField(write_only=True, required=False)


class UserProgressSerializer(serializers.ModelSerializer):
    challenge_id = serializers.IntegerField(source="challenge.id")

    class Meta:
        model = UserProgress
        fields = ["challenge_id", "status", "stars", "completed_at"]


class UserCertificateSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    verification_url = serializers.CharField(read_only=True)
    
    class Meta:
        model = UserCertificate
        fields = ['id', 'certificate_id', 'username', 'issued_date', 'is_valid', 
                  'completion_count', 'verification_url']
        read_only_fields = ['certificate_id', 'issued_date']

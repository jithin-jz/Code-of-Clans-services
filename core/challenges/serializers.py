from rest_framework import serializers
from .models import Challenge, Hint, UserProgress, UserCertificate

class HintSerializer(serializers.ModelSerializer):
    class Meta:
        model = Hint
        fields = ['id', 'content', 'cost', 'order']

class ChallengeSerializer(serializers.ModelSerializer):
    # Determine status/stars dynamically based on user context if needed, 
    # but initially we might just return static data or use a separate serializer for list vs detail.
    class Meta:
        model = Challenge
        fields = ['id', 'title', 'slug', 'description', 'initial_code', 'test_code', 'order', 'xp_reward', 'time_limit']

class UserProgressSerializer(serializers.ModelSerializer):
    challenge_id = serializers.IntegerField(source='challenge.id')
    
    class Meta:
        model = UserProgress
        fields = ['challenge_id', 'status', 'stars', 'completed_at']

class UserCertificateSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserCertificate
        fields = ['id', 'user', 'certificate_image', 'issued_at']
        read_only_fields = ['id', 'user', 'certificate_image', 'issued_at']

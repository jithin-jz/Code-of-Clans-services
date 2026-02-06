from rest_framework import serializers
from .models import Notification
from users.serializers import UserSummarySerializer

class NotificationSerializer(serializers.ModelSerializer):
    actor = UserSummarySerializer(read_only=True)
    target_preview = serializers.SerializerMethodField()
    
    class Meta:
        model = Notification
        fields = ['id', 'actor', 'verb', 'target_preview', 'is_read', 'created_at']

    def get_target_preview(self, obj):
        # Provide a hint about what was acted on
        if obj.target and hasattr(obj.target, 'image') and obj.target.image:
             request = self.context.get('request')
             if request:
                 return request.build_absolute_uri(obj.target.image.url)
             return obj.target.image.url
        return None

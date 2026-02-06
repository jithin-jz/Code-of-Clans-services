from rest_framework import serializers
from .models import Post
from users.serializers import UserSummarySerializer

class PostSerializer(serializers.ModelSerializer):
    user = UserSummarySerializer(read_only=True)
    is_liked = serializers.SerializerMethodField()
    likes_count = serializers.IntegerField(source='likes.count', read_only=True)
    image_url = serializers.ImageField(source='image', read_only=True)

    class Meta:
        model = Post
        fields = ['id', 'user', 'image', 'image_url', 'caption', 'created_at', 'likes_count', 'is_liked']
        read_only_fields = ['user', 'created_at', 'likes_count', 'image_url']
        extra_kwargs = {
             'image': {'write_only': True} 
        }

    def get_is_liked(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.likes.filter(id=request.user.id).exists()
        return False


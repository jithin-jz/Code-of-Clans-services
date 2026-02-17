from rest_framework import viewsets, permissions, status, mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from auth.throttles import NotificationRateThrottle
from .models import Notification, FCMToken
from .serializers import NotificationSerializer, FCMTokenSerializer

class FCMTokenViewSet(viewsets.ModelViewSet):
    serializer_class = FCMTokenSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return FCMToken.objects.filter(user=self.request.user)

    def create(self, request, *args, **kwargs):
        token = request.data.get('token')
        device_id = request.data.get('device_id')
        
        if not token:
            return Response({"error": "Token is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Use token as the primary lookup to avoid IntegrityError if device_id changes
            fcm_token, created = FCMToken.objects.update_or_create(
                token=token,
                defaults={
                    'user': request.user,
                    'device_id': device_id
                }
            )
            
            serializer = self.get_serializer(fcm_token)
            return Response(serializer.data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class NotificationViewSet(mixins.RetrieveModelMixin,
                          mixins.ListModelMixin,
                          mixins.DestroyModelMixin,
                          viewsets.GenericViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [NotificationRateThrottle]

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user).order_by('-created_at')

    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        self.get_queryset().filter(is_read=False).update(is_read=True)
        return Response({'status': 'marked all read'})

    @action(detail=False, methods=['delete'])
    def clear_all(self, request):
        self.get_queryset().delete()
        return Response({'status': 'cleared all notifications'})

    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        notification.is_read = True
        notification.save()
        return Response({'status': 'marked read'})

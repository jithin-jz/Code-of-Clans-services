from rest_framework import viewsets, status, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from .models import StoreItem, Purchase
from .serializers import StoreItemSerializer
from xpoint.services import XPService

from rest_framework.permissions import IsAuthenticated, IsAdminUser

import os
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile


from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache


@method_decorator(never_cache, name='dispatch')
class StoreItemViewSet(viewsets.ModelViewSet):
    queryset = StoreItem.objects.filter(is_active=True)
    serializer_class = StoreItemSerializer

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsAdminUser()]
        return [IsAuthenticated()]


class PurchaseItemView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk=None):
        item = get_object_or_404(StoreItem, pk=pk, is_active=True)
        user = request.user
        profile = user.profile

        # Check if already purchased (if we enforce unique)
        if Purchase.objects.filter(user=user, item=item).exists():
            return Response(
                {"error": "You already own this item."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if profile.xp < item.cost:
            return Response(
                {"error": f"Insufficient XP. Need {item.cost - profile.xp} more."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Process Transaction using XPService
        XPService.add_xp(
            user,
            -item.cost,
            source="store_purchase",
            description=f"Purchased {item.name}",
        )

        Purchase.objects.create(user=user, item=item)

        return Response(
            {
                "status": "success",
                "message": f"Purchased {item.name}",
                "remaining_xp": profile.xp,
            },
            status=status.HTTP_201_CREATED,
        )


class ImageUploadView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request):
        file_obj = request.FILES.get("image")
        if not file_obj:
            return Response(
                {"error": "No file provided"}, status=status.HTTP_400_BAD_REQUEST
            )

        # Save to media/store/
        directory = os.path.join("store")
        path = default_storage.save(
            os.path.join(directory, file_obj.name), ContentFile(file_obj.read())
        )

        url = os.path.join(settings.MEDIA_URL, path).replace("\\", "/")

        return Response({"url": url}, status=status.HTTP_201_CREATED)


class EquipItemView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        item_id = request.data.get("item_id")
        item = get_object_or_404(StoreItem, pk=item_id, is_active=True)
        user = request.user

        # Verify ownership
        if not Purchase.objects.filter(user=user, item=item).exists():
            return Response(
                {"error": "You do not own this item."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Handle Themes
        if item.category == "THEME":
            theme_key = item.item_data.get("theme_key")
            if not theme_key:
                return Response(
                    {"error": "Invalid theme data."}, status=status.HTTP_400_BAD_REQUEST
                )

            user.profile.active_theme = theme_key
            user.profile.save()
            return Response(
                {
                    "status": "success",
                    "message": f"Equipped {item.name}",
                    "active_theme": theme_key,
                },
                status=status.HTTP_200_OK,
            )

        # Handle Fonts
        if item.category == "FONT":
            font_family = item.item_data.get("font_family")
            if not font_family:
                return Response(
                    {"error": "Invalid font data."}, status=status.HTTP_400_BAD_REQUEST
                )
            user.profile.active_font = font_family
            user.profile.save()
            return Response(
                {
                    "status": "success",
                    "message": f"Equipped {item.name}",
                    "active_font": font_family,
                },
                status=status.HTTP_200_OK,
            )

        # Handle Effects
        if item.category == "EFFECT":
            effect_key = item.item_data.get("effect_key") or item.item_data.get(
                "effect_type"
            )
            if not effect_key:
                return Response(
                    {"error": "Invalid effect data."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            user.profile.active_effect = effect_key
            user.profile.save()
            return Response(
                {
                    "status": "success",
                    "message": f"Equipped {item.name}",
                    "active_effect": effect_key,
                },
                status=status.HTTP_200_OK,
            )

        # Handle Victory
        if item.category == "VICTORY":
            victory_key = item.item_data.get("victory_key") or item.item_data.get(
                "animation_type"
            )
            if not victory_key:
                return Response(
                    {"error": "Invalid victory data."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            user.profile.active_victory = victory_key
            user.profile.save()
            return Response(
                {
                    "status": "success",
                    "message": f"Equipped {item.name}",
                    "active_victory": victory_key,
                },
                status=status.HTTP_200_OK,
            )

        return Response(
            {"error": "This item cannot be equipped."},
            status=status.HTTP_400_BAD_REQUEST,
        )


class UnequipItemView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        category = request.data.get("category")
        user = request.user

        if category == "THEME":
            user.profile.active_theme = "vs-dark"
        elif category == "FONT":
            user.profile.active_font = "Fira Code"
        elif category == "EFFECT":
            user.profile.active_effect = None
        elif category == "VICTORY":
            user.profile.active_victory = "default"
        else:
            return Response(
                {"error": "Invalid category."}, status=status.HTTP_400_BAD_REQUEST
            )

        user.profile.save()
        return Response(
            {"status": "success", "message": f"Unequipped {category}"},
            status=status.HTTP_200_OK,
        )

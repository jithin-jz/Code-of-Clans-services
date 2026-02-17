from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from .models import StoreItem, Purchase
from .serializers import StoreItemSerializer
from xpoint.services import XPService

from rest_framework.permissions import IsAdminUser
from auth.throttles import StoreRateThrottle

import os
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile

from drf_spectacular.utils import extend_schema, OpenApiTypes, inline_serializer
from rest_framework import serializers

from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache


@method_decorator(never_cache, name="dispatch")
class StoreItemViewSet(viewsets.ModelViewSet):
    serializer_class = StoreItemSerializer

    def get_queryset(self):
        # Admin should be able to manage all items, including inactive.
        if self.request.user.is_staff:
            return StoreItem.objects.all().order_by("-created_at")
        return StoreItem.objects.filter(is_active=True).order_by("-created_at")

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsAdminUser()]
        return [IsAuthenticated()]


class PurchaseItemView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [StoreRateThrottle]

    @extend_schema(
        request=None,
        responses={
            201: inline_serializer(
                name="PurchaseResponse",
                fields={
                    "status": serializers.CharField(),
                    "message": serializers.CharField(),
                    "remaining_xp": serializers.IntegerField(),
                },
            ),
            400: OpenApiTypes.OBJECT,
        },
        description="Purchase a store item using XP.",
    )
    def post(self, request, pk=None):
        item = get_object_or_404(StoreItem, pk=pk, is_active=True)
        user = request.user

        # Check if already purchased (if we enforce unique)
        if Purchase.objects.filter(user=user, item=item).exists():
            return Response(
                {"error": "You already own this item."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if user.profile.xp < item.cost:
            return Response(
                {
                    "error": f"Insufficient XP. Need {item.cost - user.profile.xp} more."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Process Transaction using XPService
        remaining_xp = XPService.add_xp(
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
                "remaining_xp": remaining_xp,
                "item": StoreItemSerializer(item, context={"request": request}).data,
            },
            status=status.HTTP_201_CREATED,
        )


class PurchasedItemsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=None,
        responses={200: OpenApiTypes.OBJECT},
        description="Get purchased items and currently equipped cosmetics.",
    )
    def get(self, request):
        purchases = (
            Purchase.objects.select_related("item")
            .filter(user=request.user, item__is_active=True)
            .order_by("-purchased_at")
        )
        items = [p.item for p in purchases]
        serialized_items = StoreItemSerializer(
            items, many=True, context={"request": request}
        ).data

        profile = request.user.profile
        equipped_items = {
            "theme": profile.active_theme,
            "font": profile.active_font,
            "effect": profile.active_effect,
            "victory": profile.active_victory,
        }

        return Response(
            {
                "purchased_items": serialized_items,
                "equipped_items": equipped_items,
            },
            status=status.HTTP_200_OK,
        )


class ImageUploadView(APIView):
    permission_classes = [IsAdminUser]

    @extend_schema(
        request={
            "multipart/form-data": inline_serializer(
                name="ImageUploadRequest",
                fields={
                    "image": serializers.FileField(),
                }
            )
        },
        responses={
            201: inline_serializer(
                name="ImageUploadResponse",
                fields={
                    "url": serializers.CharField(),
                }
            ),
            400: OpenApiTypes.OBJECT,
        },
        description="Upload an image for store items (Admin only).",
    )
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

    @extend_schema(
        request=inline_serializer(
            name="EquipItemRequest",
            fields={
                "item_id": serializers.IntegerField(),
            }
        ),
        responses={
            200: OpenApiTypes.OBJECT,
            400: OpenApiTypes.OBJECT,
        },
        description="Equip a purchased item (theme, font, effect, etc.).",
    )
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

    @extend_schema(
        request=inline_serializer(
            name="UnequipItemRequest",
            fields={
                "category": serializers.ChoiceField(choices=["THEME", "FONT", "EFFECT", "VICTORY"]),
            }
        ),
        responses={
            200: OpenApiTypes.OBJECT,
            400: OpenApiTypes.OBJECT,
        },
        description="Unequip an item/category.",
    )
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

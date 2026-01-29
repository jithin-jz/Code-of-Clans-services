from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    StoreItemViewSet,
    PurchaseItemView,
    ImageUploadView,
    EquipItemView,
    UnequipItemView,
)

router = DefaultRouter()
router.register(r"items", StoreItemViewSet)

urlpatterns = [
    path("buy/<int:pk>/", PurchaseItemView.as_view(), name="store-buy"),
    path("upload/", ImageUploadView.as_view(), name="store-upload"),
    path("equip/", EquipItemView.as_view(), name="store-equip"),
    path("unequip/", UnequipItemView.as_view(), name="store-unequip"),
    path("", include(router.urls)),
]

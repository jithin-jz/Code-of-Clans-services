from django.contrib import admin
from .models import Challenge, Hint, UserProgress


class HintInline(admin.TabularInline):
    model = Hint
    extra = 1


@admin.register(Challenge)
class ChallengeAdmin(admin.ModelAdmin):
    list_display = ("title", "order", "xp_reward", "slug")
    prepopulated_fields = {"slug": ("title",)}
    inlines = [HintInline]
    search_fields = ("title", "description")


@admin.register(UserProgress)
class UserProgressAdmin(admin.ModelAdmin):
    list_display = ("user", "challenge", "status", "stars", "completed_at")
    list_filter = ("status", "stars")
    search_fields = ("user__username", "challenge__title")

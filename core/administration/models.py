from django.db import models
from django.contrib.auth.models import User

class AdminAuditLog(models.Model):
    admin = models.ForeignKey(User, on_delete=models.CASCADE, related_name="admin_actions")
    action = models.CharField(max_length=255)
    target_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="target_of_admin_actions")
    details = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.admin.username} - {self.action} - {self.timestamp}"

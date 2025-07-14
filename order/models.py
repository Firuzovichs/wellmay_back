from django.db import models
import uuid
from users.models import CustomUser

class Order(models.Model):
    PREMIUM_CHOICES = [
        ('Junior', 'Junior'),
        ('Middle', 'Middle'),
        ('Senior', 'Senior'),
    ]
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE)
    order_bot = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    order_bank = models.BigIntegerField(blank=True, null=True) 
    order_bank_uuid = models.UUIDField(blank=True, null=True)
    premium_name = models.CharField(max_length=10, choices=PREMIUM_CHOICES)
    status = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Order {self.order_bot} for User ID {self.user_id}"
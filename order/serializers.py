from rest_framework import serializers
from .models import Order

class OrderResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = [
            'id',
            'order_bot',
            'order_bank',
            'order_bank_uuid',
            'premium_name',
            'status',
            'is_active',
            'created_at',
            'updated_at',
        ]

class OrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = [
            'order_bot',
            'order_bank',
            'order_bank_uuid',
            'premium_name',
            'status',
            'is_active',
        ]
        read_only_fields = ['order_bot', 'status', 'is_active']

    def create(self, validated_data):
        user = self.context['request'].user
        return Order.objects.create(user=user, **validated_data)


class UpdateOrderBankSerializer(serializers.Serializer):
    order_bot = serializers.UUIDField()
    order_bank_uuid = serializers.UUIDField()
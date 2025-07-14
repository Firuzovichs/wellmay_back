from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import CustomUser, UserProfile,Orders


@admin.register(Orders)
class OrdersAdmin(admin.ModelAdmin):
    list_display = ('order_id', 'user', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('order_id', 'user__email')
    readonly_fields = ('order_id', 'created_at')

    # def has_add_permission(self, request):
    #     # Agar buyurtmalar faqat dastur tomonidan yaratilishini istasangiz,
    #     # admin paneldan yangi buyurtma qo'shishni o'chirib qo'yishingiz mumkin
    #     return False

class CustomUserAdmin(BaseUserAdmin):
    list_display = ('email', 'first_name', 'last_name', 'is_staff', 'is_active')
    list_filter = ('is_staff', 'is_active', 'is_superuser')
    search_fields = ('email', 'first_name', 'last_name')
    ordering = ('email',)

    readonly_fields = ('uuid',)  # Faqat ko‘rish uchun uuid

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Shaxsiy maʼlumotlar', {'fields': ('first_name', 'last_name')}),
        ('Ruxsatlar', {'fields': ('is_staff', 'is_active', 'is_superuser', 'groups', 'user_permissions')}),
        ('Muqobil maʼlumotlar', {'fields': ('last_login',)}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'first_name', 'last_name', 'password1', 'password2', 'is_staff', 'is_active'),
        }),
    )

    filter_horizontal = ('groups', 'user_permissions',)



class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'post', 'image', 'reels', 'free', 'premium', 'created_at')
    search_fields = ('user__email',)
    list_filter = ('free', 'premium',)
    readonly_fields = ('created_at', 'updated_at')

admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(UserProfile, UserProfileAdmin)

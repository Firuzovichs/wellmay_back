# Generated by Django 5.2.2 on 2025-07-12 12:11

import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Order',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('order_bot', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('order_bank', models.BigIntegerField(blank=True, null=True)),
                ('order_bank_uuid', models.UUIDField(blank=True, null=True)),
                ('premium_name', models.CharField(choices=[('Junior', 'Junior'), ('Middle', 'Middle'), ('Senior', 'Senior')], max_length=10)),
                ('status', models.BooleanField(default=False)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]

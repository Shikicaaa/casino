# Generated by Django 5.1.6 on 2025-03-23 18:57

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0002_alter_user_options_alter_user_managers_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="balance",
            field=models.FloatField(default=5.0),
        ),
    ]

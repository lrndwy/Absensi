# Generated by Django 5.1 on 2024-10-30 07:38

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Karyawan', '0002_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='karyawan',
            name='telegram_chat_id',
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
    ]

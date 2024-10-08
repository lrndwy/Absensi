# Generated by Django 5.1 on 2024-09-10 03:53

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Siswa',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('nisn', models.CharField(blank=True, max_length=20, null=True, unique=True)),
                ('nama', models.CharField(blank=True, max_length=200, null=True)),
                ('tanggal_lahir', models.DateField(blank=True, null=True)),
                ('alamat', models.TextField(blank=True, null=True)),
                ('telegram_chat_id', models.CharField(blank=True, max_length=20, null=True)),
            ],
        ),
    ]

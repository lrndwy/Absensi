# Generated by Django 5.1 on 2024-11-13 10:53

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0007_tanggal_merah'),
    ]

    operations = [
        migrations.AddField(
            model_name='record_absensi',
            name='terlambat',
            field=models.DurationField(blank=True, null=True),
        ),
    ]

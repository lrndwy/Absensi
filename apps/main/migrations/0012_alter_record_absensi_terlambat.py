# Generated by Django 5.1 on 2024-11-13 11:06

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0011_alter_record_absensi_terlambat'),
    ]

    operations = [
        migrations.AlterField(
            model_name='record_absensi',
            name='terlambat',
            field=models.PositiveIntegerField(default=0),
        ),
    ]
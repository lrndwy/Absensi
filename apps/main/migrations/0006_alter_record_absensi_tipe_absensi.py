# Generated by Django 5.1 on 2024-09-19 06:06

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0005_alter_instalasi_jam_kerja'),
    ]

    operations = [
        migrations.AlterField(
            model_name='record_absensi',
            name='tipe_absensi',
            field=models.CharField(blank=True, choices=[('masuk', 'Masuk'), ('pulang', 'Pulang'), ('sakit', 'Sakit'), ('izin', 'Izin')], max_length=20, null=True),
        ),
    ]

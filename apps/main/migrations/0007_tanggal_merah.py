# Generated by Django 5.1 on 2024-11-13 08:38

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0006_alter_record_absensi_tipe_absensi'),
    ]

    operations = [
        migrations.CreateModel(
            name='tanggal_merah',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nama_acara', models.CharField(blank=True, max_length=200, null=True)),
                ('tanggal', models.DateField(blank=True, null=True)),
                ('keterangan', models.TextField(blank=True, null=True)),
                ('kategori', models.CharField(choices=[('siswa', 'Siswa'), ('guru', 'Guru'), ('karyawan', 'Karyawan'), ('semua', 'Semua')], default='semua', max_length=20)),
            ],
        ),
    ]

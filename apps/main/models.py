from django.contrib.auth.models import AbstractUser
from django.db import models


class Instalasi(models.Model):
    nama_sekolah = models.CharField(max_length=200)
    deskripsi = models.TextField()
    alamat = models.TextField()
    logo = models.ImageField(upload_to='logo/')
    fitur_siswa = models.BooleanField(default=True)
    fitur_guru = models.BooleanField(default=True)
    fitur_karyawan = models.BooleanField(default=True)
    telegram_token = models.CharField(max_length=500, null=True, blank=True)

    def __str__(self):
        return self.nama_sekolah
    
class CustomUser(AbstractUser):
    userid = models.CharField(max_length=200, null=True, blank=True)
    
    def __str__(self):
        return self.username

class jenjang(models.Model):
    id = models.AutoField(primary_key=True)
    nama = models.CharField(max_length=200, null=True, blank=True)
    
    def __str__(self):
        return self.nama
    
class kelas(models.Model):
    id = models.AutoField(primary_key=True)
    nama = models.CharField(max_length=200, null=True, blank=True)
    
    def __str__(self):
        return self.nama
    
class jabatan(models.Model):
    id = models.AutoField(primary_key=True)
    nama = models.CharField(max_length=200, null=True, blank=True)
    
    def __str__(self):
        return self.nama
    
class mata_pelajaran(models.Model):
    id = models.AutoField(primary_key=True)
    nama = models.CharField(max_length=200, null=True, blank=True)
    
    def __str__(self):
        return self.nama
    
class sakit(models.Model):
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    keterangan = models.TextField(null=True, blank=True)
    surat_sakit = models.FileField(upload_to='surat_sakit/', null=True, blank=True)
    
    @property
    def get_userid(self):
        return self.userid
    
    @property
    def get_user(self):
        return self.user
    
    def __str__(self):
        return self.user.username

class izin(models.Model):
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    keterangan = models.TextField(null=True, blank=True)
    
    def __str__(self):
        return self.user.username
    
    @property
    def get_userid(self):
        return self.userid
    
    @property
    def get_user(self):
        return self.user
    
class record_absensi(models.Model):
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    id_izin = models.ForeignKey(izin, on_delete=models.CASCADE, null=True, blank=True)
    id_sakit = models.ForeignKey(sakit, on_delete=models.CASCADE, null=True, blank=True)
    checktime = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=[('hadir', 'Hadir'), ('sakit', 'Sakit'), ('izin', 'Izin')], default='hadir')
    status_verifikasi = models.CharField(max_length=20, choices=[('menunggu', 'Menunggu'), ('diterima', 'Diterima'), ('ditolak', 'Ditolak')], default='menunggu')
    
    def __str__(self):
        return str(self.id)
    
    @property
    def get_userid(self):
        return self.userid
    
    @property
    def get_user(self):
        return self.user
    
    @property
    def get_id_izin(self):
        return self.id_izin
    
    @property
    def get_id_sakit(self):
        return self.id_sakit
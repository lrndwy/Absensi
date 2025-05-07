from django.contrib.auth.models import User
from django.db import models

from apps.main.models import *


# Create your models here.
class Guru(models.Model):
    id = models.AutoField(primary_key=True)
    nuptk = models.CharField(max_length=20, unique=True, null=True, blank=True)
    nama = models.CharField(max_length=200, null=True, blank=True)
    tanggal_lahir = models.DateField(null=True, blank=True)
    alamat = models.TextField(null=True, blank=True)
    jenjang = models.ForeignKey(jenjang, on_delete=models.CASCADE, null=True, blank=True)
    kelas = models.ForeignKey(kelas, on_delete=models.CASCADE, null=True, blank=True)
    mata_pelajaran = models.ForeignKey(mata_pelajaran, on_delete=models.CASCADE, null=True, blank=True)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, null=True, blank=True)
    telegram_chat_id = models.CharField(max_length=20, null=True, blank=True)
    notifikasi_telegram = models.BooleanField(default=False)
    wali_kelas = models.BooleanField(default=False)
    kepala_sekolah = models.BooleanField(default=False)

    
    def __str__(self):
        return self.nama
    
    @property
    def get_userid(self):
        if self.user:
            return self.user.id
        return None
    
    @property
    def get_user(self):
        return self.user
    
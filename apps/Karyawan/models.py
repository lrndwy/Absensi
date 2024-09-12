from django.contrib.auth.models import User
from django.db import models

from apps.main.models import *


# Create your models here.
class Karyawan(models.Model):
    id = models.AutoField(primary_key=True)
    nip = models.CharField(max_length=20, unique=True, null=True, blank=True)
    nama = models.CharField(max_length=200, null=True, blank=True)
    tanggal_lahir = models.DateField(null=True, blank=True)
    alamat = models.TextField(null=True, blank=True)
    jabatan = models.ForeignKey(jabatan, on_delete=models.CASCADE, null=True, blank=True)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, null=True, blank=True)

    
    def __str__(self):
        return self.nama
    
    @property
    def get_userid(self):
        return self.userid
    
    @property
    def get_user(self):
        return self.user
    
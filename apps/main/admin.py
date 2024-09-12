from django.contrib import admin
from django.contrib.auth.models import Group
from unfold.admin import ModelAdmin

from .models import (CustomUser, Instalasi, izin, jabatan, jenjang, kelas,
                     mata_pelajaran, record_absensi, sakit)

admin.site.unregister(Group)


@admin.register(Instalasi)
class InstalasiAdmin(ModelAdmin):
    list_display = ['nama_sekolah', 'deskripsi', 'alamat', 'logo', 'fitur_siswa', 'fitur_guru', 'fitur_karyawan']

@admin.register(CustomUser)
class CustomUserAdmin(ModelAdmin):
    list_display = ['username', 'email', 'userid']
    search_fields = ['username', 'email', 'userid']

@admin.register(jenjang)
class JenjangAdmin(ModelAdmin):
    list_display = ['id', 'nama']
    search_fields = ['nama']

@admin.register(kelas)
class KelasAdmin(ModelAdmin):
    list_display = ['id', 'nama']
    search_fields = ['nama']

@admin.register(jabatan)
class JabatanAdmin(ModelAdmin):
    list_display = ['id', 'nama']
    search_fields = ['nama']

@admin.register(mata_pelajaran)
class MataPelajaranAdmin(ModelAdmin):
    list_display = ['id', 'nama']
    search_fields = ['nama']

@admin.register(sakit)
class SakitAdmin(ModelAdmin):
    list_display = ['id', 'user', 'keterangan']
    search_fields = ['user__username', 'keterangan']

@admin.register(izin)
class IzinAdmin(ModelAdmin):
    list_display = ['id', 'user', 'keterangan']
    search_fields = ['user__username', 'keterangan']

@admin.register(record_absensi)
class RecordAbsensiAdmin(ModelAdmin):
    list_display = ['id', 'user', 'checktime', 'status']
    list_filter = ['status', 'checktime']
    search_fields = ['user__username', 'status']

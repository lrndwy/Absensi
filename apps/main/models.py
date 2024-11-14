from datetime import date, datetime

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
    jam_masuk_siswa = models.TimeField(null=True, blank=True)
    jam_pulang_siswa = models.TimeField(null=True, blank=True)
    jam_masuk_guru = models.TimeField(null=True, blank=True)
    jam_pulang_guru = models.TimeField(null=True, blank=True)
    jam_masuk_karyawan = models.TimeField(null=True, blank=True)
    jam_pulang_karyawan = models.TimeField(null=True, blank=True)
    jam_kerja_karyawan = models.DurationField(null=True, blank=True)
    jam_kerja_guru = models.DurationField(null=True, blank=True)
    jam_sekolah_siswa = models.DurationField(null=True, blank=True)
    
    def save(self, *args, **kwargs):
        if self.jam_masuk_siswa and self.jam_pulang_siswa:
            jam_masuk = datetime.combine(date.today(), self.jam_masuk_siswa)
            jam_pulang = datetime.combine(date.today(), self.jam_pulang_siswa)
            self.jam_sekolah_siswa = jam_pulang - jam_masuk
        if self.jam_masuk_guru and self.jam_pulang_guru:
            jam_masuk = datetime.combine(date.today(), self.jam_masuk_guru)
            jam_pulang = datetime.combine(date.today(), self.jam_pulang_guru)
            self.jam_kerja_guru = jam_pulang - jam_masuk
        if self.jam_masuk_karyawan and self.jam_pulang_karyawan:
            jam_masuk = datetime.combine(date.today(), self.jam_masuk_karyawan)
            jam_pulang = datetime.combine(date.today(), self.jam_pulang_karyawan)
            self.jam_kerja_karyawan = jam_pulang - jam_masuk
        super().save(*args, **kwargs)

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
    tipe_absensi = models.CharField(max_length=20, choices=[('masuk', 'Masuk'), ('pulang', 'Pulang'), ('sakit', 'Sakit'), ('izin', 'Izin')], null=True, blank=True)
    terlambat = models.PositiveIntegerField(default=0)
    
    def save(self, *args, **kwargs):
        if self.status == 'sakit':
            self.tipe_absensi = 'sakit'
            self.terlambat = 0
        elif self.status == 'izin':
            self.tipe_absensi = 'izin'
            self.terlambat = 0
        elif self.status == 'hadir' and self.tipe_absensi == 'masuk':
            try:
                instalasi = Instalasi.objects.first()
                if not instalasi or not instalasi.jam_masuk or not self.checktime:
                    print("Debug - Instalasi atau jam masuk tidak ada atau waktu absen tidak ada")
                    self.terlambat = 0
                else:
                    # Ambil jam dan menit dari waktu absen
                    jam_absen = self.checktime.hour
                    menit_absen = self.checktime.minute
                    
                    # Ambil jam dan menit dari jam masuk yang ditentukan
                    jam_seharusnya = instalasi.jam_masuk.hour
                    menit_seharusnya = instalasi.jam_masuk.minute
                    
                    # Hitung total menit
                    total_menit_absen = (jam_absen * 60) + menit_absen
                    total_menit_seharusnya = (jam_seharusnya * 60) + menit_seharusnya
                    
                    # Hitung selisih
                    selisih_menit = total_menit_absen - total_menit_seharusnya
                    
                    # Simpan keterlambatan
                    self.terlambat = max(0, selisih_menit)
                    
                    print(f"Debug - Jam Masuk: {instalasi.jam_masuk}")
                    print(f"Debug - Waktu Absen: {self.checktime}")
                    print(f"Debug - Terlambat: {self.terlambat} menit")
            
            except Exception as e:
                print(f"Error: {str(e)}")
                self.terlambat = 0
        else:
            print(f"Debug - Status: {self.status}, Tipe Absensi: {self.tipe_absensi}")
            self.terlambat = 0
            
        super().save(*args, **kwargs)
        
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
      
class tanggal_merah(models.Model):
    nama_acara = models.CharField(max_length=200, null=True, blank=True)
    tanggal = models.DateField(null=True, blank=True)
    keterangan = models.TextField(null=True, blank=True)
    kategori = models.CharField(max_length=20, choices=[('siswa', 'Siswa'), ('guru', 'Guru'), ('karyawan', 'Karyawan'), ('semua', 'Semua')], default='semua')
    
    def __str__(self):
        return self.nama_acara

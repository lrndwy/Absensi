from datetime import date, datetime

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError


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
    akun_ortu = models.BooleanField(default=False)
    
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
    mesin = models.CharField(max_length=255, null=True, blank=True)
    
    def save(self, *args, **kwargs):
        from django.utils import timezone
        from django.core.exceptions import ValidationError
        
        try:
            # Ambil tanggal dari checktime atau gunakan tanggal hari ini
            if isinstance(self.checktime, str):
                try:
                    # Coba format ISO (YYYY-MM-DDTHH:MM)
                    naive_datetime = timezone.datetime.strptime(self.checktime, "%Y-%m-%dT%H:%M")
                    # Tambahkan timezone
                    self.checktime = timezone.make_aware(naive_datetime)
                except ValueError:
                    try:
                        # Coba format standard (YYYY-MM-DD HH:MM:SS)
                        naive_datetime = timezone.datetime.strptime(self.checktime, "%Y-%m-%d %H:%M:%S")
                        self.checktime = timezone.make_aware(naive_datetime)
                    except ValueError:
                        try:
                            # Format ISO dengan detik (YYYY-MM-DDTHH:MM:SS)
                            naive_datetime = timezone.datetime.strptime(self.checktime, "%Y-%m-%dT%H:%M:%S")
                            self.checktime = timezone.make_aware(naive_datetime)
                        except ValueError as e:
                            raise ValidationError(f"Format tanggal tidak valid: {str(e)}")
            
            current_date = timezone.localtime(self.checktime if self.checktime else timezone.now()).date()
            
            # Cek record yang sudah ada untuk user yang sama pada tanggal yang sama
            existing_records = record_absensi.objects.filter(
                user=self.user,
                checktime__year=current_date.year,
                checktime__month=current_date.month,
                checktime__day=current_date.day
            )
            
            # Jika ini adalah record baru
            if not self.id:
                existing_types = existing_records.values_list('tipe_absensi', flat=True)
                existing_status = existing_records.values_list('status', flat=True)
                
                # Jika sudah ada record dengan status izin atau sakit
                if 'izin' in existing_status:
                    raise ValidationError('Sudah ada record izin untuk hari ini')
                elif 'sakit' in existing_status:
                    raise ValidationError('Sudah ada record sakit untuk hari ini')
                    
                # Validasi untuk status hadir
                if self.status == 'hadir':
                    if self.tipe_absensi == 'masuk':
                        if 'masuk' in existing_types:
                            raise ValidationError('Sudah melakukan absensi masuk hari ini')
                    elif self.tipe_absensi == 'pulang':
                        if 'pulang' in existing_types:
                            raise ValidationError('Sudah melakukan absensi pulang hari ini')
                        if 'masuk' not in existing_types:
                            raise ValidationError('Harus melakukan absensi masuk terlebih dahulu')
                        
                # Validasi untuk status izin atau sakit
                elif self.status in ['izin', 'sakit']:
                    if existing_records.exists():
                        raise ValidationError(f'Sudah ada record absensi untuk hari ini, tidak bisa menambah {self.status}')

            # Lanjutkan dengan logika save yang sudah ada
            if self.status == 'sakit':
                self.tipe_absensi = 'sakit'
                self.terlambat = 0
            elif self.status == 'izin':
                self.tipe_absensi = 'izin'
                self.terlambat = 0
            elif self.status == 'hadir':
              pass
                # if self.tipe_absensi == 'masuk':
                    # try:
                    #     instalasi = Instalasi.objects.first()
                    #     if not instalasi or not self.checktime:
                    #         print("Debug - Instalasi atau waktu absen tidak ada")
                    #         self.terlambat = 0
                    #     else:
                    #         # Konversi waktu absen ke waktu lokal
                    #         local_checktime = timezone.localtime(self.checktime)
                            
                    #         # Tentukan jam masuk berdasarkan tipe user
                    #         if hasattr(self.user, 'siswa'):
                    #             jam_masuk = instalasi.jam_masuk_siswa
                    #         elif hasattr(self.user, 'guru'):
                    #             jam_masuk = instalasi.jam_masuk_guru
                    #         elif hasattr(self.user, 'karyawan'):
                    #             jam_masuk = instalasi.jam_masuk_karyawan
                    #         else:
                    #             print("Debug - Tipe user tidak dikenali")
                    #             self.terlambat = 0
                    #             super().save(*args, **kwargs)
                    #             return

                    #         if not jam_masuk:
                    #             print(f"Debug - Jam masuk tidak ditemukan untuk user type: {self.user}")
                    #             self.terlambat = 0
                    #         else:
                    #             # Ambil jam dan menit dari waktu absen
                    #             waktu_absen = local_checktime.time()
                                
                    #             # Hitung selisih dalam menit
                    #             selisih_menit = (
                    #                 waktu_absen.hour * 60 + waktu_absen.minute
                    #             ) - (
                    #                 jam_masuk.hour * 60 + jam_masuk.minute
                    #             )
                                
                    #             # Set keterlambatan (minimal 0 menit)
                    #             self.terlambat = max(0, selisih_menit)
                                
                    #             print(f"Debug - Jam Masuk: {jam_masuk}")
                    #             print(f"Debug - Waktu Absen: {waktu_absen}")
                    #             print(f"Debug - Terlambat: {self.terlambat} menit")

                    # except Exception as e:
                    #     print(f"Error dalam perhitungan keterlambatan: {str(e)}")
                    #     self.terlambat = 0
                    #  
                # else:
                #     print(f"Debug - Status: {self.status}, Tipe Absensi: {self.tipe_absensi}")
                
            super().save(*args, **kwargs)
            
        except Exception as e:
            print(f"Error dalam proses save: {str(e)}")
            raise ValidationError(f"Terjadi kesalahan: {str(e)}")
        
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

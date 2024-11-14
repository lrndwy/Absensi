from django.urls import path

from apps.CustomAdmin import views as admin
from apps.Guru import views as guru
from apps.Karyawan import views as karyawan
from apps.main import views as main
from apps.Siswa import views as siswa

urlpatterns = [
    # Main
    path('', main.instalasi, name='instalasi'),
    path('login/', main.login_view, name='login_view'),
    path('logout/', main.logout_view, name='logout_view'),
    path('webhook/kehadiran/', main.webhook_kehadiran, name='webhook_kehadiran'),
    
    # CustomAdmin
    path('dashboard/', admin.admin_dashboard, name='admin_dashboard'),
    path('dashboard/absensi/siswa/', admin.admin_dashboard_absensi_siswa, name='admin_dashboard_absensi_siswa'),
    path('dashboard/absensi/guru/', admin.admin_dashboard_absensi_guru, name='admin_dashboard_absensi_guru'),
    path('dashboard/absensi/karyawan/', admin.admin_dashboard_absensi_karyawan, name='admin_dashboard_absensi_karyawan'),
    path('dashboard/siswa/', admin.admin_siswa, name='admin_siswa'),
    path('dashboard/guru/', admin.admin_guru, name='admin_guru'),
    path('dashboard/karyawan/', admin.admin_karyawan, name='admin_karyawan'),
    path('dashboard/atribut/', admin.admin_atribut, name='admin_atribut'),
    path('dashboard/sakit/', admin.admin_sakit, name='admin_sakit'),
    path('dashboard/izin/', admin.admin_izin, name='admin_izin'),
    path('dashboard/tanggal-merah/', admin.admin_tanggal_merah, name='admin_tanggal_merah'),
    
    path('dashboard/atribut/kelas/', admin.admin_atribut_kelas, name='admin_atribut_kelas'),
    path('dashboard/atribut/mapel/', admin.admin_atribut_mapel, name='admin_atribut_mapel'),
    path('dashboard/atribut/jabatan/', admin.admin_atribut_jabatan, name='admin_atribut_jabatan'),
    path('dashboard/atribut/jenjang/', admin.admin_atribut_jenjang, name='admin_atribut_jenjang'),
    
    path('dashboard/sakit/siswa/', admin.admin_sakit_siswa, name='admin_sakit_siswa'),
    path('dashboard/sakit/guru/', admin.admin_sakit_guru, name='admin_sakit_guru'),
    path('dashboard/sakit/karyawan/', admin.admin_sakit_karyawan, name='admin_sakit_karyawan'),
    
    path('dashboard/izin/siswa/', admin.admin_izin_siswa, name='admin_izin_siswa'),
    path('dashboard/izin/guru/', admin.admin_izin_guru, name='admin_izin_guru'),
    path('dashboard/izin/karyawan/', admin.admin_izin_karyawan, name='admin_izin_karyawan'),
    
    path('dashboard/pengaturan/', admin.admin_pengaturan, name='admin_pengaturan'),
    path('dashboard/verifikasi/', admin.admin_verifikasi, name='admin_verifikasi'),
    # Siswa
    path('siswa/', siswa.siswa_dashboard, name='siswa_dashboard'),
    path('siswa/statistik/', siswa.siswa_statistik, name='siswa_statistik'),
    path('siswa/pengaturan/', siswa.siswa_pengaturan, name='siswa_pengaturan'),
    
    # Guru
    path('guru/', guru.guru_dashboard, name='guru_dashboard'),
    path('guru/statistik/', guru.guru_statistik, name='guru_statistik'),
    path('guru/pengaturan/', guru.guru_pengaturan, name='guru_pengaturan'),
    # Karyawan
    path('karyawan/', karyawan.karyawan_dashboard, name='karyawan_dashboard'),
    path('karyawan/statistik/', karyawan.karyawan_statistik, name='karyawan_statistik'),
    path('karyawan/pengaturan/', karyawan.karyawan_pengaturan, name='karyawan_pengaturan'),
    # Export Data
    path('export/', main.export_data, name='export_data'),
]

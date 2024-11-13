import json
import os
from datetime import date, datetime, timedelta

import pandas as pd
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
# Create your views here.
from django.contrib.auth.decorators import user_passes_test
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db.models import Count, OuterRef, Q, Subquery
from django.db.models.functions import Coalesce, TruncDate
from django.shortcuts import get_object_or_404, redirect, render
from django.templatetags.static import static
from django.urls import reverse
from django.utils import timezone

from apps.CustomAdmin.functions import *

from apps.Guru.models import *
from apps.Karyawan.models import *
from apps.main.instalasi import cek_instalasi, get_context
from apps.main.models import *
from apps.main.models import CustomUser, izin, jenjang, kelas
from apps.Siswa.models import *

@cek_instalasi
@superuser_required
def admin_pengaturan(request):
    try:
        instalasi = Instalasi.objects.first()
        
        if request.method == 'POST':
            if request.POST.get('action') == 'reset':
                # Menghapus semua data dari database
                try:
                    # Hapus semua data dari model-model yang ada
                    CustomUser.objects.all().delete()
                    Siswa.objects.all().delete()
                    Guru.objects.all().delete()
                    Karyawan.objects.all().delete()
                    record_absensi.objects.all().delete()
                    izin.objects.all().delete()
                    sakit.objects.all().delete()
                    jenjang.objects.all().delete()
                    kelas.objects.all().delete()
                    mata_pelajaran.objects.all().delete()
                    jabatan.objects.all().delete()
                    Instalasi.objects.all().delete()
                    
                    # Hapus semua file media yang diupload
                    import os
                    import shutil

                    from django.conf import settings
                    
                    media_root = settings.MEDIA_ROOT
                    if os.path.exists(media_root):
                        for root, dirs, files in os.walk(media_root):
                            for file in files:
                                os.remove(os.path.join(root, file))
                            for dir in dirs:
                                shutil.rmtree(os.path.join(root, dir))
                    
                    messages.success(request, 'Semua data berhasil dihapus dari database.')
                except Exception as e:
                    messages.error(request, f'Terjadi kesalahan saat menghapus data: {str(e)}')
                messages.success(request, 'Website berhasil direset.')
                return redirect('login_view')
            elif request.POST.get('nama_sekolah'):
                try:
                    nama_sekolah = request.POST.get('nama_sekolah')
                    deskripsi = request.POST.get('deskripsi')
                    alamat = request.POST.get('alamat')
                    logo = request.FILES.get('logo')
                    fitur_siswa = request.POST.get('fitur_siswa') == 'on'
                    fitur_guru = request.POST.get('fitur_guru') == 'on'
                    fitur_karyawan = request.POST.get('fitur_karyawan') == 'on'
                    telegram_token = request.POST.get('telegram_token')
                    jam_masuk = request.POST.get('jam_masuk')
                    jam_pulang = request.POST.get('jam_pulang')
                    if instalasi:
                        instalasi.nama_sekolah = nama_sekolah
                        instalasi.deskripsi = deskripsi
                        instalasi.alamat = alamat
                        if logo:
                            instalasi.logo = logo
                            messages.success(request, 'Logo berhasil diperbarui.')
                        instalasi.fitur_siswa = fitur_siswa
                        instalasi.fitur_guru = fitur_guru
                        instalasi.fitur_karyawan = fitur_karyawan
                        instalasi.telegram_token = telegram_token
                        
                        if jam_masuk and jam_pulang:
                            try:
                                jam_masuk_time = datetime.strptime(jam_masuk, '%H:%M').time()
                                jam_pulang_time = datetime.strptime(jam_pulang, '%H:%M').time()
                                
                                instalasi.jam_masuk = jam_masuk_time
                                instalasi.jam_pulang = jam_pulang_time
                            except ValueError:
                                messages.error(request, 'Format jam tidak valid. Gunakan format HH:MM.')
                        
                        instalasi.save()
                        messages.success(request, 'Pengaturan berhasil diperbarui.')
                        
                        if fitur_siswa:
                            messages.info(request, 'Fitur siswa diaktifkan.')
                        else:
                            messages.info(request, 'Fitur siswa dinonaktifkan.')
                        
                        if fitur_guru:
                            messages.info(request, 'Fitur guru diaktifkan.')
                        else:
                            messages.info(request, 'Fitur guru dinonaktifkan.')
                        
                        if fitur_karyawan:
                            messages.info(request, 'Fitur karyawan diaktifkan.')
                        else:
                            messages.info(request, 'Fitur karyawan dinonaktifkan.')
                    else:
                        messages.error(request, 'Data instalasi tidak ditemukan.')
                except Exception as e:
                    messages.error(request, f'Terjadi kesalahan saat memperbarui pengaturan: {str(e)}')
                
                return redirect('admin_pengaturan')

        context = get_context()
        context.update({
            'instalasi': instalasi,
            'logoimage': instalasi.logo.url if instalasi.logo else static('images/example_logo.png'),
            'nama_sekolah': instalasi.nama_sekolah,
            'alamat': instalasi.alamat,
            'deskripsi': instalasi.deskripsi,
            'fitur_siswa': instalasi.fitur_siswa,
            'fitur_guru': instalasi.fitur_guru,
            'fitur_karyawan': instalasi.fitur_karyawan,
            'telegram_token': instalasi.telegram_token,
            'jam_masuk': instalasi.jam_masuk.strftime('%H:%M') if instalasi.jam_masuk else '',
            'jam_pulang': instalasi.jam_pulang.strftime('%H:%M') if instalasi.jam_pulang else '',
        })
        return render(request, 'CustomAdmin/admin_pengaturan.html', context)
    except Exception as e:
        messages.error(request, f'Terjadi kesalahan pada sistem: {str(e)}')
        return redirect('admin_pengaturan')

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
def admin_verifikasi(request):
    try:
        record_absensi_list = record_absensi.objects.filter(status_verifikasi='menunggu')
        
        edit_data_verifikasi = None
        edit_id = request.GET.get('id')
        if edit_id:
            data_record = record_absensi.objects.filter(id=edit_id).first()
            if data_record:
                edit_data_verifikasi = {
                    'id': data_record.id,
                    'username': data_record.user.username,
                    'entitas': 'Siswa' if Siswa.objects.filter(user=data_record.user).exists() else 'Guru' if Guru.objects.filter(user=data_record.user).exists() else 'Karyawan',
                    'nama': Siswa.objects.get(user=data_record.user).nama if Siswa.objects.filter(user=data_record.user).exists() else Guru.objects.get(user=data_record.user).nama if Guru.objects.filter(user=data_record.user).exists() else Karyawan.objects.get(user=data_record.user).nama,
                    'status': data_record.status,
                    'checktime': timezone.localtime(data_record.checktime).strftime('%Y-%m-%d %H:%M:%S'),
                }
                if data_record.status == 'sakit':
                    edit_data_verifikasi['id_sakit'] = data_record.id_sakit.id if data_record.id_sakit else None
                    edit_data_verifikasi['surat_sakit'] = data_record.id_sakit.surat_sakit.url if data_record.id_sakit and data_record.id_sakit.surat_sakit else None  
                    edit_data_verifikasi['keterangan'] = data_record.id_sakit.keterangan if data_record.id_sakit else None
                elif data_record.status == 'izin':
                    edit_data_verifikasi['id_izin'] = data_record.id_izin.id if data_record.id_izin else None
                    edit_data_verifikasi['keterangan'] = data_record.id_izin.keterangan if data_record.id_izin else None
                
                messages.info(request, 'Data absensi berhasil dimuat untuk diverifikasi.')
            else:
                messages.error(request, 'Data absensi tidak ditemukan.')
        
        if request.method == 'POST':
            action = request.POST.get('action')
            if action == 'verifikasi':
                id_record = request.POST.get('id')
                record = record_absensi.objects.get(id=id_record)
                record.status_verifikasi = 'diterima'
                checktime = request.POST.get('checktime')
                if checktime:
                    record.checktime = datetime.strptime(checktime, '%Y-%m-%d %H:%M:%S')
                record.save()
                messages.success(request, 'Data berhasil diverifikasi.')
                return redirect('admin_verifikasi')
        
        table_data = []
        for record in record_absensi_list:
            entitas = ''
            nama = ''
            if Siswa.objects.filter(user=record.user).exists():
                entitas = 'Siswa'
                nama = Siswa.objects.get(user=record.user).nama
            elif Guru.objects.filter(user=record.user).exists():
                entitas = 'Guru'
                nama = Guru.objects.get(user=record.user).nama
            elif Karyawan.objects.filter(user=record.user).exists():
                entitas = 'Karyawan'
                nama = Karyawan.objects.get(user=record.user).nama

            table_data.append([
                record.id,
                record.user.username,
                entitas,
                nama,
                record.status,
                timezone.localtime(record.checktime).strftime('%Y-%m-%d %H:%M:%S'),
                record.status_verifikasi,
            ])


        if not table_data:
            messages.info(request, 'Tidak ada data absensi yang perlu diverifikasi.')
        else:
            messages.info(request, f'Terdapat {len(table_data)} data absensi yang perlu diverifikasi.')

        context = get_context()
        context.update({
            'table_columns': ['ID Record', 'Username', 'Entitas', 'Nama', 'Status', 'Waktu', 'Status Verifikasi'],
            'table_data': table_data,
            'total_data_table': len(table_data),
            'verifikasi': True,
            'edit_data_verifikasi': edit_data_verifikasi,
            'status_verifikasi_list': ['menunggu', 'diterima', 'ditolak'],
        })
        return render(request, 'CustomAdmin/admin_verifikasi.html', context)
    except Exception as e:
        messages.error(request, f'Terjadi kesalahan pada sistem: {str(e)}')
        return redirect('admin_verifikasi')

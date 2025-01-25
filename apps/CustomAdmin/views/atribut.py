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
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from apps.CustomAdmin.functions import *

from apps.Guru.models import *
from apps.Karyawan.models import *
from apps.main.instalasi import cek_instalasi, get_context
from apps.main.models import *
from apps.main.models import CustomUser, izin, jenjang, kelas
from apps.Siswa.models import *




@cek_instalasi
@superuser_required
def admin_atribut(request):
    try:
        context = get_context()
        context.update({
            
        })
        return render(request, 'CustomAdmin/admin_atribut.html', context)
    except Exception as e:
        messages.error(request, f'Terjadi kesalahan pada sistem: {str(e)}')
        return redirect('admin_atribut')

@cek_instalasi
@superuser_required
def admin_atribut_kelas(request):
    try:
        edit_data_atribut_kelas = []
        edit_id = request.GET.get('id')
        if edit_id:
            try:
                data_kelas = kelas.objects.filter(id=edit_id).first()
                if data_kelas:
                    edit_data_atribut_kelas.append({
                        'id': data_kelas.id,
                        'nama_kelas': data_kelas.nama,
                    })
            except Exception as e:
                messages.error(request, f'Gagal mengambil data kelas: {str(e)}')
                return redirect('admin_atribut_kelas')
        
        if request.method == 'POST':
            try:
                action = request.POST.get('action')
                if action == 'tambah':
                    nama = request.POST.get('nama_kelas')
                    kelas.objects.create(nama=nama)
                    messages.success(request, 'Kelas berhasil ditambahkan.')
                elif action == 'edit':
                    id_kelas = request.POST.get('id')
                    nama = request.POST.get('nama_kelas')
                    kelas.objects.filter(id=id_kelas).update(nama=nama)
                    messages.success(request, 'Kelas berhasil diperbarui.')
                elif action == 'hapus':
                    selected_ids = request.POST.getlist('selectedIds')
                    ids_to_delete = []
                    for selected_id in selected_ids:
                        ids_to_delete.extend(selected_id.split(','))
                    kelas.objects.filter(id__in=ids_to_delete).delete()
                    messages.success(request, 'Kelas berhasil dihapus.')
            except Exception as e:
                messages.error(request, f'Gagal memproses aksi: {str(e)}')
                return redirect('admin_atribut_kelas')
            
            return redirect('admin_atribut_kelas')
            
        try:
            kelas_list = kelas.objects.all()
            
            table_data = [
                [kelas.id, kelas.nama]
                for kelas in kelas_list
            ]
            context = get_context()
            context.update({
                'table_columns': ['ID', 'Nama'],
                'table_data': table_data,
                'edit_data_atribut_kelas': edit_data_atribut_kelas,
                'kelas': True,
                'total_data_table': kelas_list.count(),
                'API_LINK': reverse('api_kelas'),
            })
            return render(request, 'CustomAdmin/admin_atribut_kelas.html', context)
        except Exception as e:
            messages.error(request, f'Gagal memuat data: {str(e)}')
            return redirect('admin_atribut_kelas')
            
    except Exception as e:
        messages.error(request, f'Terjadi kesalahan pada sistem: {str(e)}')
        return redirect('admin_atribut_kelas')

@cek_instalasi
@superuser_required
def admin_atribut_mapel(request):
    try:
        edit_data_atribut_mapel = []
        edit_id = request.GET.get('id')
        if edit_id:
            try:
                data_mapel = mata_pelajaran.objects.filter(id=edit_id).first()
                if data_mapel:
                    edit_data_atribut_mapel.append({
                        'id': data_mapel.id,
                        'nama_mapel': data_mapel.nama,
                    })
            except Exception as e:
                messages.error(request, f'Gagal memuat data edit: {str(e)}')
                return redirect('admin_atribut_mapel')
        
        if request.method == 'POST':
            try:
                action = request.POST.get('action')
                if action == 'tambah':
                    nama = request.POST.get('nama_mapel')
                    mata_pelajaran.objects.create(nama=nama)
                    messages.success(request, 'Mata pelajaran berhasil ditambahkan.')
                elif action == 'edit':
                    id_mapel = request.POST.get('id')
                    nama = request.POST.get('nama_mapel')
                    mata_pelajaran.objects.filter(id=id_mapel).update(nama=nama)
                    messages.success(request, 'Mata pelajaran berhasil diperbarui.')
                elif action == 'hapus':
                    selected_ids = request.POST.getlist('selectedIds')
                    ids_to_delete = []
                    for selected_id in selected_ids:
                        ids_to_delete.extend(selected_id.split(','))
                    mata_pelajaran.objects.filter(id__in=ids_to_delete).delete()
                    messages.success(request, 'Mata pelajaran berhasil dihapus.')
            except Exception as e:
                messages.error(request, f'Gagal memproses aksi: {str(e)}')
                return redirect('admin_atribut_mapel')
            
            return redirect('admin_atribut_mapel')
            
        try:
            mapel_list = mata_pelajaran.objects.all()
            
            table_data = [
                [mapel.id, mapel.nama]
                for mapel in mapel_list
            ]
            context = get_context()
            context.update({
                'table_columns': ['ID', 'Nama'],
                'table_data': table_data,
                'edit_data_atribut_mapel': edit_data_atribut_mapel,
                'mapel': True,
                'total_data_table': mapel_list.count(),
                'API_LINK': reverse('api_mapel'),
            })
            return render(request, 'CustomAdmin/admin_atribut_mapel.html', context)
        except Exception as e:
            messages.error(request, f'Gagal memuat data: {str(e)}')
            return redirect('admin_atribut_mapel')
            
    except Exception as e:
        messages.error(request, f'Terjadi kesalahan pada sistem: {str(e)}')
        return redirect('admin_atribut_mapel')

@cek_instalasi
@superuser_required
def admin_atribut_jabatan(request):
    try:
        edit_data_atribut_jabatan = []
        edit_id = request.GET.get('id')
        if edit_id:
            try:
                data_jabatan = jabatan.objects.filter(id=edit_id).first()
                if data_jabatan:
                    edit_data_atribut_jabatan.append({
                        'id': data_jabatan.id,
                        'nama_jabatan': data_jabatan.nama,
                    })
            except Exception as e:
                messages.error(request, f'Gagal mengambil data jabatan: {str(e)}')
                return redirect('admin_atribut_jabatan')
        
        if request.method == 'POST':
            try:
                action = request.POST.get('action')
                if action == 'tambah':
                    nama = request.POST.get('nama_jabatan')
                    jabatan.objects.create(nama=nama)
                    messages.success(request, 'Jabatan berhasil ditambahkan.')
                elif action == 'edit':
                    id_jabatan = request.POST.get('id')
                    nama = request.POST.get('nama_jabatan')
                    jabatan.objects.filter(id=id_jabatan).update(nama=nama)
                    messages.success(request, 'Jabatan berhasil diperbarui.')
                elif action == 'hapus':
                    selected_ids = request.POST.getlist('selectedIds')
                    # Menangani kasus di mana selectedIds berisi string dengan beberapa ID
                    all_ids = []
                    for id_string in selected_ids:
                        all_ids.extend(id_string.split(','))
                    
                    jabatan.objects.filter(id__in=all_ids).delete()
                    messages.success(request, 'Jabatan berhasil dihapus.')
            except Exception as e:
                messages.error(request, f'Gagal memproses aksi: {str(e)}')
                return redirect('admin_atribut_jabatan')
            
            return redirect('admin_atribut_jabatan')
            
        try:
            jabatan_list = jabatan.objects.all()
            
            table_data = [
                [jab.id, jab.nama]
                for jab in jabatan_list
            ]
            context = get_context()
            context.update({
                'table_columns': ['ID', 'Nama'],
                'table_data': table_data,
                'edit_data_atribut_jabatan': edit_data_atribut_jabatan,
                'jabatan': True,
                
                'total_data_table': jabatan_list.count(),
                'API_LINK': reverse('api_jabatan'),
            })
            return render(request, 'CustomAdmin/admin_atribut_jabatan.html', context)
        except Exception as e:
            messages.error(request, f'Gagal memuat data: {str(e)}')
            return redirect('admin_atribut_jabatan')
            
    except Exception as e:
        messages.error(request, f'Terjadi kesalahan pada sistem: {str(e)}')
        return redirect('admin_atribut_jabatan')

@cek_instalasi
@superuser_required
def admin_atribut_jenjang(request):
    try:
        edit_data_atribut_jenjang = []
        edit_id = request.GET.get('id')
        if edit_id:
            data_jenjang = jenjang.objects.filter(id=edit_id).first()
            if data_jenjang:
                edit_data_atribut_jenjang.append({
                    'id': data_jenjang.id,
                    'nama_jenjang': data_jenjang.nama,
                })
        
        if request.method == 'POST':
            try:
                action = request.POST.get('action')
                if action == 'tambah':
                    nama = request.POST.get('nama_jenjang')
                    jenjang.objects.create(nama=nama)
                    messages.success(request, 'Jenjang berhasil ditambahkan.')
                elif action == 'edit':
                    id_jenjang = request.POST.get('id')
                    nama = request.POST.get('nama_jenjang')
                    jenjang.objects.filter(id=id_jenjang).update(nama=nama)
                    messages.success(request, 'Jenjang berhasil diperbarui.')
                elif action == 'hapus':
                    selected_ids = request.POST.getlist('selectedIds')
                    # Menangani kasus di mana selectedIds berisi string dengan beberapa ID
                    all_ids = []
                    for id_string in selected_ids:
                        all_ids.extend(id_string.split(','))
                    
                    jenjang.objects.filter(id__in=all_ids).delete()
                    messages.success(request, 'Jenjang berhasil dihapus.')
            except Exception as e:
                messages.error(request, f'Gagal memproses aksi: {str(e)}')
                return redirect('admin_atribut_jenjang')
            
            return redirect('admin_atribut_jenjang')
            
        try:
            jenjang_list = jenjang.objects.all()
            
            table_data = [
                [jen.id, jen.nama]
                for jen in jenjang_list
            ]
            context = get_context()
            context.update({
                'table_columns': ['ID', 'Nama'],
                'table_data': table_data,
                'edit_data_atribut_jenjang': edit_data_atribut_jenjang,
                'jenjang': True,
                
                'total_data_table': jenjang_list.count(),
                'API_LINK': reverse('api_jenjang'),
            })
            return render(request, 'CustomAdmin/admin_atribut_jenjang.html', context)
        except Exception as e:
            messages.error(request, f'Gagal memuat data: {str(e)}')
            return redirect('admin_atribut_jenjang')
            
    except Exception as e:
        messages.error(request, f'Terjadi kesalahan pada sistem: {str(e)}')
        return redirect('admin_atribut_jenjang')

# Tambahkan API views
@cek_instalasi
@superuser_required
@require_http_methods(['GET'])
def api_kelas(request):
    try:
        kelas_list = kelas.objects.all()
        data = [
            {
                'id': kls.id,
                'nama': kls.nama
            }
            for kls in kelas_list
        ]
        return JsonResponse({'kelas': data}, safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@cek_instalasi
@superuser_required
@require_http_methods(['GET'])
def api_mapel(request):
    try:
        mapel_list = mata_pelajaran.objects.all()
        data = [
            {
                'id': mpl.id,
                'nama': mpl.nama
            }
            for mpl in mapel_list
        ]
        return JsonResponse({'mapel': data}, safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@cek_instalasi
@superuser_required
@require_http_methods(['GET'])
def api_jabatan(request):
    try:
        jabatan_list = jabatan.objects.all()
        data = [
            {
                'id': jbt.id,
                'nama': jbt.nama
            }
            for jbt in jabatan_list
        ]
        return JsonResponse({'jabatan': data}, safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@cek_instalasi
@superuser_required
@require_http_methods(['GET'])
def api_jenjang(request):
    try:
        jenjang_list = jenjang.objects.all()
        data = [
            {
                'id': jjg.id,
                'nama': jjg.nama
            }
            for jjg in jenjang_list
        ]
        return JsonResponse({'jenjang': data}, safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

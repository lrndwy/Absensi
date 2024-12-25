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
def admin_sakit(request):
    try:
        context = get_context()
        context.update({
        })
        return render(request, 'CustomAdmin/admin_sakit.html', context)
    except Exception as e:
        messages.error(request, f'Terjadi kesalahan pada sistem: {str(e)}')
        return redirect('admin_sakit')

@cek_instalasi
@superuser_required
def admin_sakit_siswa(request):
    try:
        edit_data_sakit_siswa = []
        edit_id = request.GET.get('id')
        if edit_id:
            data_sakit = sakit.objects.filter(id=edit_id).first()
            if data_sakit:
                siswa = Siswa.objects.get(user=data_sakit.user)
                edit_data_sakit_siswa.append({
                    'id': data_sakit.id,
                    'user': data_sakit.user,
                    'nama': siswa.nama,
                    'kelas': siswa.kelas,
                    'jenjang': siswa.jenjang,
                    'keterangan': data_sakit.keterangan,
                    'surat_sakit_file': data_sakit.surat_sakit,
                })
                
        if request.method == 'POST':
            try:
                action = request.POST.get('action')
                if action == 'tambah':
                    user_nama = request.POST.get('nama')
                    user = CustomUser.objects.get(username=user_nama)
                    keterangan = request.POST.get('keterangan')
                    surat_sakit_file = request.FILES.get('surat_sakit_file')
                    
                    if surat_sakit_file:
                        # Simpan file
                        file_name = default_storage.save(f'surat_sakit/{surat_sakit_file.name}', ContentFile(surat_sakit_file.read()))
                        
                        # Buat objek sakit
                        sakit.objects.create(user=user, keterangan=keterangan, surat_sakit=file_name)
                        messages.success(request, 'Data sakit siswa berhasil ditambahkan.')
                    else:
                        messages.error(request, 'File surat sakit tidak ditemukan.')
                    
                    return redirect('admin_sakit_siswa')
                elif action == 'edit':
                    id_sakit = request.POST.get('id')
                    user_nama = request.POST.get('nama')
                    user = CustomUser.objects.get(username=user_nama)
                    keterangan = request.POST.get('keterangan')
                    surat_sakit_file = request.FILES.get('surat_sakit_file')
                    sakit_obj = sakit.objects.get(id=id_sakit)
                    sakit_obj.user = user
                    sakit_obj.keterangan = keterangan
                    if surat_sakit_file:
                        sakit_obj.surat_sakit = surat_sakit_file
                    sakit_obj.save()
                    messages.success(request, 'Data sakit siswa berhasil diperbarui.')
                elif action == 'hapus':
                    selected_ids = request.POST.getlist('selectedIds')
                    print(selected_ids)
                    deleted_count = 0
                    for id_group in selected_ids:
                        ids = id_group.split(',')
                        for id in ids:
                            try:
                                sakit_obj = sakit.objects.get(id=int(id))
                                if sakit_obj.surat_sakit:
                                    default_storage.delete(f'surat_sakit/{sakit_obj.surat_sakit}')
                                sakit_obj.delete()
                                deleted_count += 1
                            except ValueError:
                                messages.error(request, f'ID tidak valid: {id}')
                            except sakit.DoesNotExist:
                                messages.error(request, f'Data sakit dengan ID {id} tidak ditemukan')
                    if deleted_count > 0:
                        messages.success(request, f'{deleted_count} data sakit siswa berhasil dihapus.')
                    else:
                        messages.warning(request, 'Tidak ada data sakit siswa yang dihapus.')
                
                return redirect('admin_sakit_siswa')
            except Exception as e:
                messages.error(request, f'Terjadi kesalahan saat memproses aksi: {str(e)}')
                return redirect('admin_sakit_siswa')
        
        sakit_list = sakit.objects.filter(user__siswa__isnull=False)
        
        table_data = [
            [
                sakit_obj.id, 
                Siswa.objects.get(user=sakit_obj.user).nama,
                f"Kelas {Siswa.objects.get(user=sakit_obj.user).kelas} - {Siswa.objects.get(user=sakit_obj.user).jenjang}",
                sakit_obj.keterangan, 
                sakit_obj.surat_sakit.name if sakit_obj.surat_sakit else ''
            ]
            for sakit_obj in sakit_list
        ]
        context = get_context()
        context.update({
            'table_columns': ['ID', 'Nama Siswa', 'Kelas - Jenjang', 'Keterangan', 'Surat Sakit'],
            'table_data': table_data,
            'edit_data_sakit_siswa': edit_data_sakit_siswa,
            'siswa_list': Siswa.objects.all(),
            'sakit': True,
            
            'total_data_table': sakit_list.count(),
        })
        return render(request, 'CustomAdmin/admin_sakit_siswa.html', context)
    except Exception as e:
        messages.error(request, f'Terjadi kesalahan pada sistem: {str(e)}')
        return redirect('admin_sakit_siswa')

@cek_instalasi
@superuser_required
def admin_sakit_guru(request):
    try:
        edit_data_sakit_guru = []
        edit_id = request.GET.get('id')
        if edit_id:
            data_sakit = sakit.objects.filter(id=edit_id).first()
            if data_sakit:
                guru = Guru.objects.get(user=data_sakit.user)
                edit_data_sakit_guru.append({
                    'id': data_sakit.id,
                    'user': data_sakit.user,
                    'nama': guru.nama,
                    'mapel': guru.mata_pelajaran,
                    'jenjang': guru.jenjang,
                    'kelas': guru.kelas,
                    'keterangan': data_sakit.keterangan,
                    'surat_sakit_file': data_sakit.surat_sakit,
                })
                
        if request.method == 'POST':
            action = request.POST.get('action')
            if action == 'tambah':
                user_nama = request.POST.get('nama')
                user = CustomUser.objects.get(username=user_nama)
                keterangan = request.POST.get('keterangan')
                surat_sakit_file = request.FILES.get('surat_sakit_file')
                
                if surat_sakit_file:
                    # Simpan file
                    file_name = default_storage.save(f'surat_sakit_guru/{surat_sakit_file.name}', ContentFile(surat_sakit_file.read()))
                    
                    # Buat objek sakit
                    sakit.objects.create(user=user, keterangan=keterangan, surat_sakit=file_name)
                    messages.success(request, 'Data sakit guru berhasil ditambahkan.')
                else:
                    messages.error(request, 'File surat sakit tidak ditemukan.')
                
                return redirect('admin_sakit_guru')
            elif action == 'edit':
                id_sakit = request.POST.get('id')
                user_nama = request.POST.get('nama')
                user = CustomUser.objects.get(username=user_nama)
                keterangan = request.POST.get('keterangan')
                surat_sakit_file = request.FILES.get('surat_sakit_file')
                sakit_obj = sakit.objects.get(id=id_sakit)
                sakit_obj.user = user
                sakit_obj.keterangan = keterangan
                if surat_sakit_file:
                    sakit_obj.surat_sakit = surat_sakit_file
                sakit_obj.save()
                messages.success(request, 'Data sakit guru berhasil diperbarui.')
            elif action == 'hapus':
                selected_ids = request.POST.getlist('selectedIds')
                deleted_count = 0
                for id_group in selected_ids:
                    ids = id_group.split(',')
                    for id in ids:
                        try:
                            sakit_obj = sakit.objects.get(id=int(id))
                            if sakit_obj.surat_sakit:
                                default_storage.delete(f'surat_sakit_guru/{sakit_obj.surat_sakit}')
                            sakit_obj.delete()
                            deleted_count += 1
                        except ValueError:
                            messages.error(request, f'ID tidak valid: {id}')
                        except sakit.DoesNotExist:
                            messages.error(request, f'Data sakit dengan ID {id} tidak ditemukan')
                if deleted_count > 0:
                    messages.success(request, f'{deleted_count} data sakit guru berhasil dihapus.')
                else:
                    messages.warning(request, 'Tidak ada data sakit guru yang dihapus.')
            
            return redirect('admin_sakit_guru')
        
        sakit_list = sakit.objects.filter(user__guru__isnull=False)
        
        table_data = [
            [
                sakit_obj.id, 
                Guru.objects.get(user=sakit_obj.user).nama,
                Guru.objects.get(user=sakit_obj.user).mata_pelajaran,
                f"Kelas {Guru.objects.get(user=sakit_obj.user).kelas} - {Guru.objects.get(user=sakit_obj.user).jenjang}",
                sakit_obj.keterangan,
                sakit_obj.surat_sakit.name if sakit_obj.surat_sakit else ''
            ]
            for sakit_obj in sakit_list
        ]
           
        context = get_context()     
        context.update({
            'table_columns': ['ID', 'Nama Guru', 'Mata Pelajaran', 'Kelas - Jenjang', 'Keterangan', 'Surat Sakit'],
            'table_data': table_data,
            'edit_data_sakit_guru': edit_data_sakit_guru,
            'guru_list': Guru.objects.all(),
            'sakit': True,
            
            'total_data_table': sakit_list.count(),
        })
        return render(request, 'CustomAdmin/admin_sakit_guru.html', context)
    except Exception as e:
        messages.error(request, f'Terjadi kesalahan pada sistem: {str(e)}')
        return redirect('admin_sakit_guru')

@cek_instalasi
@superuser_required
def admin_sakit_karyawan(request):
    try:
        edit_data_sakit_karyawan = []
        edit_id = request.GET.get('id')
        if edit_id:
            data_sakit = sakit.objects.filter(id=edit_id).first()
            if data_sakit:
                karyawan = Karyawan.objects.get(user=data_sakit.user)
                edit_data_sakit_karyawan.append({
                    'id': data_sakit.id,
                    'user': data_sakit.user,
                    'nama': karyawan.nama,
                    'jabatan': karyawan.jabatan,
                    'keterangan': data_sakit.keterangan,
                    'surat_sakit_file': data_sakit.surat_sakit,
                })
                
        if request.method == 'POST':
            action = request.POST.get('action')
            if action == 'tambah':
                user_nama = request.POST.get('nama')
                user = CustomUser.objects.get(username=user_nama)
                keterangan = request.POST.get('keterangan')
                surat_sakit_file = request.FILES.get('surat_sakit_file')
                
                if surat_sakit_file:
                    # Simpan file
                    file_name = default_storage.save(f'surat_sakit_karyawan/{surat_sakit_file.name}', ContentFile(surat_sakit_file.read()))
                    
                    # Buat objek sakit
                    sakit.objects.create(user=user, keterangan=keterangan, surat_sakit=file_name)
                    messages.success(request, 'Data sakit karyawan berhasil ditambahkan.')
                else:
                    messages.error(request, 'File surat sakit tidak ditemukan.')
                
                return redirect('admin_sakit_karyawan')
            elif action == 'edit':
                id_sakit = request.POST.get('id')
                user_nama = request.POST.get('nama')
                user = CustomUser.objects.get(username=user_nama)
                keterangan = request.POST.get('keterangan')
                surat_sakit_file = request.FILES.get('surat_sakit_file')
                sakit_obj = sakit.objects.get(id=id_sakit)
                sakit_obj.user = user
                sakit_obj.keterangan = keterangan
                if surat_sakit_file:
                    sakit_obj.surat_sakit = surat_sakit_file
                sakit_obj.save()
                messages.success(request, 'Data sakit karyawan berhasil diperbarui.')
            elif action == 'hapus':
                selected_ids = request.POST.getlist('selectedIds')
                deleted_count = 0
                for id_group in selected_ids:
                    ids = id_group.split(',')
                    for id in ids:
                        try:
                            sakit_obj = sakit.objects.get(id=int(id))
                            if sakit_obj.surat_sakit:
                                default_storage.delete(f'surat_sakit_karyawan/{sakit_obj.surat_sakit}')
                            sakit_obj.delete()
                            deleted_count += 1
                        except ValueError:
                            messages.error(request, f'ID tidak valid: {id}')
                        except sakit.DoesNotExist:
                            messages.error(request, f'Data sakit dengan ID {id} tidak ditemukan')
                if deleted_count > 0:
                    messages.success(request, f'{deleted_count} data sakit karyawan berhasil dihapus.')
                else:
                    messages.warning(request, 'Tidak ada data sakit karyawan yang dihapus.')
            
            return redirect('admin_sakit_karyawan')
        
        sakit_list = sakit.objects.filter(user__karyawan__isnull=False)
        
        table_data = [
            [
                sakit_obj.id, 
                Karyawan.objects.get(user=sakit_obj.user).nama,
                Karyawan.objects.get(user=sakit_obj.user).jabatan,
                sakit_obj.keterangan,
                sakit_obj.surat_sakit.name if sakit_obj.surat_sakit else ''
            ]
            for sakit_obj in sakit_list
        ]
        context = get_context()
        context.update({
            'table_columns': ['ID', 'Nama Karyawan', 'Jabatan', 'Keterangan', 'Surat Sakit'],
            'table_data': table_data,
            'edit_data_sakit_karyawan': edit_data_sakit_karyawan,
            'karyawan_list': Karyawan.objects.all(),
            'sakit': True,
            
            'total_data_table': sakit_list.count(),
        })
        return render(request, 'CustomAdmin/admin_sakit_karyawan.html', context)
    except Exception as e:
        messages.error(request, f'Terjadi kesalahan pada sistem: {str(e)}')
        return redirect('admin_sakit_karyawan')

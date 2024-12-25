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
def admin_izin(request):
    try:
        context = get_context()
        context.update({
        })
        return render(request, 'CustomAdmin/admin_izin.html', context)
    except Exception as e:
        messages.error(request, f'Terjadi kesalahan pada sistem: {str(e)}')
        return redirect('admin_izin')

@cek_instalasi
@superuser_required
def admin_izin_siswa(request):
    try:
        edit_data_izin_siswa = []
        edit_id = request.GET.get('id')
        if edit_id:
            data_izin = izin.objects.filter(id=edit_id).first()
            if data_izin:
                siswa = Siswa.objects.get(user=data_izin.user)
                edit_data_izin_siswa.append({
                    'id': data_izin.id,
                    'nama': siswa.nama,
                    'kelas': siswa.kelas,
                    'jenjang': siswa.jenjang,
                    'keterangan': data_izin.keterangan,
                })
                
        if request.method == 'POST':
            action = request.POST.get('action')
            if action == 'tambah':
                user_nama = request.POST.get('nama')
                user = CustomUser.objects.get(username=user_nama)
                keterangan = request.POST.get('keterangan')
                
                izin.objects.create(user=user, keterangan=keterangan)
                messages.success(request, 'Data izin siswa berhasil ditambahkan.')
                
                return redirect('admin_izin_siswa')
            elif action == 'edit':
                id_izin = request.POST.get('id')
                user_nama = request.POST.get('nama')
                user = CustomUser.objects.get(username=user_nama)
                keterangan = request.POST.get('keterangan')
                izin_obj = izin.objects.get(id=id_izin)
                izin_obj.user = user
                izin_obj.keterangan = keterangan
                izin_obj.save()
                messages.success(request, 'Data izin siswa berhasil diperbarui.')
            elif action == 'hapus':
                selected_ids = request.POST.getlist('selectedIds')
                deleted_count = 0
                for id_group in selected_ids:
                    ids = id_group.split(',')
                    for id in ids:
                        try:
                            izin_obj = izin.objects.get(id=int(id))
                            izin_obj.delete()
                            deleted_count += 1
                        except ValueError:
                            messages.error(request, f'ID tidak valid: {id}')
                        except izin.DoesNotExist:
                            messages.error(request, f'Data izin dengan ID {id} tidak ditemukan')
                if deleted_count > 0:
                    messages.success(request, f'{deleted_count} data izin siswa berhasil dihapus.')
                else:
                    messages.warning(request, 'Tidak ada data izin siswa yang dihapus.')
            
            return redirect('admin_izin_siswa')
        
        izin_list = izin.objects.filter(user__siswa__isnull=False)
        
        table_data = [
            [izin_obj.id, Siswa.objects.get(user=izin_obj.user).nama,
             f"Kelas {Siswa.objects.get(user=izin_obj.user).kelas} - {Siswa.objects.get(user=izin_obj.user).jenjang}",
             izin_obj.keterangan]
            for izin_obj in izin_list
        ]
        
        context = get_context()
        context.update({
            'table_columns': ['ID', 'Nama Siswa', 'Kelas - Jenjang', 'Keterangan'],
            'table_data': table_data,
            'edit_data_izin_siswa': edit_data_izin_siswa,
            'siswa_list': Siswa.objects.all(),
            'izin': True,
            
            'total_data_table': izin_list.count(),
        })
        return render(request, 'CustomAdmin/admin_izin_siswa.html', context)
    except Exception as e:
        messages.error(request, f'Terjadi kesalahan pada sistem: {str(e)}')
        return redirect('admin_izin_siswa')

@cek_instalasi
@superuser_required
def admin_izin_guru(request):
    try:
        edit_data_izin_guru = []
        edit_id = request.GET.get('id')
        if edit_id:
            data_izin = izin.objects.filter(id=edit_id).first()
            if data_izin:
                guru = Guru.objects.get(user=data_izin.user)
                edit_data_izin_guru.append({
                    'id': data_izin.id,
                    'nama': guru.nama,
                    'mapel': guru.mata_pelajaran,
                    'jenjang': guru.jenjang,
                    'kelas': guru.kelas,
                    'keterangan': data_izin.keterangan,
                })
                
        if request.method == 'POST':
            action = request.POST.get('action')
            if action == 'tambah':
                user_nama = request.POST.get('nama')
                user = CustomUser.objects.get(username=user_nama)
                keterangan = request.POST.get('keterangan')
                
                izin.objects.create(user=user, keterangan=keterangan)
                messages.success(request, 'Data izin guru berhasil ditambahkan.')
                
                return redirect('admin_izin_guru')
            elif action == 'edit':
                id_izin = request.POST.get('id')
                user_nama = request.POST.get('nama')
                user = CustomUser.objects.get(username=user_nama)
                keterangan = request.POST.get('keterangan')
                izin_obj = izin.objects.get(id=id_izin)
                izin_obj.user = user
                izin_obj.keterangan = keterangan
                izin_obj.save()
                messages.success(request, 'Data izin guru berhasil diperbarui.')
            elif action == 'hapus':
                selected_ids = request.POST.getlist('selectedIds')
                deleted_count = 0
                for id_group in selected_ids:
                    ids = id_group.split(',')
                    for id in ids:
                        try:
                            izin_obj = izin.objects.get(id=int(id))
                            izin_obj.delete()
                            deleted_count += 1
                        except ValueError:
                            messages.error(request, f'ID tidak valid: {id}')
                        except izin.DoesNotExist:
                            messages.error(request, f'Data izin dengan ID {id} tidak ditemukan')
                if deleted_count > 0:
                    messages.success(request, f'{deleted_count} data izin guru berhasil dihapus.')
                else:
                    messages.warning(request, 'Tidak ada data izin guru yang dihapus.')
            
            return redirect('admin_izin_guru')
        
        izin_list = izin.objects.filter(user__guru__isnull=False)
        
        table_data = [
            [izin_obj.id, Guru.objects.get(user=izin_obj.user).nama,
             f"Kelas {Guru.objects.get(user=izin_obj.user).kelas} - {Guru.objects.get(user=izin_obj.user).jenjang}",
             Guru.objects.get(user=izin_obj.user).mata_pelajaran,
             izin_obj.keterangan]
            for izin_obj in izin_list
        ]
        
        context = get_context()
        context.update({
            'table_columns': ['ID', 'Nama Guru', 'Mata Pelajaran', 'Kelas - Jenjang', 'Keterangan'],
            'table_data': table_data,
            'edit_data_izin_guru': edit_data_izin_guru,
            'guru_list': Guru.objects.all(),
            'izin': True,
            
            'total_data_table': izin_list.count(),
        })
        return render(request, 'CustomAdmin/admin_izin_guru.html', context)
    except Exception as e:
        messages.error(request, f'Terjadi kesalahan pada sistem: {str(e)}')
        return redirect('admin_izin_guru')

@cek_instalasi
@superuser_required
def admin_izin_karyawan(request):
    try:
        edit_data_izin_karyawan = []
        edit_id = request.GET.get('id')
        if edit_id:
            data_izin = izin.objects.filter(id=edit_id).first()
            if data_izin:
                karyawan = Karyawan.objects.get(user=data_izin.user)
                edit_data_izin_karyawan.append({
                    'id': data_izin.id,
                    'nama': karyawan.nama,
                    'jabatan': karyawan.jabatan,
                    'keterangan': data_izin.keterangan,
                })
                
        if request.method == 'POST':
            action = request.POST.get('action')
            if action == 'tambah':
                user_nama = request.POST.get('nama')
                user = CustomUser.objects.get(username=user_nama)
                keterangan = request.POST.get('keterangan')
                
                izin.objects.create(user=user, keterangan=keterangan)
                messages.success(request, 'Data izin karyawan berhasil ditambahkan.')
                
                return redirect('admin_izin_karyawan')
            elif action == 'edit':
                id_izin = request.POST.get('id')
                user_nama = request.POST.get('nama')
                user = CustomUser.objects.get(username=user_nama)
                keterangan = request.POST.get('keterangan')
                izin_obj = izin.objects.get(id=id_izin)
                izin_obj.user = user
                izin_obj.keterangan = keterangan
                izin_obj.save()
                messages.success(request, 'Data izin karyawan berhasil diperbarui.')
            elif action == 'hapus':
                selected_ids = request.POST.getlist('selectedIds')
                deleted_count = 0
                for id_group in selected_ids:
                    ids = id_group.split(',')
                    for id in ids:
                        try:
                            izin_obj = izin.objects.get(id=int(id))
                            izin_obj.delete()
                            deleted_count += 1
                        except ValueError:
                            messages.error(request, f'ID tidak valid: {id}')
                        except izin.DoesNotExist:
                            messages.error(request, f'Data izin dengan ID {id} tidak ditemukan')
                if deleted_count > 0:
                    messages.success(request, f'{deleted_count} data izin karyawan berhasil dihapus.')
                else:
                    messages.warning(request, 'Tidak ada data izin karyawan yang dihapus.')
            
            return redirect('admin_izin_karyawan')
        
        izin_list = izin.objects.filter(user__karyawan__isnull=False)
        
        table_data = [
            [izin_obj.id, Karyawan.objects.get(user=izin_obj.user).nama,
             Karyawan.objects.get(user=izin_obj.user).jabatan,
             izin_obj.keterangan]
            for izin_obj in izin_list
        ]
        
        context = get_context()
        context.update({
            'table_columns': ['ID', 'Nama Karyawan', 'Jabatan', 'Keterangan'],
            'table_data': table_data,
            'edit_data_izin_karyawan': edit_data_izin_karyawan,
            'karyawan_list': Karyawan.objects.all(),
            'izin': True,
            
            'total_data_table': izin_list.count(),
        })
        return render(request, 'CustomAdmin/admin_izin_karyawan.html', context)
    except Exception as e:
        messages.error(request, f'Terjadi kesalahan pada sistem: {str(e)}')
        return redirect('admin_izin_karyawan')

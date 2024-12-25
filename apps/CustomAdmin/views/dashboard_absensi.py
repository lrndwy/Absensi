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
def admin_dashboard(request):
    try:
        absensi_records = record_absensi.objects.filter(status_verifikasi='diterima').order_by('-checktime')
        absensi_record_charts = record_absensi.objects.filter(
            status_verifikasi='diterima'
        ).order_by('-checktime')

        start_date = request.GET.get('start')
        end_date = request.GET.get('end')
        
        # Pastikan start_date dan end_date memiliki nilai default
        if not start_date or not end_date:
            end_date = timezone.localtime(timezone.now()).date()
            start_date = end_date - timezone.timedelta(days=6)  # 7 hari terakhir
        else:
            try:
                start_date = datetime.strptime(start_date, '%m/%d/%Y').date()
                end_date = datetime.strptime(end_date, '%m/%d/%Y').date()
                messages.info(request, f'Data difilter berdasarkan tanggal: {start_date} - {end_date}')
            except ValueError:
                end_date = timezone.now().date()
                start_date = end_date - timezone.timedelta(days=6)
                messages.error(request, 'Format tanggal tidak valid. Menggunakan rentang tanggal default.')

        # Filter absensi_records berdasarkan rentang tanggal
        absensi_records = absensi_records.filter(
            checktime__date__gte=start_date,
            checktime__date__lte=end_date
        )
        
        absensi_record_charts = absensi_record_charts.filter(
            checktime__date__gte=start_date,
            checktime__date__lte=end_date
        )

        if request.method == 'POST':
            action = request.POST.get('action')
            if action == 'tambah':
                user_id = request.POST.get('user')
                status = request.POST.get('status')
                checktime = request.POST.get('checktime')
                tipe_absensi = request.POST.get('tipe_absensi')
                
                try:
                    user = CustomUser.objects.get(id=user_id)
                    instalasi = Instalasi.objects.first()
                    
                    if status == 'hadir':
                        # Tentukan jam masuk dan pulang berdasarkan tipe user
                        jam_masuk = None
                        jam_pulang = None
                        terlambat = 0
                        
                        if Siswa.objects.filter(user=user).exists():
                            jam_masuk = instalasi.jam_masuk_siswa
                            jam_pulang = instalasi.jam_pulang_siswa
                            jam_kerja = instalasi.jam_sekolah_siswa
                        elif Guru.objects.filter(user=user).exists():
                            jam_masuk = instalasi.jam_masuk_guru
                            jam_pulang = instalasi.jam_pulang_guru
                            jam_kerja = instalasi.jam_kerja_guru
                        elif Karyawan.objects.filter(user=user).exists():
                            jam_masuk = instalasi.jam_masuk_karyawan
                            jam_pulang = instalasi.jam_pulang_karyawan
                            jam_kerja = instalasi.jam_kerja_karyawan
                            
                        # Cek apakah sudah ada absensi dengan tipe yang sama untuk hari ini
                        existing_record = record_absensi.objects.filter(
                            user=user,
                            status='hadir',
                            tipe_absensi=tipe_absensi,
                            checktime__date=datetime.strptime(checktime, '%Y-%m-%dT%H:%M').date()
                        ).exists()
                        
                        if existing_record:
                            messages.error(request, f'Sudah ada data absensi {tipe_absensi} untuk hari ini.')
                            return redirect('admin_dashboard')
                        
                        if tipe_absensi == 'masuk':
                            try:
                                if not instalasi:
                                    terlambat = 0
                                else:
                                    if jam_masuk:
                                        # Ambil jam dan menit dari waktu absen
                                        waktu_absen = timezone.make_aware(datetime.strptime(checktime, '%Y-%m-%dT%H:%M')).time()
                                        
                                        # Hitung selisih dalam menit
                                        selisih_menit = (
                                            waktu_absen.hour * 60 + waktu_absen.minute
                                        ) - (
                                            jam_masuk.hour * 60 + jam_masuk.minute
                                        )
                                        
                                        # Set keterlambatan (minimal 0 menit)
                                        terlambat = max(0, selisih_menit)
                                    else:
                                        terlambat = 0
                            except Exception as e:
                                messages.error(request, f'Error menghitung keterlambatan: {str(e)}')
                                terlambat = 0
                                
                        elif tipe_absensi == 'pulang':
                            try: 
                                # Ambil jam masuk terakhir siswa untuk hari ini
                                jam_masuk_record = record_absensi.objects.filter(
                                    user=user,
                                    status='hadir',
                                    tipe_absensi='masuk',
                                    checktime__date=datetime.strptime(checktime, '%Y-%m-%dT%H:%M').date()
                                ).first()
                                
                                if not jam_masuk_record:
                                    messages.error(request, 'Tidak ada data absensi masuk untuk hari ini.')
                                    return redirect('admin_dashboard')
                                
                                # Hitung selisih waktu
                                waktu_pulang = timezone.make_aware(datetime.strptime(checktime, '%Y-%m-%dT%H:%M'))
                                
                                # # Tentukan jam kerja berdasarkan tipe user
                                # if Siswa.objects.filter(user=user).exists():
                                #     jam_kerja = instalasi.jam_sekolah_siswa
                                #     jam_pulang_ref = instalasi.jam_pulang_siswa
                                # elif Guru.objects.filter(user=user).exists():
                                #     jam_kerja = instalasi.jam_kerja_guru
                                #     jam_pulang_ref = instalasi.jam_pulang_guru
                                # elif Karyawan.objects.filter(user=user).exists():
                                #     jam_kerja = instalasi.jam_kerja_karyawan
                                #     jam_pulang_ref = instalasi.jam_pulang_karyawan
                                # else:
                                #     messages.error(request, 'Tipe pengguna tidak valid.')
                                #     return redirect('admin_dashboard')
                                
                                # if not jam_kerja:
                                #     messages.error(request, 'Jam kerja belum diatur di sistem.')
                                #     return redirect('admin_dashboard')
                                    
                                # # Hitung selisih waktu dari absen masuk
                                # selisih_waktu = waktu_pulang - jam_masuk_record.checktime
                                
                                # # Validasi minimal jam kerja
                                # if selisih_waktu < jam_kerja:
                                #     messages.error(request, f'Waktu pulang tidak boleh kurang dari {jam_kerja} dari jam masuk.')
                                #     return redirect('admin_dashboard')
                                
                                # # Validasi jam pulang tidak lebih awal dari jadwal
                                # if jam_pulang_ref:
                                #     waktu_pulang_min = datetime.combine(
                                #         waktu_pulang.date(), 
                                #         jam_pulang_ref
                                #     )
                                #     waktu_pulang_min = timezone.make_aware(waktu_pulang_min)
                                    
                                #     if waktu_pulang < waktu_pulang_min:
                                #         messages.error(request, f'Waktu pulang tidak boleh lebih awal dari jadwal ({jam_pulang_ref.strftime("%H:%M")})')
                                #         return redirect('admin_dashboard')
                                    
                            except record_absensi.DoesNotExist:
                                messages.error(request, 'Tidak ada data absensi masuk untuk hari ini.')
                                return redirect('admin_dashboard')
                            except Exception as e:
                                messages.error(request, f'Terjadi kesalahan saat memproses absensi pulang: {str(e)}')
                                return redirect('admin_dashboard')
                        record = record_absensi.objects.create(
                            user=user,
                            status=status,
                            checktime=checktime,
                            status_verifikasi='diterima',
                            tipe_absensi=tipe_absensi,
                            terlambat=terlambat
                        )
                    elif status == 'izin':
                      id_izin = request.POST.get('id_izin')
                      izin_obj = izin.objects.get(id=id_izin)
                      if izin_obj.user != user:
                          messages.error(request, f'Data izin user {user.username} dengan id {id_izin} tidak ditemukan.')
                          return redirect('admin_dashboard')
                      record = record_absensi.objects.create(
                          user=user,
                          status=status,
                          id_izin=izin_obj,
                          checktime=checktime,
                          status_verifikasi='diterima',
                          terlambat=0
                      )
                    elif status == 'sakit':
                        id_sakit = request.POST.get('id_sakit')
                        sakit_obj = sakit.objects.get(id=id_sakit)
                        if sakit_obj.user != user:
                            messages.error(request, f'Data sakit user {user.username} dengan id {id_sakit} tidak ditemukan.')
                            return redirect('admin_dashboard')
                        record = record_absensi.objects.create(
                            user=user,
                            status=status,
                            id_sakit=sakit_obj,
                            checktime=checktime,
                            status_verifikasi='diterima',
                            terlambat=0
                        )
                    
                    messages.success(request, 'Data absensi berhasil ditambahkan.')
                except CustomUser.DoesNotExist:
                    messages.error(request, 'Pengguna tidak ditemukan.')
                except izin.DoesNotExist:
                    messages.error(request, 'Data izin tidak ditemukan.')
                except sakit.DoesNotExist:
                    messages.error(request, 'Data sakit tidak ditemukan.')
                except Exception as e:
                    messages.error(request, f'Terjadi kesalahan: {str(e)}')
                
                return redirect('admin_dashboard')

            elif action == 'hapus':
                selected_ids = request.POST.get('selectedIds')
                if selected_ids:
                    valid_ids = [int(id.strip()) for id in selected_ids.split(',') if id.strip().isdigit()]
                    if valid_ids:
                        deleted_count = record_absensi.objects.filter(id__in=valid_ids).delete()[0]
                        messages.success(request, f'{deleted_count} data absensi berhasil dihapus.')
                    else:
                        messages.error(request, 'Tidak ada ID valid yang dipilih untuk dihapus.')
                else:
                    messages.error(request, 'Tidak ada data yang dipilih untuk dihapus.')
                return redirect('admin_dashboard')
              
            if action == 'edit':
                absensi_id = request.POST.get('id')
                checktime = request.POST.get('tanggal_waktu')
                status = request.POST.get('status')
                status_verifikasi = request.POST.get('status_verifikasi')
                tipe_absensi = request.POST.get('tipe_absensi')
                
                try:
                    absensi = record_absensi.objects.get(id=absensi_id)
                    user = absensi.user
                    terlambat = 0  # Inisialisasi variabel terlambat di awal
                    
                    # Ubah format waktu dengan benar
                    try:
                        checktime_datetime = datetime.strptime(checktime, '%Y-%m-%dT%H:%M')
                        checktime_aware = timezone.make_aware(checktime_datetime)
                        absensi.checktime = checktime_aware
                    except ValueError:
                        messages.error(request, 'Format tanggal dan waktu tidak valid')
                        return redirect('admin_dashboard')
                        
                    
                    if status == 'izin':
                        id_izin = request.POST.get('id_izin')
                        absensi.id_izin = izin.objects.get(id=id_izin) if id_izin else None
                        absensi.id_sakit = None
                        terlambat = 0
                    elif status == 'sakit':
                        id_sakit = request.POST.get('id_sakit')
                        absensi.id_sakit = sakit.objects.get(id=id_sakit) if id_sakit else None
                        absensi.id_izin = None
                        terlambat = 0
                    else:
                        absensi.id_izin = None
                        absensi.id_sakit = None
                        
                        # Cek apakah sudah ada absensi dengan tipe yang sama untuk hari ini
                        existing_record = record_absensi.objects.filter(
                            user=user,
                            status='hadir',
                            tipe_absensi=tipe_absensi,
                            checktime__date=datetime.strptime(checktime, '%Y-%m-%dT%H:%M').date()
                        ).exclude(id=absensi_id).exists()  # Tambahkan .exclude(id=absensi_id)
                        
                        if existing_record:
                            messages.error(request, f'Sudah ada data absensi {tipe_absensi} untuk hari ini.')
                            return redirect('admin_dashboard')
                        
                        if tipe_absensi == 'masuk':
                            try:
                                instalasi = Instalasi.objects.first()
                                if not instalasi:
                                    absensi.terlambat = 0
                                else:
                                    # Tentukan jam masuk berdasarkan tipe user
                                    jam_masuk = None
                                    if Siswa.objects.filter(user=user).exists():
                                        jam_masuk = instalasi.jam_masuk_siswa
                                    elif Guru.objects.filter(user=user).exists():
                                        jam_masuk = instalasi.jam_masuk_guru
                                    elif Karyawan.objects.filter(user=user).exists():
                                        jam_masuk = instalasi.jam_masuk_karyawan
                                    
                                    if jam_masuk:
                                        # Ambil jam dan menit dari waktu absen
                                        waktu_absen = checktime_aware.time()
                                        
                                        # Hitung selisih dalam menit
                                        selisih_menit = (
                                            waktu_absen.hour * 60 + waktu_absen.minute
                                        ) - (
                                            jam_masuk.hour * 60 + jam_masuk.minute
                                        )
                                        
                                        # Set keterlambatan (minimal 0 menit)
                                        terlambat = max(0, selisih_menit)
                                        
                                    else:
                                        absensi.terlambat = 0
                            except Exception as e:
                                messages.error(request, f'Error menghitung keterlambatan: {str(e)}')
                                absensi.terlambat = 0
                        
                                
                        elif tipe_absensi == 'pulang':
                            try: 
                                # Ambil jam masuk terakhir siswa
                                jam_masuk = record_absensi.objects.filter(
                                    user=user,
                                    status='hadir',
                                    tipe_absensi='masuk',
                                    checktime__date=datetime.strptime(checktime, '%Y-%m-%dT%H:%M').date()
                                ).latest('checktime')
                                
                                # # Kode di bawah ini dinonaktifkan - tidak perlu cek jam kerja
                                # # Ambil jam kerja dari Instalasi
                                # instalasi = Instalasi.objects.first()
                                
                                # # Tentukan jam kerja berdasarkan tipe user
                                # jam_kerja = None
                                # if Siswa.objects.filter(user=user).exists():
                                #     jam_kerja = instalasi.jam_sekolah_siswa
                                # elif Guru.objects.filter(user=user).exists():
                                #     jam_kerja = instalasi.jam_kerja_guru
                                # elif Karyawan.objects.filter(user=user).exists():
                                #     jam_kerja = instalasi.jam_kerja_karyawan
                                
                                # if jam_kerja:
                                #     # Hitung selisih waktu
                                #     waktu_pulang = checktime_aware
                                #     selisih_waktu = waktu_pulang - jam_masuk.checktime
                                
                                #     if selisih_waktu < jam_kerja:
                                #         messages.error(request, f'Waktu pulang tidak boleh lebih cepat dari {jam_kerja} dari jam masuk.')
                                #         return redirect('admin_dashboard')
                                
                                terlambat = 0
                            except record_absensi.DoesNotExist:
                                messages.error(request, 'Tidak ada data absensi masuk untuk hari ini. Siswa harus absen masuk terlebih dahulu.')
                                return redirect('admin_dashboard')
                    absensi.status = status
                    absensi.status_verifikasi = status_verifikasi
                    absensi.tipe_absensi = tipe_absensi
                    absensi.terlambat = terlambat
                    print(f'absensi: {absensi.status}, {absensi.status_verifikasi}, {absensi.tipe_absensi}, {absensi.terlambat}')
                    absensi.save()
                    messages.success(request, 'Data absensi berhasil diperbarui.')
                except record_absensi.DoesNotExist:
                    messages.error(request, 'Data absensi tidak ditemukan.')
                except Exception as e:
                    messages.error(request, f'Terjadi kesalahan: {str(e)}')
                
                return redirect('admin_dashboard')
              
        # Data untuk series chart
        daily_counts = absensi_record_charts.annotate(date=TruncDate('checktime')).values('date').annotate(
            hadir=Count('id', filter=Q(status='hadir')),
            sakit=Count('id', filter=Q(status='sakit')),
            izin=Count('id', filter=Q(status='izin'))
        ).order_by('date')
        
        dates = [(start_date + timezone.timedelta(days=x)).strftime('%d') for x in range((end_date - start_date).days + 1)]
        hadir_data = [0] * len(dates)
        sakit_data = [0] * len(dates)
        izin_data = [0] * len(dates)

        for count in daily_counts:
            if count['date'] is not None:
                index = (count['date'] - start_date).days
                if 0 <= index < len(dates):
                    hadir_data[index] = count['hadir']
                    sakit_data[index] = count['sakit']
                    izin_data[index] = count['izin']

        # Data untuk pie chart dan radial charts
        total_hadir = sum(hadir_data)
        total_sakit = sum(sakit_data)
        total_izin = sum(izin_data)
        total_all = total_hadir + total_sakit + total_izin

        hadir_percentage = round((total_hadir / total_all) * 100) if total_all > 0 else 0
        sakit_percentage = round((total_sakit / total_all) * 100) if total_all > 0 else 0
        izin_percentage = round((total_izin / total_all) * 100) if total_all > 0 else 0
        
        # untuk edit data
        edit_data_dashboard_absensi = []
        edit_id = request.GET.get('id')
        # Untuk admin_dashboard
        if edit_id:
            for record_edit in record_absensi.objects.filter(id=edit_id):
                record_data = {
                    'id': record_edit.id,
                    'user': record_edit.user.username if record_edit.user else None,
                    'checktime': timezone.localtime(record_edit.checktime).strftime('%Y-%m-%d %H:%M'),
                    'status': record_edit.status,
                    'id_izin': record_edit.id_izin.id if record_edit.id_izin else None,
                    'id_sakit': record_edit.id_sakit.id if record_edit.id_sakit else None,
                    'status_verifikasi': record_edit.status_verifikasi,
                    'tipe_absensi': record_edit.tipe_absensi,
                }
                edit_data_dashboard_absensi.append(record_data)

        context = get_context()
        context.update({
            # Data Series
            'ds_title': 'Statistik Absensi',
            'ds_percentage': str(hadir_percentage)+'%',
            'ds_name_1': 'Hadir',
            'ds_data_1': hadir_data,
            'ds_name_2': 'Sakit',
            'ds_data_2': sakit_data,
            'ds_name_3': 'Izin',
            'ds_data_3': izin_data,
            'ds_categories_json': json.dumps(dates),
            'ds_month': f"{start_date.strftime('%d %B')} - {end_date.strftime('%d %B %Y')}",
            
            # Pie Charts
            'pc_title': 'Statistik Absensi',
            'pc_month': f"{start_date.strftime('%d %B')} - {end_date.strftime('%d %B %Y')}",
            'pc_data': json.dumps([total_izin, total_sakit, total_hadir]),
            'pc_labels': json.dumps(['Izin', 'Sakit', 'Hadir']),
            
            # Radial Charts
            'rc_title': 'Statistik Absensi',
            'rc_month': f"{start_date.strftime('%d %B')} - {end_date.strftime('%d %B %Y')}",
            'rc_data_percentage_1': str(hadir_percentage),
            'rc_data_total_1': str(total_hadir),
            'rc_name_1': 'Hadir',
            'rc_data_percentage_2': str(sakit_percentage),
            'rc_data_total_2': str(total_sakit),
            'rc_name_2': 'Sakit',
            'rc_data_percentage_3': str(izin_percentage),
            'rc_data_total_3': str(total_izin),
            'rc_name_3': 'Izin',
            
            'day_ago': (end_date - start_date).days + 1,
            
            # Table data (updated)
            'table_columns': ['id records', 'userid', 'Username', 'Nama', 'Checktime', 'Status', 'Tipe Absensi', 'Terlambat (menit)', 'Mesin'],
            'table_data': absensi_records.annotate(
                nama=Coalesce(
                    'user__siswa__nama',
                    'user__guru__nama',
                    'user__karyawan__nama',
                    'user__first_name'
                ),
            ).values_list('id', 'user__userid', 'user__username', 'nama', 'checktime', 'status', 'tipe_absensi', 'terlambat', 'mesin'),
            
            'start_date': start_date.strftime('%m/%d/%Y'),
            'end_date': end_date.strftime('%m/%d/%Y'),
            
            'total_data_table': absensi_records.count(),
            
            # form tambah record
            'users': CustomUser.objects.filter(is_superuser=False),
            'id_izin': izin.objects.exclude(id__in=record_absensi.objects.values('id_izin')),
            'id_sakit': sakit.objects.exclude(id__in=record_absensi.objects.values('id_sakit')),
            
            # form edit record
            'edit_data_dashboard_absensi': edit_data_dashboard_absensi,
            
            # id Izin
            'id_izin': izin.objects.exclude(record_absensi__id_izin__isnull=False),
            'id_sakit': sakit.objects.exclude(record_absensi__id_sakit__isnull=False),
            
            'status_list': ['hadir', 'izin', 'sakit'],
            'status_verifikasi_list': ['menunggu', 'diterima', 'ditolak'],
            'tipe_absensi_list': ['masuk', 'pulang'],
        })
        return render(request, 'CustomAdmin/admin_dashboard.html', context)
    except Exception as e:
        messages.error(request, f'Terjadi kesalahan pada sistem: {str(e)}')
        return redirect('admin_dashboard')


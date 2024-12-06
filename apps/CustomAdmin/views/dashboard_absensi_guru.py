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
def admin_dashboard_absensi_guru(request):
    try:
        absensi_records = record_absensi.objects.filter(user__guru__isnull=False).order_by('-checktime')
        absensi_records_charts = record_absensi.objects.filter(
            user__guru__isnull=False,
            status='hadir'
        ).order_by('-checktime')

        start_date = request.GET.get('start')
        end_date = request.GET.get('end')
        jenjang_selected = request.GET.get('jenjang')
        mata_pelajaran_selected = request.GET.get('mata_pelajaran')
        kelas_selected = request.GET.get('kelas')
        
        # Pastikan start_date dan end_date memiliki nilai default
        if not start_date or not end_date:
            end_date = timezone.localtime(timezone.now()).date()
            start_date = end_date - timezone.timedelta(days=6)
        else:
            try:
                start_date = datetime.strptime(start_date, '%m/%d/%Y').date()
                end_date = datetime.strptime(end_date, '%m/%d/%Y').date()
                messages.info(request, f'Data difilter berdasarkan tanggal: {start_date} - {end_date}')
            except ValueError:
                end_date = timezone.now().date()
                start_date = end_date - timezone.timedelta(days=6)
                messages.error(request, 'Format tanggal tidak valid. Menggunakan rentang tanggal default.')

        # Filter berdasarkan tanggal
        absensi_records = absensi_records.filter(
            checktime__date__gte=start_date,
            checktime__date__lte=end_date
        )
        
        absensi_records_charts = absensi_records_charts.filter(
            checktime__date__gte=start_date,
            checktime__date__lte=end_date
        )

        # Filter tambahan
        filters = {
            'jenjang': ('user__guru__jenjang__nama', jenjang_selected),
            'mata_pelajaran': ('user__guru__mata_pelajaran__nama', mata_pelajaran_selected),
            'kelas': ('user__guru__kelas__nama', kelas_selected)
        }

        for filter_name, (filter_field, filter_value) in filters.items():
            if filter_value:
                absensi_records = absensi_records.filter(**{filter_field: filter_value})
                absensi_records_charts = absensi_records_charts.filter(**{filter_field: filter_value})
                messages.info(request, f'Data difilter berdasarkan {filter_name}: {filter_value}')

        if request.method == 'POST':
            action = request.POST.get('action')
            if action == 'tambah':
                try:
                    user_id = request.POST.get('guru')
                    status = request.POST.get('status')
                    checktime = request.POST.get('checktime')
                    tipe_absensi = request.POST.get('tipe_absensi')
                    
                    user = CustomUser.objects.get(id=user_id)
                    guru = Guru.objects.get(user=user)
                    instalasi = Instalasi.objects.first()
                    
                    if status == 'hadir':
                        # Cek existing record
                        existing_record = record_absensi.objects.filter(
                            user=user,
                            status='hadir',
                            tipe_absensi=tipe_absensi,
                            checktime__date=datetime.strptime(checktime, '%Y-%m-%dT%H:%M').date()
                        ).exists()
                        
                        if existing_record:
                            messages.error(request, f'Sudah ada data absensi {tipe_absensi} untuk hari ini.')
                            return redirect('admin_dashboard_absensi_guru')
                        
                        if tipe_absensi == 'masuk':
                            try:
                                instalasi = Instalasi.objects.first()
                                if not instalasi:
                                    terlambat = 0
                                else:
                                    # Tentukan jam masuk berdasarkan tipe user
                                    jam_masuk = instalasi.jam_masuk_guru
                                    
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
                                # Ambil jam masuk terakhir
                                jam_masuk_record = record_absensi.objects.filter(
                                    user=user,
                                    status='hadir',
                                    tipe_absensi='masuk',
                                    checktime__date=datetime.strptime(checktime, '%Y-%m-%dT%H:%M').date()
                                ).latest('checktime')
                                
                                # waktu_pulang = timezone.make_aware(datetime.strptime(checktime, '%Y-%m-%dT%H:%M'))
                                # selisih_waktu = waktu_pulang - jam_masuk_record.checktime
                                
                                # Gunakan jam_kerja_guru dari instalasi
                                # if selisih_waktu < instalasi.jam_kerja_guru:
                                #     messages.error(request, f'Waktu pulang tidak boleh lebih cepat dari {instalasi.jam_kerja_guru} dari jam masuk.')
                                #     return redirect('admin_dashboard_absensi_guru')
                                terlambat = 0
                            except record_absensi.DoesNotExist:
                                messages.error(request, 'Tidak ada data absensi masuk untuk hari ini.')
                                return redirect('admin_dashboard_absensi_guru')
                        # Buat record baru
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
                        if izin_obj.user is not user:
                            messages.error(request, f'Data izin user {user.username} dengan id {id_izin} tidak ditemukan.')
                            return redirect('admin_dashboard_absensi_guru')
                        record = record_absensi.objects.create(
                            user=user,
                            status=status,
                            id_izin=izin_obj,
                            checktime=checktime,
                            status_verifikasi='diterima',
                            tipe_absensi='izin',
                            terlambat=0
                        )
                        
                    elif status == 'sakit':
                        id_sakit = request.POST.get('id_sakit')
                        sakit_obj = sakit.objects.get(id=id_sakit)
                        if sakit_obj.user is not user:
                            messages.error(request, f'Data sakit user {user.username} dengan id {id_sakit} tidak ditemukan.')
                            return redirect('admin_dashboard_absensi_guru')
                        record = record_absensi.objects.create(
                            user=user,
                            status=status,
                            id_sakit=sakit_obj,
                            checktime=checktime,
                            status_verifikasi='diterima',
                            tipe_absensi='sakit',
                            terlambat=0
                        )
                        
                    messages.success(request, 'Data absensi berhasil ditambahkan.')
                    
                except CustomUser.DoesNotExist:
                    messages.error(request, 'Pengguna tidak ditemukan.')
                except Guru.DoesNotExist:
                    messages.error(request, 'Data guru tidak ditemukan.')
                except izin.DoesNotExist:
                    messages.error(request, 'Data izin tidak ditemukan.')
                except sakit.DoesNotExist:
                    messages.error(request, 'Data sakit tidak ditemukan.')
                except Exception as e:
                    messages.error(request, f'Terjadi kesalahan: {str(e)}')
                
                return redirect('admin_dashboard_absensi_guru')
              
            elif action == 'edit':
                absensi_id = request.POST.get('id')
                checktime = request.POST.get('tanggal_waktu')
                status = request.POST.get('status')
                status_verifikasi = request.POST.get('status_verifikasi')
                tipe_absensi = request.POST.get('tipe_absensi')
                
                try:
                    absensi = record_absensi.objects.get(id=absensi_id)
                    user = absensi.user
                    
                    # Ubah format waktu dengan benar
                    try:
                        checktime_datetime = datetime.strptime(checktime, '%Y-%m-%dT%H:%M')
                        checktime_aware = timezone.make_aware(checktime_datetime)
                        absensi.checktime = checktime_aware
                    except ValueError:
                        messages.error(request, 'Format tanggal dan waktu tidak valid')
                        return redirect('admin_dashboard_absensi_guru')
                        
                    if status == 'izin':
                        id_izin = request.POST.get('id_izin')
                        absensi.id_izin = izin.objects.get(id=id_izin) if id_izin else None
                        absensi.id_sakit = None
                        absensi.terlambat = 0
                    elif status == 'sakit':
                        id_sakit = request.POST.get('id_sakit')
                        absensi.id_sakit = sakit.objects.get(id=id_sakit) if id_sakit else None
                        absensi.id_izin = None
                        absensi.terlambat = 0
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
                            return redirect('admin_dashboard_absensi_guru')
                        
                        if tipe_absensi == 'masuk':
                            try:
                                instalasi = Instalasi.objects.first()
                                if not instalasi:
                                    absensi.terlambat = 0
                                else:
                                    # Tentukan jam masuk berdasarkan tipe user
                                    jam_masuk = instalasi.jam_masuk_guru
                                    
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
                                # Ambil jam masuk terakhir guru
                                jam_masuk = record_absensi.objects.filter(
                                    user=user,
                                    status='hadir',
                                    tipe_absensi='masuk',
                                    checktime__date=datetime.strptime(checktime, '%Y-%m-%dT%H:%M').date()
                                ).latest('checktime')
                                
                                # Ambil jam kerja dari Instalasi
                                # instalasi = Instalasi.objects.first()
                                # jam_kerja = instalasi.jam_kerja_guru
                                
                                # if jam_kerja:
                                #     # Hitung selisih waktu
                                #     waktu_pulang = checktime_aware
                                #     selisih_waktu = waktu_pulang - jam_masuk.checktime
                                
                                #     if selisih_waktu < jam_kerja:
                                #         messages.error(request, f'Waktu pulang tidak boleh lebih cepat dari {jam_kerja} dari jam masuk.')
                                #         return redirect('admin_dashboard_absensi_guru')
                                terlambat = 0
                            except record_absensi.DoesNotExist:
                                messages.error(request, 'Tidak ada data absensi masuk untuk hari ini. Guru harus absen masuk terlebih dahulu.')
                                return redirect('admin_dashboard_absensi_guru')
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
                
                return redirect('admin_dashboard_absensi_guru')
              
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
                return redirect('admin_dashboard_absensi_guru')

        daily_counts = absensi_records_charts.annotate(date=TruncDate('checktime')).values('date').annotate(
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

        total_hadir = sum(hadir_data)
        total_sakit = sum(sakit_data)
        total_izin = sum(izin_data)
        total_all = total_hadir + total_sakit + total_izin

        hadir_percentage = round((total_hadir / total_all) * 100) if total_all > 0 else 0
        sakit_percentage = round((total_sakit / total_all) * 100) if total_all > 0 else 0
        izin_percentage = round((total_izin / total_all) * 100) if total_all > 0 else 0

        # untuk edit data
        edit_data_absensi_guru = []
        edit_id = request.GET.get('id')
        if edit_id:
            for record in record_absensi.objects.filter(id=edit_id).select_related('user'):
                guru = record.user.guru_set.first()
                record_data = {
                    'id': record.id,
                    'guru': guru.nama if guru else None,
                    'checktime': timezone.localtime(record.checktime).strftime('%Y-%m-%d %H:%M'),
                    'status': record.status,
                    'id_izin': record.id_izin.id if record.id_izin else None,
                    'id_sakit': record.id_sakit.id if record.id_sakit else None,
                    'status_verifikasi': record.status_verifikasi,
                    'tipe_absensi': record.tipe_absensi,
                }
                edit_data_absensi_guru.append(record_data)

        context = get_context()
        context.update({
            'guru': True,
            
            # Data Series
            'ds_title': 'Statistik Absensi Guru',
            'ds_percentage': f'{hadir_percentage}%',
            'ds_name_1': 'Hadir',
            'ds_data_1': hadir_data,
            'ds_name_2': 'Sakit',
            'ds_data_2': sakit_data,
            'ds_name_3': 'Izin',
            'ds_data_3': izin_data,
            'ds_categories_json': json.dumps(dates),
            'ds_month': f"{start_date.strftime('%d %B')} - {end_date.strftime('%d %B %Y')}",
            
            # Pie Charts
            'pc_title': 'Statistik Absensi Guru',
            'pc_month': f"{start_date.strftime('%d %B')} - {end_date.strftime('%d %B %Y')}",
            'pc_data': json.dumps([total_izin, total_sakit, total_hadir]),
            'pc_labels': json.dumps(['Izin', 'Sakit', 'Hadir']),
            
            # Radial Charts
            'rc_title': 'Statistik Absensi Guru',
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
            
            # Table data
            'table_columns': ['ID RECORD', 'NUPTK', 'Nama Guru', 'Jenjang', 'Kelas', 'Mata Pelajaran', 'Checktime', 'Status', 'Tipe Absensi', 'Terlambat (menit)', 'Mesin'],
            'table_data': absensi_records.values_list(
                'id',
                'user__guru__nuptk', 
                'user__guru__nama',
                'user__guru__jenjang__nama',
                'user__guru__kelas__nama',
                'user__guru__mata_pelajaran__nama',
                'checktime',
                'status',
                'tipe_absensi',
                'terlambat',
                'mesin'
            ),
            
            'start_date': start_date.strftime('%m/%d/%Y'),
            'end_date': end_date.strftime('%m/%d/%Y'),
            'selected_jenjang': jenjang_selected,
            'selected_mata_pelajaran': mata_pelajaran_selected,
            'selected_kelas': kelas_selected,
            
            'total_data_table': absensi_records.count(),
            
            # form tambah record
            'guru_list': Guru.objects.all(),
            'id_izin': izin.objects.exclude(record_absensi__id_izin__isnull=False),
            'id_sakit': sakit.objects.exclude(record_absensi__id_sakit__isnull=False),
            
            # form edit record
            'edit_data_absensi_guru': edit_data_absensi_guru,
            
            'status_list': ['hadir', 'izin', 'sakit'],
            
            # Jenjang, Mata Pelajaran, dan Kelas
            'jenjang_list': jenjang.objects.all(),
            'mata_pelajaran_list': mata_pelajaran.objects.all(),
            'kelas_list': kelas.objects.all(),
            'status_verifikasi_list': ['menunggu', 'diterima', 'ditolak'],
            'tipe_absensi_list': ['masuk', 'pulang'],
        })
        return render(request, 'CustomAdmin/admin_dashboard_absensi_guru.html', context)
        
    except Exception as e:
        messages.error(request, f'Terjadi kesalahan pada sistem: {str(e)}')
        return redirect('admin_dashboard')

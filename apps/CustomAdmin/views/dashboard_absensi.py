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
def admin_dashboard_absensi_siswa(request):
    try:
        absensi_records = record_absensi.objects.filter(user__siswa__isnull=False, status_verifikasi='diterima').order_by('-checktime')
        absensi_records_charts = record_absensi.objects.filter(user__siswa__isnull=False, status_verifikasi='diterima', tipe_absensi__in=['masuk', 'sakit', 'izin']).order_by('-checktime')

        start_date = request.GET.get('start')
        end_date = request.GET.get('end')
        jenjang_selected = request.GET.get('jenjang')
        kelas_selected = request.GET.get('kelas')
        
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

        absensi_records = absensi_records.filter(
            checktime__date__gte=start_date,
            checktime__date__lte=end_date
        )
        
        absensi_records_charts = absensi_records_charts.filter(
            checktime__date__gte=start_date,
            checktime__date__lte=end_date
        )

        # Filter berdasarkan jenjang
        if jenjang_selected:
            absensi_records = absensi_records.filter(user__siswa__jenjang__nama=jenjang_selected)
            absensi_records_charts = absensi_records_charts.filter(user__siswa__jenjang__nama=jenjang_selected)
            messages.info(request, f'Data difilter berdasarkan jenjang: {jenjang_selected}')

        # Filter berdasarkan kelas
        if kelas_selected:
            absensi_records = absensi_records.filter(user__siswa__kelas__nama=kelas_selected)
            absensi_records_charts = absensi_records_charts.filter(user__siswa__kelas__nama=kelas_selected)
            messages.info(request, f'Data difilter berdasarkan kelas: {kelas_selected}')

        if request.method == 'POST':
            try:
                action = request.POST.get('action')
                
                if action == 'tambah':
                    try:
                        siswa_id = request.POST.get('siswa')
                        status = request.POST.get('status')
                        checktime = request.POST.get('checktime')
                        tipe_absensi = request.POST.get('tipe_absensi')

                        if not all([siswa_id, status, checktime]):
                            raise ValueError("Semua field harus diisi")

                        siswa = Siswa.objects.get(id=siswa_id)
                        user = siswa.user
                        
                        if status == 'hadir':
                            
                            # Cek apakah sudah ada absensi dengan tipe yang sama untuk hari ini
                            existing_record = record_absensi.objects.filter(
                                user=user,
                                status='hadir',
                                tipe_absensi=tipe_absensi,
                                checktime__date=datetime.strptime(checktime, '%Y-%m-%dT%H:%M').date()
                            ).exists()
                            
                            if existing_record:
                                messages.error(request, f'Sudah ada data absensi {tipe_absensi} untuk hari ini.')
                                return redirect('admin_dashboard_absensi_siswa')
                            
                            if tipe_absensi == 'pulang':
                                # Ambil jam masuk terakhir siswa
                                jam_masuk = record_absensi.objects.filter(
                                    user=user,
                                    status='hadir',
                                    tipe_absensi='masuk',
                                    checktime__date=datetime.strptime(checktime, '%Y-%m-%dT%H:%M').date()
                                ).latest('checktime')
                                
                                # Ambil jam kerja dari Instalasi
                                instalasi = Instalasi.objects.first()
                                jam_kerja = instalasi.jam_kerja
                                
                                # Hitung selisih waktu
                                waktu_pulang = datetime.strptime(checktime, '%Y-%m-%dT%H:%M')
                                selisih_waktu = waktu_pulang - jam_masuk.checktime.replace(tzinfo=None)
                                
                                if selisih_waktu < jam_kerja:
                                    messages.error(request, f'Waktu pulang tidak boleh lebih cepat dari {jam_kerja} dari jam masuk.')
                                    return redirect('admin_dashboard_absensi_siswa')
                            
                            record = record_absensi.objects.create(
                                user=user,
                                status=status,
                                checktime=checktime,
                                status_verifikasi='diterima',
                                tipe_absensi=tipe_absensi
                            )
                        elif status == 'izin':
                            id_izin = request.POST.get('id_izin')
                            izin_obj = izin.objects.get(id=id_izin)
                            record = record_absensi.objects.create(
                                user=user,
                                status=status,
                                id_izin=izin_obj,
                                checktime=checktime,
                                status_verifikasi='diterima'
                            )
                        elif status == 'sakit':
                            id_sakit = request.POST.get('id_sakit')
                            sakit_obj = sakit.objects.get(id=id_sakit)
                            record = record_absensi.objects.create(
                                user=user,
                                status=status,
                                id_sakit=sakit_obj,
                                checktime=checktime,
                                status_verifikasi='diterima'
                            )
                        
                        messages.success(request, f'Data absensi siswa {siswa.nama} berhasil ditambahkan dengan status {status}.')
                        
                    except ValueError as e:
                        messages.error(request, str(e))
                    except Siswa.DoesNotExist:
                        messages.error(request, 'Siswa tidak ditemukan')
                    except (izin.DoesNotExist, sakit.DoesNotExist):
                        messages.error(request, 'Data izin/sakit tidak ditemukan')
                    except record_absensi.DoesNotExist:
                        messages.error(request, 'Record absensi tidak ditemukan')
                    except Exception as e:
                        messages.error(request, f'Terjadi kesalahan saat menambah data: {str(e)}')
                
                elif action == 'hapus':
                    try:
                        selected_ids = request.POST.get('selectedIds')
                        if not selected_ids:
                            raise ValueError('Tidak ada data yang dipilih untuk dihapus')
                            
                        valid_ids = [int(id.strip()) for id in selected_ids.split(',') if id.strip().isdigit()]
                        if not valid_ids:
                            raise ValueError('Tidak ada ID valid yang dipilih untuk dihapus')
                            
                        deleted_count = record_absensi.objects.filter(id__in=valid_ids).delete()[0]
                        messages.success(request, f'{deleted_count} data absensi siswa berhasil dihapus')
                        
                    except ValueError as e:
                        messages.error(request, str(e))
                    except Exception as e:
                        messages.error(request, f'Terjadi kesalahan saat menghapus data: {str(e)}')
                
                elif action == 'edit':
                    try:
                        absensi_id = request.POST.get('id')
                        checktime = request.POST.get('tanggal_waktu')
                        status = request.POST.get('status')
                        status_verifikasi = request.POST.get('status_verifikasi')
                        tipe_absensi = request.POST.get('tipe_absensi')

                        if not all([absensi_id, checktime, status, status_verifikasi]):
                            raise ValueError("Semua field harus diisi")

                        record = record_absensi.objects.get(id=absensi_id)
                        old_status = record.status
                        record.checktime = checktime
                        record.status = status
                        record.status_verifikasi = status_verifikasi
                        
                        if status == 'izin':
                            id_izin = request.POST.get('id_izin')
                            izin_obj = izin.objects.get(id=id_izin)
                            record.id_izin = izin_obj
                            record.id_sakit = None
                        elif status == 'sakit':
                            id_sakit = request.POST.get('id_sakit')
                            sakit_obj = sakit.objects.get(id=id_sakit)
                            record.id_sakit = sakit_obj
                            record.id_izin = None
                        else:
                            record.id_izin = None
                            record.id_sakit = None
                            record.tipe_absensi = tipe_absensi
                            
                            # Cek apakah sudah ada absensi dengan tipe yang sama untuk hari ini
                            existing_record = record_absensi.objects.filter(
                                user=record.user,
                                status='hadir',
                                tipe_absensi=tipe_absensi,
                                checktime__date=record.checktime.date()
                            ).exists()
                            
                            if existing_record:
                                messages.error(request, f'Sudah ada data absensi {tipe_absensi} untuk hari ini.')
                                return redirect('admin_dashboard_absensi_siswa')
                            if tipe_absensi:
                                if tipe_absensi == 'pulang':
                                    try: 
                                        # Ambil jam masuk terakhir siswa
                                        jam_masuk = record_absensi.objects.filter(
                                            user=record.user,
                                            status='hadir',
                                            tipe_absensi='masuk',
                                            checktime__date=record.checktime.date()
                                        ).latest('checktime')
                                        
                                        # Ambil jam kerja dari Instalasi
                                        instalasi = Instalasi.objects.first()
                                        jam_kerja = instalasi.jam_kerja
                                        
                                        # Hitung selisih waktu
                                        waktu_pulang = datetime.strptime(record.checktime, '%Y-%m-%dT%H:%M')
                                        selisih_waktu = waktu_pulang - jam_masuk.checktime.replace(tzinfo=None)
                                        
                                        if selisih_waktu < jam_kerja:
                                            messages.error(request, f'Waktu pulang tidak boleh lebih cepat dari {jam_kerja} dari jam masuk.')
                                            return redirect('admin_dashboard_absensi_siswa')
                                    except record_absensi.DoesNotExist:
                                        messages.error(request, 'Tidak ada data absensi masuk untuk hari ini. Siswa harus absen masuk terlebih dahulu.')
                                        return redirect('admin_dashboard_absensi_siswa')
                            
                        record.save()
                        messages.success(request, f'Data absensi siswa berhasil diperbarui dari {old_status} menjadi {status}.')
                        
                    except ValueError as e:
                        messages.error(request, str(e))
                    except record_absensi.DoesNotExist:
                        messages.error(request, 'Data absensi tidak ditemukan')
                    except (izin.DoesNotExist, sakit.DoesNotExist):
                        messages.error(request, 'Data izin/sakit tidak ditemukan')
                    except Exception as e:
                        messages.error(request, f'Terjadi kesalahan saat mengedit data: {str(e)}')

            except Exception as e:
                messages.error(request, f'Terjadi kesalahan pada aksi: {str(e)}')

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
        edit_data_absensi_siswa = []
        edit_id = request.GET.get('id')
        if edit_id:
            for record in record_absensi.objects.filter(id=edit_id).select_related('user'):
                siswa = record.user.siswa_set.first()
                record_data = {
                    'id': record.id,
                    'siswa': siswa.nama if siswa else None,
                    'checktime': timezone.localtime(record.checktime).strftime('%Y-%m-%d %H:%M:%S'),
                    'status': record.status,
                    'id_izin': record.id_izin.id if record.id_izin else None,
                    'id_sakit': record.id_sakit.id if record.id_sakit else None,
                    'status_verifikasi': record.status_verifikasi,
                    'tipe_absensi': record.tipe_absensi,
                }
                edit_data_absensi_siswa.append(record_data)

        context = get_context()
        context.update({
            'siswa': True,
            
            # Data Series
            'ds_title': 'Statistik Absensi Siswa',
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
            'pc_title': 'Statistik Absensi Siswa',
            'pc_month': f"{start_date.strftime('%d %B')} - {end_date.strftime('%d %B %Y')}",
            'pc_data': json.dumps([total_izin, total_sakit, total_hadir]),
            'pc_labels': json.dumps(['Izin', 'Sakit', 'Hadir']),
            
            # Radial Charts
            'rc_title': 'Statistik Absensi Siswa',
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
            'table_columns': ['ID RECORD', 'NISN', 'Nama Siswa', 'Jenjang', 'Kelas', 'Checktime', 'Status', 'Tipe Absensi'],
            'table_data': absensi_records.values_list(
                'id',
                'user__siswa__nisn',
                'user__siswa__nama',
                'user__siswa__jenjang__nama',
                'user__siswa__kelas__nama',
                'checktime',
                'status',
                'tipe_absensi'
            ),
            
            'start_date': start_date.strftime('%m/%d/%Y'),
            'end_date': end_date.strftime('%m/%d/%Y'),
            'selected_jenjang': jenjang,
            'selected_kelas': kelas,
            
            'total_data_table': absensi_records.count(),
            
            # form tambah record
            'siswa_list': Siswa.objects.all(),
            'id_izin': izin.objects.exclude(record_absensi__id_izin__isnull=False),
            'id_sakit': sakit.objects.exclude(record_absensi__id_sakit__isnull=False),
            
            # form edit record
            'edit_data_absensi_siswa': edit_data_absensi_siswa,
            
            'status_list': ['hadir', 'izin', 'sakit'],
            
            # Kelas dan Jenjang
            'kelas_list': kelas.objects.all(),
            'jenjang_list': jenjang.objects.all(),
            'status_verifikasi_list': ['menunggu', 'diterima', 'ditolak'],
            'tipe_absensi_list': ['masuk', 'pulang'],
        })
        return render(request, 'CustomAdmin/admin_dashboard_absensi_siswa.html', context)
        
    except Exception as e:
        messages.error(request, f'Terjadi kesalahan pada sistem: {str(e)}')
        return redirect('admin_dashboard')

@cek_instalasi
@superuser_required
def admin_dashboard_absensi_guru(request):
    try:
        absensi_records = record_absensi.objects.filter(user__guru__isnull=False, status_verifikasi='diterima').order_by('-checktime')
        absensi_records_charts = record_absensi.objects.filter(user__guru__isnull=False, status_verifikasi='diterima', tipe_absensi__in=['masuk', 'sakit', 'izin']).order_by('-checktime')

        start_date = request.GET.get('start')
        end_date = request.GET.get('end')
        jenjang_selected = request.GET.get('jenjang')
        mata_pelajaran_selected = request.GET.get('mata_pelajaran')
        kelas_selected = request.GET.get('kelas')
        
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

        absensi_records = absensi_records.filter(
            checktime__date__gte=start_date,
            checktime__date__lte=end_date
        )
        
        absensi_records_charts = absensi_records_charts.filter(
            checktime__date__gte=start_date,
            checktime__date__lte=end_date
        )

        # Filter berdasarkan jenjang
        if jenjang_selected:
            absensi_records = absensi_records.filter(user__guru__jenjang__nama=jenjang_selected)
            absensi_records_charts = absensi_records_charts.filter(user__guru__jenjang__nama=jenjang_selected)
            messages.info(request, f'Data difilter berdasarkan jenjang: {jenjang_selected}')

        # Filter berdasarkan mata pelajaran
        if mata_pelajaran_selected:
            absensi_records = absensi_records.filter(user__guru__mata_pelajaran__nama=mata_pelajaran_selected)
            absensi_records_charts = absensi_records_charts.filter(user__guru__mata_pelajaran__nama=mata_pelajaran_selected)
            messages.info(request, f'Data difilter berdasarkan mata pelajaran: {mata_pelajaran_selected}')

        # Filter berdasarkan kelas
        if kelas_selected:
            absensi_records = absensi_records.filter(user__guru__kelas__nama=kelas_selected)
            absensi_records_charts = absensi_records_charts.filter(user__guru__kelas__nama=kelas_selected)
            messages.info(request, f'Data difilter berdasarkan kelas: {kelas_selected}')

        if request.method == 'POST':
            try:
                action = request.POST.get('action')
                
                if action == 'tambah':
                    try:
                        guru_id = request.POST.get('guru')
                        status = request.POST.get('status')
                        checktime = request.POST.get('checktime')
                        tipe_absensi = request.POST.get('tipe_absensi')

                        if not all([guru_id, status, checktime]):
                            raise ValueError("Semua field harus diisi")

                        guru = Guru.objects.get(id=guru_id)
                        user = guru.user
                        
                        if status == 'hadir':
                            # Cek apakah sudah ada absensi dengan tipe yang sama untuk hari ini
                            existing_record = record_absensi.objects.filter(
                                user=user,
                                status='hadir',
                                tipe_absensi=tipe_absensi,
                                checktime__date=datetime.strptime(checktime, '%Y-%m-%dT%H:%M').date()
                            ).exists()
                            
                            if existing_record:
                                messages.error(request, f'Sudah ada data absensi {tipe_absensi} untuk hari ini.')
                                return redirect('admin_dashboard_absensi_guru')
                            
                            if tipe_absensi == 'pulang':
                                # Ambil jam masuk terakhir guru
                                jam_masuk = record_absensi.objects.filter(
                                    user=user,
                                    status='hadir',
                                    tipe_absensi='masuk',
                                    checktime__date=datetime.strptime(checktime, '%Y-%m-%dT%H:%M').date()
                                ).latest('checktime')
                                
                                # Ambil jam kerja dari Instalasi
                                instalasi = Instalasi.objects.first()
                                jam_kerja = instalasi.jam_kerja
                                
                                # Hitung selisih waktu
                                waktu_pulang = datetime.strptime(checktime, '%Y-%m-%dT%H:%M')
                                selisih_waktu = waktu_pulang - jam_masuk.checktime.replace(tzinfo=None)
                                
                                if selisih_waktu < jam_kerja:
                                    messages.error(request, f'Waktu pulang tidak boleh lebih cepat dari {jam_kerja} dari jam masuk.')
                                    return redirect('admin_dashboard_absensi_guru')
                            
                            record = record_absensi.objects.create(
                                user=user,
                                status=status,
                                checktime=checktime,
                                status_verifikasi='diterima',
                                tipe_absensi=tipe_absensi
                            )
                        elif status == 'izin':
                            id_izin = request.POST.get('id_izin')
                            izin_obj = izin.objects.get(id=id_izin)
                            record = record_absensi.objects.create(
                                user=user,
                                status=status,
                                id_izin=izin_obj,
                                checktime=checktime,
                                status_verifikasi='diterima'
                            )
                        elif status == 'sakit':
                            id_sakit = request.POST.get('id_sakit')
                            sakit_obj = sakit.objects.get(id=id_sakit)
                            record = record_absensi.objects.create(
                                user=user,
                                status=status,
                                id_sakit=sakit_obj,
                                checktime=checktime,
                                status_verifikasi='diterima'
                            )
                        
                        messages.success(request, f'Data absensi guru {guru.nama} berhasil ditambahkan dengan status {status}.')
                        
                    except ValueError as e:
                        messages.error(request, str(e))
                    except Guru.DoesNotExist:
                        messages.error(request, 'Guru tidak ditemukan')
                    except (izin.DoesNotExist, sakit.DoesNotExist):
                        messages.error(request, 'Data izin/sakit tidak ditemukan')
                    except record_absensi.DoesNotExist:
                        messages.error(request, 'Record absensi tidak ditemukan')
                    except Exception as e:
                        messages.error(request, f'Terjadi kesalahan saat menambah data: {str(e)}')
                    
                    return redirect('admin_dashboard_absensi_guru')
                
                elif action == 'hapus':
                    try:
                        selected_ids = request.POST.get('selectedIds')
                        if not selected_ids:
                            raise ValueError('Tidak ada data yang dipilih untuk dihapus')
                            
                        valid_ids = [int(id.strip()) for id in selected_ids.split(',') if id.strip().isdigit()]
                        if not valid_ids:
                            raise ValueError('Tidak ada ID valid yang dipilih untuk dihapus')
                            
                        deleted_count = record_absensi.objects.filter(id__in=valid_ids).delete()[0]
                        messages.success(request, f'{deleted_count} data absensi guru berhasil dihapus')
                        
                    except ValueError as e:
                        messages.error(request, str(e))
                    except Exception as e:
                        messages.error(request, f'Terjadi kesalahan saat menghapus data: {str(e)}')
                    
                    return redirect('admin_dashboard_absensi_guru')
                
                elif action == 'edit':
                    try:
                        absensi_id = request.POST.get('id')
                        checktime = request.POST.get('tanggal_waktu')
                        status = request.POST.get('status')
                        status_verifikasi = request.POST.get('status_verifikasi')
                        tipe_absensi = request.POST.get('tipe_absensi')

                        if not all([absensi_id, checktime, status, status_verifikasi]):
                            raise ValueError("Semua field harus diisi")

                        record = record_absensi.objects.get(id=absensi_id)
                        old_status = record.status
                        
                        record.checktime = checktime
                        record.status = status
                        record.status_verifikasi = status_verifikasi
                        if status == 'izin':
                            id_izin = request.POST.get('id_izin')
                            izin_obj = izin.objects.get(id=id_izin)
                            record.id_izin = izin_obj
                            record.id_sakit = None
                        elif status == 'sakit':
                            id_sakit = request.POST.get('id_sakit')
                            sakit_obj = sakit.objects.get(id=id_sakit)
                            record.id_sakit = sakit_obj
                            record.id_izin = None
                        else:
                            record.id_izin = None
                            record.id_sakit = None
                            
                            # Cek apakah sudah ada absensi dengan tipe yang sama untuk hari ini
                            existing_record = record_absensi.objects.filter(
                                user=record.user,
                                status='hadir',
                                tipe_absensi=tipe_absensi,
                                checktime__date=record.checktime.date()
                            ).exists()
                            
                            if existing_record:
                                messages.error(request, f'Sudah ada data absensi {tipe_absensi} untuk hari ini.')
                                return redirect('admin_dashboard_absensi_guru')
                            if tipe_absensi:
                                if tipe_absensi == 'pulang':
                                    try: 
                                        # Ambil jam masuk terakhir guru
                                        jam_masuk = record_absensi.objects.filter(
                                            user=record.user,
                                            status='hadir',
                                            tipe_absensi='masuk',
                                            checktime__date=record.checktime.date()
                                        ).latest('checktime')
                                        
                                        # Ambil jam kerja dari Instalasi
                                        instalasi = Instalasi.objects.first()
                                        jam_kerja = instalasi.jam_kerja
                                        
                                        # Hitung selisih waktu
                                        waktu_pulang = datetime.strptime(checktime, '%Y-%m-%dT%H:%M')
                                        selisih_waktu = waktu_pulang - jam_masuk.checktime.replace(tzinfo=None)
                                        
                                        if selisih_waktu < jam_kerja:
                                            messages.error(request, f'Waktu pulang tidak boleh lebih cepat dari {jam_kerja} dari jam masuk.')
                                            return redirect('admin_dashboard_absensi_guru')
                                    except record_absensi.DoesNotExist:
                                        messages.error(request, 'Tidak ada data absensi masuk untuk hari ini. Guru harus absen masuk terlebih dahulu.')
                                        return redirect('admin_dashboard_absensi_guru')
                            
                        record.save()
                        messages.success(request, f'Data absensi guru berhasil diperbarui dari {old_status} menjadi {status}.')
                        
                    except ValueError as e:
                        messages.error(request, str(e))
                    except record_absensi.DoesNotExist:
                        messages.error(request, 'Data absensi tidak ditemukan')
                    except (izin.DoesNotExist, sakit.DoesNotExist):
                        messages.error(request, 'Data izin/sakit tidak ditemukan')
                    except Exception as e:
                        messages.error(request, f'Terjadi kesalahan saat mengedit data: {str(e)}')
                    
                    return redirect('admin_dashboard_absensi_guru')

            except Exception as e:
                messages.error(request, f'Terjadi kesalahan pada aksi: {str(e)}')

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
                    'checktime': timezone.localtime(record.checktime).strftime('%Y-%m-%d %H:%M:%S'),
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
            'table_columns': ['ID RECORD', 'NUPTK', 'Nama Guru', 'Jenjang', 'Kelas', 'Mata Pelajaran', 'Checktime', 'Status', 'Tipe Absensi'],
            'table_data': absensi_records.values_list(
                'id',
                'user__guru__nuptk',
                'user__guru__nama',
                'user__guru__jenjang__nama',
                'user__guru__kelas__nama',
                'user__guru__mata_pelajaran__nama',
                'checktime',
                'status',
                'tipe_absensi'
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

@cek_instalasi
@superuser_required
def admin_dashboard_absensi_karyawan(request):
    try:
        absensi_records = record_absensi.objects.filter(user__karyawan__isnull=False, status_verifikasi='diterima').order_by('-checktime')
        absensi_records_charts = record_absensi.objects.filter(user__karyawan__isnull=False, status_verifikasi='diterima', tipe_absensi__in=['masuk', 'sakit', 'izin']).order_by('-checktime')

        start_date = request.GET.get('start')
        end_date = request.GET.get('end')
        jabatan_selected = request.GET.get('jabatan')
        
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

        absensi_records = absensi_records.filter(
            checktime__date__gte=start_date,
            checktime__date__lte=end_date
        )
        
        absensi_records_charts = absensi_records_charts.filter(
            checktime__date__gte=start_date,
            checktime__date__lte=end_date
        )

        # Filter berdasarkan jabatan
        if jabatan_selected:
            absensi_records = absensi_records.filter(user__karyawan__jabatan__nama=jabatan_selected)
            absensi_records_charts = absensi_records_charts.filter(user__karyawan__jabatan__nama=jabatan_selected)
            messages.info(request, f'Data difilter berdasarkan jabatan: {jabatan_selected}')

        if request.method == 'POST':
            try:
                action = request.POST.get('action')
                
                if action == 'tambah':
                    try:
                        karyawan_id = request.POST.get('karyawan')
                        status = request.POST.get('status')
                        checktime = request.POST.get('checktime')
                        tipe_absensi = request.POST.get('tipe_absensi')

                        if not all([karyawan_id, status, checktime]):
                            raise ValueError("Semua field harus diisi")

                        karyawan = Karyawan.objects.get(id=karyawan_id)
                        user = karyawan.user
                        
                        if status == 'hadir':
                            # Cek apakah sudah ada absensi dengan tipe yang sama untuk hari ini
                            existing_record = record_absensi.objects.filter(
                                user=user,
                                status='hadir',
                                tipe_absensi=tipe_absensi,
                                checktime__date=datetime.strptime(checktime, '%Y-%m-%dT%H:%M').date()
                            ).exists()
                            
                            if existing_record:
                                messages.error(request, f'Sudah ada data absensi {tipe_absensi} untuk hari ini.')
                                return redirect('admin_dashboard_absensi_karyawan')
                            
                            if tipe_absensi == 'pulang':
                                try:
                                    # Ambil jam masuk terakhir karyawan
                                    jam_masuk = record_absensi.objects.filter(
                                        user=user,
                                        status='hadir',
                                        tipe_absensi='masuk',
                                        checktime__date=datetime.strptime(checktime, '%Y-%m-%dT%H:%M').date()
                                    ).latest('checktime')
                                    
                                    # Ambil jam kerja dari Instalasi
                                    instalasi = Instalasi.objects.first()
                                    jam_kerja = instalasi.jam_kerja
                                    
                                    # Hitung selisih waktu
                                    waktu_pulang = datetime.strptime(checktime, '%Y-%m-%dT%H:%M')
                                    selisih_waktu = waktu_pulang - jam_masuk.checktime.replace(tzinfo=None)
                                    
                                    if selisih_waktu < jam_kerja:
                                        messages.error(request, f'Waktu pulang tidak boleh lebih cepat dari {jam_kerja} dari jam masuk.')
                                        return redirect('admin_dashboard_absensi_karyawan')
                                except record_absensi.DoesNotExist:
                                    messages.error(request, 'Tidak ada data absensi masuk untuk hari ini. Karyawan harus absen masuk terlebih dahulu.')
                                    return redirect('admin_dashboard_absensi_karyawan')
                            
                            record = record_absensi.objects.create(
                                user=user,
                                status=status,
                                checktime=checktime,
                                status_verifikasi='diterima',
                                tipe_absensi=tipe_absensi
                            )
                        elif status == 'izin':
                            id_izin = request.POST.get('id_izin')
                            izin_obj = izin.objects.get(id=id_izin)
                            record = record_absensi.objects.create(
                                user=user,
                                status=status,
                                id_izin=izin_obj,
                                checktime=checktime,
                                status_verifikasi='diterima'
                            )
                        elif status == 'sakit':
                            id_sakit = request.POST.get('id_sakit')
                            sakit_obj = sakit.objects.get(id=id_sakit)
                            record = record_absensi.objects.create(
                                user=user,
                                status=status,
                                id_sakit=sakit_obj,
                                checktime=checktime,
                                status_verifikasi='diterima'
                            )
                        
                        messages.success(request, f'Data absensi karyawan {karyawan.nama} berhasil ditambahkan dengan status {status}.')
                        
                    except ValueError as e:
                        messages.error(request, str(e))
                    except Karyawan.DoesNotExist:
                        messages.error(request, 'Karyawan tidak ditemukan')
                    except (izin.DoesNotExist, sakit.DoesNotExist):
                        messages.error(request, 'Data izin/sakit tidak ditemukan')
                    except record_absensi.DoesNotExist:
                        messages.error(request, 'Record absensi tidak ditemukan')
                    except Exception as e:
                        messages.error(request, f'Terjadi kesalahan saat menambah data: {str(e)}')
                    
                    return redirect('admin_dashboard_absensi_karyawan')
                
                elif action == 'hapus':
                    try:
                        selected_ids = request.POST.get('selectedIds')
                        if not selected_ids:
                            raise ValueError('Tidak ada data yang dipilih untuk dihapus')
                            
                        valid_ids = [int(id.strip()) for id in selected_ids.split(',') if id.strip().isdigit()]
                        if not valid_ids:
                            raise ValueError('Tidak ada ID valid yang dipilih untuk dihapus')
                            
                        deleted_count = record_absensi.objects.filter(id__in=valid_ids).delete()[0]
                        messages.success(request, f'{deleted_count} data absensi karyawan berhasil dihapus')
                        
                    except ValueError as e:
                        messages.error(request, str(e))
                    except Exception as e:
                        messages.error(request, f'Terjadi kesalahan saat menghapus data: {str(e)}')
                    
                    return redirect('admin_dashboard_absensi_karyawan')
                
                elif action == 'edit':
                    try:
                        absensi_id = request.POST.get('id')
                        checktime = request.POST.get('tanggal_waktu')
                        status = request.POST.get('status')
                        status_verifikasi = request.POST.get('status_verifikasi')
                        tipe_absensi = request.POST.get('tipe_absensi')

                        if not all([absensi_id, checktime, status, status_verifikasi]):
                            raise ValueError("Semua field harus diisi")

                        record = record_absensi.objects.get(id=absensi_id)
                        old_status = record.status
                        record.checktime = checktime
                        record.status = status
                        record.status_verifikasi = status_verifikasi
                        
                        if status == 'izin':
                            id_izin = request.POST.get('id_izin')
                            izin_obj = izin.objects.get(id=id_izin)
                            record.id_izin = izin_obj
                            record.id_sakit = None
                        elif status == 'sakit':
                            id_sakit = request.POST.get('id_sakit')
                            sakit_obj = sakit.objects.get(id=id_sakit)
                            record.id_sakit = sakit_obj
                            record.id_izin = None
                        else:
                            record.id_izin = None
                            record.id_sakit = None
                            record.tipe_absensi = tipe_absensi
                            
                            # Cek apakah sudah ada absensi dengan tipe yang sama untuk hari ini
                            existing_record = record_absensi.objects.filter(
                                user=record.user,
                                status='hadir',
                                tipe_absensi=tipe_absensi,
                                checktime__date=record.checktime.date()
                            ).exists()
                            
                            if existing_record:
                                messages.error(request, f'Sudah ada data absensi {tipe_absensi} untuk hari ini.')
                                return redirect('admin_dashboard_absensi_karyawan')
                            if tipe_absensi:
                                if tipe_absensi == 'pulang':
                                    try: 
                                        # Ambil jam masuk terakhir karyawan
                                        jam_masuk = record_absensi.objects.filter(
                                            user=record.user,
                                            status='hadir',
                                            tipe_absensi='masuk',
                                            checktime__date=record.checktime.date()
                                        ).latest('checktime')
                                        
                                        # Ambil jam kerja dari Instalasi
                                        instalasi = Instalasi.objects.first()
                                        jam_kerja = instalasi.jam_kerja
                                        
                                        # Hitung selisih waktu
                                        waktu_pulang = datetime.strptime(checktime, '%Y-%m-%dT%H:%M')
                                        selisih_waktu = waktu_pulang - jam_masuk.checktime.replace(tzinfo=None)
                                        
                                        if selisih_waktu < jam_kerja:
                                            messages.error(request, f'Waktu pulang tidak boleh lebih cepat dari {jam_kerja} dari jam masuk.')
                                            return redirect('admin_dashboard_absensi_karyawan')
                                    except record_absensi.DoesNotExist:
                                        messages.error(request, 'Tidak ada data absensi masuk untuk hari ini. Karyawan harus absen masuk terlebih dahulu.')
                                        return redirect('admin_dashboard_absensi_karyawan')
                            
                        record.save()
                        messages.success(request, f'Data absensi karyawan berhasil diperbarui dari {old_status} menjadi {status}.')
                        
                    except ValueError as e:
                        messages.error(request, str(e))
                    except record_absensi.DoesNotExist:
                        messages.error(request, 'Data absensi tidak ditemukan')
                    except (izin.DoesNotExist, sakit.DoesNotExist):
                        messages.error(request, 'Data izin/sakit tidak ditemukan')
                    except Exception as e:
                        messages.error(request, f'Terjadi kesalahan saat mengedit data: {str(e)}')
                    
                    return redirect('admin_dashboard_absensi_karyawan')

            except Exception as e:
                messages.error(request, f'Terjadi kesalahan pada aksi: {str(e)}')
            return redirect('admin_dashboard_absensi_karyawan')

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
        edit_data_absensi_karyawan = []
        edit_id = request.GET.get('id')
        if edit_id:
            for record in record_absensi.objects.filter(id=edit_id).select_related('user'):
                karyawan = record.user.karyawan_set.first()
                record_data = {
                    'id': record.id,
                    'karyawan': karyawan.nama if karyawan else None,
                    'checktime': timezone.localtime(record.checktime).strftime('%Y-%m-%d %H:%M:%S'),
                    'status': record.status,
                    'id_izin': record.id_izin.id if record.id_izin else None,
                    'id_sakit': record.id_sakit.id if record.id_sakit else None,
                    'status_verifikasi': record.status_verifikasi,
                    'tipe_absensi': record.tipe_absensi,
                }
                edit_data_absensi_karyawan.append(record_data)

        context = get_context()
        context.update({
            'karyawan': True,
            
            # Data Series
            'ds_title': 'Statistik Absensi Karyawan',
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
            'pc_title': 'Statistik Absensi Karyawan',
            'pc_month': f"{start_date.strftime('%d %B')} - {end_date.strftime('%d %B %Y')}",
            'pc_data': json.dumps([total_izin, total_sakit, total_hadir]),
            'pc_labels': json.dumps(['Izin', 'Sakit', 'Hadir']),
            
            # Radial Charts
            'rc_title': 'Statistik Absensi Karyawan',
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
            'table_columns': ['ID RECORD', 'NIP', 'Nama Karyawan', 'Jabatan', 'Checktime', 'Status','Tipe Absensi'],
            'table_data': absensi_records.values_list(
                'id',
                'user__karyawan__nip',
                'user__karyawan__nama',
                'user__karyawan__jabatan__nama',
                'checktime',
                'status',
                'tipe_absensi'
            ),
            
            'start_date': start_date.strftime('%m/%d/%Y'),
            'end_date': end_date.strftime('%m/%d/%Y'),
            'selected_jabatan': jabatan_selected,
            
            'total_data_table': absensi_records.count(),
            
            # form tambah record
            'karyawan_list': Karyawan.objects.all(),
            'id_izin': izin.objects.exclude(record_absensi__id_izin__isnull=False),
            'id_sakit': sakit.objects.exclude(record_absensi__id_sakit__isnull=False),
            
            # form edit record
            'edit_data_absensi_karyawan': edit_data_absensi_karyawan,
            
            'status_list': ['hadir', 'izin', 'sakit'],
            
            # Jabatan
            'jabatan_list': jabatan.objects.all(),
            'status_verifikasi_list': ['menunggu', 'diterima', 'ditolak'],
            'tipe_absensi_list': ['masuk', 'pulang'],
        })
        return render(request, 'CustomAdmin/admin_dashboard_absensi_karyawan.html', context)
        
    except Exception as e:
        messages.error(request, f'Terjadi kesalahan pada sistem: {str(e)}')
        return redirect('admin_dashboard')

@cek_instalasi
@superuser_required
def admin_dashboard(request):
    try:
        absensi_records = record_absensi.objects.filter(status_verifikasi='diterima').order_by('-checktime')
        absensi_record_charts = record_absensi.objects.filter(status_verifikasi='diterima', tipe_absensi__in=['masuk', 'sakit', 'izin']).order_by('-checktime')

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
                # Jika parsing gagal, gunakan nilai default
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

        # untuk pie charts dan radial charts

        if request.method == 'POST':
            action = request.POST.get('action')
            if action == 'tambah':
                user_id = request.POST.get('user')
                status = request.POST.get('status')
                checktime = request.POST.get('checktime')
                tipe_absensi = request.POST.get('tipe_absensi')
                
                try:
                    user = CustomUser.objects.get(id=user_id)
                    
                    if status == 'hadir':
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
                        
                        # ... existing code ...
                        if tipe_absensi == 'pulang':
                            try: 
                                # Ambil jam masuk terakhir siswa
                                jam_masuk = record_absensi.objects.filter(
                                    user=user,
                                    status='hadir',
                                    tipe_absensi='masuk',
                                    checktime__date=datetime.strptime(checktime, '%Y-%m-%dT%H:%M').date()
                                ).latest('checktime')
                                
                                # Ambil jam kerja dari Instalasi
                                instalasi = Instalasi.objects.first()
                                jam_kerja = instalasi.jam_kerja
                                
                                # Hitung selisih waktu
                                waktu_pulang = timezone.make_aware(datetime.strptime(checktime, '%Y-%m-%dT%H:%M'))
                                selisih_waktu = waktu_pulang - jam_masuk.checktime.replace(tzinfo=None)
                                
                                if selisih_waktu < jam_kerja:   
                                    messages.error(request, f'Waktu pulang tidak boleh lebih cepat dari {jam_kerja} dari jam masuk.')
                                    return redirect('admin_dashboard')
                            except record_absensi.DoesNotExist:
                                messages.error(request, 'Tidak ada data absensi masuk untuk hari ini. Siswa harus absen masuk terlebih dahulu.')
                                return redirect('admin_dashboard')
                        record = record_absensi.objects.create(
                            user=user,
                            status=status,
                            checktime=checktime,
                            status_verifikasi='diterima',
                            tipe_absensi=tipe_absensi
                        )
                    elif status == 'izin':
                        id_izin = request.POST.get('id_izin')
                        izin_obj = izin.objects.get(id=id_izin)
                        record = record_absensi.objects.create(
                            user=user,
                            status=status,
                            id_izin=izin_obj,
                            checktime=checktime,
                            status_verifikasi='diterima',
                        )
                    elif status == 'sakit':
                        id_sakit = request.POST.get('id_sakit')
                        sakit_obj = sakit.objects.get(id=id_sakit)
                        record = record_absensi.objects.create(
                            user=user,
                            status=status,
                            id_sakit=sakit_obj,
                            checktime=checktime,
                            status_verifikasi='diterima'
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
                    user = absensi.user  # Tambahkan baris ini untuk mendapatkan user dari absensi
                    absensi.checktime = checktime
                    absensi.status = status
                    absensi.status_verifikasi = status_verifikasi
                    absensi.tipe_absensi = tipe_absensi  # Tambahkan baris ini
                    
                    if status == 'izin':
                        id_izin = request.POST.get('id_izin')
                        absensi.id_izin = izin.objects.get(id=id_izin) if id_izin else None
                        absensi.id_sakit = None
                    elif status == 'sakit':
                        id_sakit = request.POST.get('id_sakit')
                        absensi.id_sakit = sakit.objects.get(id=id_sakit) if id_sakit else None
                        absensi.id_izin = None
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
                        
                        if tipe_absensi == 'pulang':
                            try: 
                                # Ambil jam masuk terakhir siswa
                                jam_masuk = record_absensi.objects.filter(
                                    user=user,
                                    status='hadir',
                                    tipe_absensi='masuk',
                                    checktime__date=datetime.strptime(checktime, '%Y-%m-%dT%H:%M').date()
                                ).latest('checktime')
                                
                                # Ambil jam kerja dari Instalasi
                                instalasi = Instalasi.objects.first()
                                jam_kerja = instalasi.jam_kerja
                                
                                # Hitung selisih waktu
                                waktu_pulang = datetime.strptime(checktime, '%Y-%m-%dT%H:%M')
                                selisih_waktu = waktu_pulang - jam_masuk.checktime.replace(tzinfo=None) #ini
                                
                                if selisih_waktu < jam_kerja:#ini
                                    messages.error(request, f'Waktu pulang tidak boleh lebih cepat dari {jam_kerja} jam masuk.')
                                    return redirect('admin_dashboard')
                            except record_absensi.DoesNotExist:
                                messages.error(request, 'Tidak ada data absensi masuk untuk hari ini. Siswa harus absen masuk terlebih dahulu.')
                                return redirect('admin_dashboard')
                    
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
                    'checktime': timezone.localtime(record_edit.checktime).strftime('%Y-%m-%d %H:%M:%S'),
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
            'table_columns': ['id records', 'userid', 'Username', 'Nama', 'Checktime', 'Status', 'Tipe Absensi'],
            'table_data': absensi_records.annotate(
                nama=Coalesce(
                    'user__siswa__nama',
                    'user__guru__nama',
                    'user__karyawan__nama',
                    'user__first_name'
                ),
            ).values_list('id', 'user__userid', 'user__username', 'nama', 'checktime', 'status', 'tipe_absensi'),
            
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


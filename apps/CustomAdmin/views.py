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

from apps.Guru.models import *
from apps.Karyawan.models import *
from apps.main.instalasi import cek_instalasi, get_context
from apps.main.models import *
from apps.main.models import CustomUser, izin, jenjang, kelas
from apps.Siswa.models import *


def is_superuser(user):
    return user.is_authenticated and user.is_superuser

def superuser_required(view_func):
    decorated_view_func = user_passes_test(is_superuser, login_url='login_view')(view_func)
    return decorated_view_func

def get_bulan_now():
    bulan = datetime.now().month
    nama_bulan = {
        1: 'Januari',
        2: 'Februari',
        3: 'Maret',
        4: 'April',
        5: 'Mei',
        6: 'Juni',
        7: 'Juli',
        8: 'Agustus',
        9: 'September',
        10: 'Oktober',
        11: 'November',
        12: 'Desember'
    }
    return nama_bulan.get(bulan, 'Bulan tidak valid')

def get_tanggal_now():
    tanggal = datetime.now().day
    return tanggal

def get_tanggal_from_bulan_request(bulan):
    if bulan == "Januari":
        return ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12', '13', '14', '15', '16', '17', '18', '19', '20', '21', '22', '23', '24', '25', '26', '27', '28', '29', '30', '31']
    elif bulan == "Februari":
        return ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12', '13', '14', '15', '16', '17', '18', '19', '20', '21', '22', '23', '24', '25', '26', '27', '28']
    elif bulan == "Maret":
        return ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12', '13', '14', '15', '16', '17', '18', '19', '20', '21', '22', '23', '24', '25', '26', '27', '28', '29', '30', '31']
    elif bulan == "April":
        return ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12', '13', '14', '15', '16', '17', '18', '19', '20', '21', '22', '23', '24', '25', '26', '27', '28', '29', '30']
    elif bulan == "Mei":
        return ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12', '13', '14', '15', '16', '17', '18', '19', '20', '21', '22', '23', '24', '25', '26', '27', '28', '29', '30', '31']
    elif bulan == "Juni":
        return ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12', '13', '14', '15', '16', '17', '18', '19', '20', '21', '22', '23', '24', '25', '26', '27', '28', '29', '30', '31']
    elif bulan == "Juli":
        return ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12', '13', '14', '15', '16', '17', '18', '19', '20', '21', '22', '23', '24', '25', '26', '27', '28', '29', '30', '31']
    elif bulan == "Agustus":
        return ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12', '13', '14', '15', '16', '17', '18', '19', '20', '21', '22', '23', '24', '25', '26', '27', '28', '29', '30', '31']
    elif bulan == "September":
        return ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12', '13', '14', '15', '16', '17', '18', '19', '20', '21', '22', '23', '24', '25', '26', '27', '28', '29', '30', '31']
    elif bulan == "Oktober":
        return ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12', '13', '14', '15', '16', '17', '18', '19', '20', '21', '22', '23', '24', '25', '26', '27', '28', '29', '30', '31']
    elif bulan == "November":
        return ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12', '13', '14', '15', '16', '17', '18', '19', '20', '21', '22', '23', '24', '25', '26', '27', '28', '29', '30', '31']
    elif bulan == "Desember":
        return ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12', '13', '14', '15', '16', '17', '18', '19', '20', '21', '22', '23', '24', '25', '26', '27', '28', '29', '30', '31']
    else:
        return []
    
def get_bulan_from_date(date):
    bulan = date.strftime('%B')
    return bulan

@cek_instalasi
@superuser_required
def admin_dashboard_absensi_siswa(request): 
    absensi_records = record_absensi.objects.filter(user__siswa__isnull=False, status_verifikasi='diterima').order_by('-checktime')
    absensi_records_charts = record_absensi.objects.filter(user__siswa__isnull=False, status_verifikasi='diterima', tipe_absensi='masuk').order_by('-checktime')

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
        action = request.POST.get('action')
        if action == 'tambah':
            siswa_id = request.POST.get('siswa')
            status = request.POST.get('status')
            checktime = request.POST.get('checktime')
            tipe_absensi = request.POST.get('tipe_absensi')

            try:
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
            except (Siswa.DoesNotExist, izin.DoesNotExist, sakit.DoesNotExist):
                messages.error(request, 'Terjadi kesalahan. Pastikan semua data yang dimasukkan valid.')
            except record_absensi.DoesNotExist:
                messages.error(request, 'Tidak ada data absensi masuk untuk hari ini.')
            
            return redirect('admin_dashboard_absensi_siswa')
        elif action == 'hapus':
            selected_ids = request.POST.get('selectedIds')
            if selected_ids:
                valid_ids = [int(id.strip()) for id in selected_ids.split(',') if id.strip().isdigit()]
                if valid_ids:
                    deleted_count = record_absensi.objects.filter(id__in=valid_ids).delete()[0]
                    messages.success(request, f'{deleted_count} data absensi siswa berhasil dihapus.')
                else:
                    messages.error(request, 'Tidak ada ID valid yang dipilih untuk dihapus.')
            else:
                messages.error(request, 'Tidak ada data yang dipilih untuk dihapus.')
            return redirect('admin_dashboard_absensi_siswa')
        elif action == 'edit':
            absensi_id = request.POST.get('id')
            checktime = request.POST.get('tanggal_waktu')
            status = request.POST.get('status')
            status_verifikasi_checkbox = request.POST.get('status_verifikasi')
            try:
                record = record_absensi.objects.get(id=absensi_id)
                old_status = record.status
                record.checktime = checktime
                record.status = status
                record.status_verifikasi = status_verifikasi_checkbox
                
                
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
            except (record_absensi.DoesNotExist, izin.DoesNotExist, sakit.DoesNotExist):
                messages.error(request, 'Terjadi kesalahan. Pastikan semua data yang dimasukkan valid.')
            
            return redirect('admin_dashboard_absensi_siswa')

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

@cek_instalasi
@superuser_required
def admin_dashboard_absensi_guru(request):
    absensi_records = record_absensi.objects.filter(user__guru__isnull=False, status_verifikasi='diterima').order_by('-checktime')
    absensi_records_charts = record_absensi.objects.filter(user__guru__isnull=False, status_verifikasi='diterima', tipe_absensi='masuk').order_by('-checktime')

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
        action = request.POST.get('action')
        if action == 'tambah':
            guru_id = request.POST.get('guru')
            status = request.POST.get('status')
            checktime = request.POST.get('checktime')
            tipe_absensi = request.POST.get('tipe_absensi')

            try:
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
                
                messages.success(request, 'Data absensi guru berhasil ditambahkan.')
            except (Guru.DoesNotExist, izin.DoesNotExist, sakit.DoesNotExist):
                messages.error(request, 'Terjadi kesalahan. Pastikan semua data yang dimasukkan valid.')
            
            return redirect('admin_dashboard_absensi_guru')
        elif action == 'hapus':
            selected_ids = request.POST.get('selectedIds')
            if selected_ids:
                valid_ids = [int(id.strip()) for id in selected_ids.split(',') if id.strip().isdigit()]
                if valid_ids:
                    deleted_count = record_absensi.objects.filter(id__in=valid_ids).delete()[0]
                    messages.success(request, f'{deleted_count} data absensi guru berhasil dihapus.')
                else:
                    messages.error(request, 'Tidak ada ID valid yang dipilih untuk dihapus.')
            else:
                messages.error(request, 'Tidak ada data yang dipilih untuk dihapus.')
            return redirect('admin_dashboard_absensi_guru')
        elif action == 'edit':
            absensi_id = request.POST.get('id')
            checktime = request.POST.get('tanggal_waktu')
            status = request.POST.get('status')
            status_verifikasi_checkbox = request.POST.get('status_verifikasi')
            tipe_absensi = request.POST.get('tipe_absensi')
            try:
                record = record_absensi.objects.get(id=absensi_id)
                record.checktime = checktime
                record.status = status
                record.status_verifikasi = status_verifikasi_checkbox
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
                    
                record.save()
                messages.success(request, 'Data absensi guru berhasil diperbarui.')
            except (record_absensi.DoesNotExist, izin.DoesNotExist, sakit.DoesNotExist):
                messages.error(request, 'Terjadi kesalahan. Pastikan semua data yang dimasukkan valid.')
            
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

@cek_instalasi
@superuser_required
def admin_dashboard_absensi_karyawan(request):
    absensi_records = record_absensi.objects.filter(user__karyawan__isnull=False, status_verifikasi='diterima').order_by('-checktime')
    absensi_records_charts = record_absensi.objects.filter(user__karyawan__isnull=False, status_verifikasi='diterima', tipe_absensi='masuk').order_by('-checktime')
    
    # untuk filter data
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
        action = request.POST.get('action')
        if action == 'tambah':
            karyawan_id = request.POST.get('karyawan')
            status = request.POST.get('status')
            checktime = request.POST.get('checktime')
            tipe_absensi = request.POST.get('tipe_absensi')

            try:
                karyawan = Karyawan.objects.get(id=karyawan_id)
                user = karyawan.user
                
                if status == 'hadir':
                    
                    # Cek apakah sudah ada absensi dengan tipe yang sama untuk hari ini
                    existing_record = record_absensi.objects.filter(
                        user=user,
                        status='hadir',
                        tipe_absensi=tipe_absensi,
                        checktime__date=record.checktime.date()
                    ).exists()
                    
                    if existing_record:
                        messages.error(request, f'Sudah ada data absensi {tipe_absensi} untuk hari ini.')
                        return redirect('admin_dashboard_absensi_karyawan')
                    
                    if tipe_absensi == 'pulang':
                        try: 
                            # Ambil jam masuk terakhir guru
                            jam_masuk = record_absensi.objects.filter(
                                user=record.user,
                                status='hadir',
                                tipe_absensi='masuk',
                                checktime__date=record.checktime.date()
                            )
                            
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
                            messages.error(request, 'Tidak ada data absensi masuk untuk hari ini. Guru harus absen masuk terlebih dahulu.')
                    
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
            except (Karyawan.DoesNotExist, izin.DoesNotExist, sakit.DoesNotExist):
                messages.error(request, 'Terjadi kesalahan. Pastikan semua data yang dimasukkan valid.')
            
            return redirect('admin_dashboard_absensi_karyawan')
        elif action == 'hapus':
            selected_ids = request.POST.get('selectedIds')
            if selected_ids:
                valid_ids = [int(id.strip()) for id in selected_ids.split(',') if id.strip().isdigit()]
                if valid_ids:
                    deleted_count = record_absensi.objects.filter(id__in=valid_ids).delete()[0]
                    messages.success(request, f'{deleted_count} data absensi karyawan berhasil dihapus.')
                else:
                    messages.error(request, 'Tidak ada ID valid yang dipilih untuk dihapus.')
            else:
                messages.error(request, 'Tidak ada data yang dipilih untuk dihapus.')
            return redirect('admin_dashboard_absensi_karyawan')
        elif action == 'edit':
            absensi_id = request.POST.get('id')
            checktime = request.POST.get('tanggal_waktu')
            status = request.POST.get('status')
            status_verifikasi = request.POST.get('status_verifikasi')
            tipe_absensi = request.POST.get('tipe_absensi')
            try:
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
                        user=user,
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
                                # Ambil jam masuk terakhir guru
                                jam_masuk = record_absensi.objects.filter(
                                    user=record.user,
                                    status='hadir',
                                    tipe_absensi='masuk',
                                    checktime__date=record.checktime.date()
                                )
                                
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
                                messages.error(request, 'Tidak ada data absensi masuk untuk hari ini. Guru harus absen masuk terlebih dahulu.')
                        
                record.save()
                messages.success(request, f'Data absensi karyawan berhasil diperbarui dari {old_status} menjadi {status}.')
            except (record_absensi.DoesNotExist, izin.DoesNotExist, sakit.DoesNotExist):
                messages.error(request, 'Terjadi kesalahan. Pastikan semua data yang dimasukkan valid.')
            
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

@cek_instalasi
@superuser_required
def admin_dashboard(request):
    absensi_records = record_absensi.objects.filter(status_verifikasi='diterima').order_by('-checktime')
    absensi_record_charts = record_absensi.objects.filter(status_verifikasi='diterima', tipe_absensi='masuk').order_by('-checktime')

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
            # except Exception as e:
            #     messages.error(request, f'Terjadi kesalahan: {str(e)}')
            
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

@cek_instalasi
@superuser_required
def admin_siswa(request):
    today = timezone.localtime(timezone.now()).date()
    jenjang_filter = request.GET.get('jenjang')
    kelas_filter = request.GET.get('kelas')

    edit_data_siswa = []
    edit_id = request.GET.get('id')
    if edit_id:
        for data_siswa in Siswa.objects.filter(id=edit_id):
            data_edit = {
                'id': data_siswa.id,
                'iduser': data_siswa.user.id if data_siswa.user else None,
                'username': data_siswa.user.username if data_siswa.user else None,
                'email': data_siswa.user.email if data_siswa.user else None,
                'nama': data_siswa.nama,
                'nisn': data_siswa.nisn,
                'tanggal_lahir': data_siswa.tanggal_lahir.strftime('%Y-%m-%d'),
                'jenjang': data_siswa.jenjang.nama if data_siswa.jenjang else None,
                'kelas': data_siswa.kelas.nama if data_siswa.kelas else None,
                'alamat': data_siswa.alamat if data_siswa else None,
                'chatid': data_siswa.telegram_chat_id if data_siswa else None,
                'userid': data_siswa.user.userid if data_siswa.user else None
            }
            edit_data_siswa.append(data_edit)
            
    # Filter siswa berdasarkan jenjang dan kelas
    siswa_filter = Siswa.objects.all()
    if jenjang_filter:
        siswa_filter = siswa_filter.filter(jenjang__nama=jenjang_filter)
    if kelas_filter:
        siswa_filter = siswa_filter.filter(kelas__nama=kelas_filter)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'tambah':
            try:
                username = request.POST.get('username')
                email = request.POST.get('email')
                password = request.POST.get('password')
                userid = request.POST.get('userid')
                
                # Buat user baru
                user = CustomUser.objects.create_user(username=username, email=email, password=password, userid=userid, is_staff=True)
                
                # Ambil data siswa
                nama = request.POST.get('nama')
                nisn = request.POST.get('nisn')
                tgl_lahir = request.POST.get('tanggal_lahir')
                jenjang_siswa = request.POST.get('jenjang')
                kelas_siswa = request.POST.get('kelas')
                alamat = request.POST.get('alamat')
                telegram_chat_id = request.POST.get('chatid')
                
                
                # Buat siswa baru dengan user yang telah dibuat
                siswa = Siswa.objects.create(
                    user=user,
                    nisn=nisn,
                    nama=nama,
                    tanggal_lahir=tgl_lahir,
                    jenjang_id=jenjang_siswa,
                    kelas_id=kelas_siswa,
                    alamat=alamat,
                    telegram_chat_id=telegram_chat_id,
                )
                messages.success(request, 'Data siswa berhasil ditambahkan.')
            except Exception as e:
                messages.error(request, f'Terjadi kesalahan: {str(e)}')
                return redirect('admin_siswa')
        elif action == 'edit':
            id_siswa = request.POST.get('id')
            id_user = request.POST.get('iduser')
            userid = request.POST.get('userid')
            username = request.POST.get('username')
            nama = request.POST.get('nama')
            email = request.POST.get('email')
            nisn = request.POST.get('nisn')
            tanggal_lahir = request.POST.get('tanggal_lahir')
            jenjang_selected = request.POST.get('jenjang')
            kelas_selected = request.POST.get('kelas')
            alamat = request.POST.get('alamat')
            chatid = request.POST.get('chatid')
            password = request.POST.get('new_password')

            # Update user details
            user = CustomUser.objects.get(id=id_user)
            user.username = username
            user.email = email
            user.userid = userid
            if password not in (None, ''):
                user.set_password(password)
            user.save()
            
            if jenjang_selected not in ('None', '', 'Pilih Jenjang', None, 0, '0'):
                siswa.jenjang = jenjang.objects.get(nama=jenjang_selected)
            else:
                pass
            
            if kelas_selected not in ('None', '', 'Pilih Kelas', None, 0, '0'):
                siswa.kelas = kelas.objects.get(nama=kelas_selected)
            else:
                pass
            
            # Update siswa details
            siswa = Siswa.objects.get(id=id_siswa)
            siswa.nisn = nisn
            siswa.nama = nama
            siswa.tanggal_lahir = tanggal_lahir
            siswa.alamat = alamat
            siswa.telegram_chat_id = chatid
            siswa.save()
            
            messages.success(request, 'Data siswa berhasil diperbarui.')
            return redirect('admin_siswa')
        elif action == 'hapus':
            selected_ids = request.POST.getlist('selectedIds')
            # Menangani kasus di mana selectedIds berisi string dengan beberapa ID
            all_ids = []
            for id_string in selected_ids:
                all_ids.extend(id_string.split(','))
            
            siswa_list = Siswa.objects.filter(id__in=all_ids)
            for siswa in siswa_list:
                user = siswa.user
                # Menghapus semua record_absensi terkait
                record_absensi.objects.filter(user=user).delete()
                # Menghapus semua izin terkait
                izin.objects.filter(user=user).delete()
                # Menghapus semua sakit terkait
                sakit.objects.filter(user=user).delete()
                # Menghapus Siswa
                siswa.delete()
                # Menghapus user
                user.delete()

            messages.success(request, f'{len(all_ids)} data siswa berhasil dihapus.')
            return redirect('admin_siswa')

        elif action == 'import':
            file_type = request.POST.get('file_type')
            file = request.FILES.get('file_input')
            
            if file_type == 'csv':
                df = pd.read_csv(file)
            elif file_type == 'excel':
                df = pd.read_excel(file)
            else:
                messages.error(request, 'Tipe file tidak didukung.')
                return redirect('admin_siswa')
            
            success_count = 0
            error_count = 0
            
            for _, row in df.iterrows():
                try:
                    # Cek apakah username sudah ada
                    username = row['username']
                    counter = 1
                    while CustomUser.objects.filter(username=username).exists():
                        username = f"{row['username']}_{counter}"
                        counter += 1
                    
                    user = CustomUser.objects.create_user(
                        username=username,
                        email=row['email'],
                        password=row['password'],
                        userid=row['userid'],
                        is_staff=True
                    )
                    
                    # Cek dan buat jenjang jika belum ada
                    jenjang_obj, _ = jenjang.objects.get_or_create(nama=row['jenjang'])
                    
                    # Cek dan buat kelas jika belum ada
                    kelas_obj, _ = kelas.objects.get_or_create(nama=row['kelas'])
                    
                    Siswa.objects.create(
                        user=user,
                        nisn=row['nisn'],
                        nama=row['nama'],
                        tanggal_lahir=row['tanggal_lahir'],
                        jenjang=jenjang_obj,
                        kelas=kelas_obj,
                        alamat=row['alamat'],
                        telegram_chat_id=row['telegram_chat_id']
                    )
                    success_count += 1
                except Exception as e:
                    error_count += 1
                    print(f'Gagal mengimpor data: {str(e)}')
            
            if success_count > 0:
                messages.success(request, f'{success_count} data siswa berhasil diimpor.')
            if error_count > 0:
                messages.warning(request, f'{error_count} data siswa gagal diimpor. Silakan periksa log untuk detailnya.')
            
            return redirect('admin_siswa')


    
    # Subquery untuk mendapatkan status record_absensi terbaru untuk setiap siswa hari ini
    latest_absensi = record_absensi.objects.filter(
        user__siswa=OuterRef('pk'),
        checktime__date=today
    ).order_by('-checktime').values('status', 'status_verifikasi')[:1]

    # Query utama
    students = siswa_filter.select_related('user', 'jenjang', 'kelas').annotate(
        today_status=Subquery(latest_absensi.values('status')),
        today_status_verifikasi=Subquery(latest_absensi.values('status_verifikasi')),
        today_checktime=Subquery(latest_absensi.values('checktime')),
        today_tipe_absensi=Subquery(latest_absensi.values('tipe_absensi'))
    ).values_list(
        'id',
        'user__userid',
        'nama',
        'jenjang__nama',
        'kelas__nama',
        'alamat',
        'user__username',
        'today_status',
        'today_status_verifikasi',
        'today_checktime',
        'today_tipe_absensi'
    )

    # Memproses queryset untuk menampilkan status yang lebih detail
    table_data = []
    for student in students:
        status = student[-4]  # today_status
        status_verifikasi = student[-3]  # today_status_verifikasi
        checktime = timezone.localtime(student[-2])  # today_checktime
        tipe_absensi = student[-1]  # today_tipe_absensi
        print(status, status_verifikasi, checktime, tipe_absensi)
        
        if status_verifikasi == 'menunggu':
            display_status = "Belum Diverifikasi"
        elif status_verifikasi == 'ditolak':
            display_status = "Ditolak"
        elif tipe_absensi == 'pulang':
            display_status = "Sudah Pulang"
        elif status == 'hadir' and tipe_absensi == 'masuk':
            instalasi = Instalasi.objects.first()
            jam_masuk = instalasi.jam_masuk if instalasi.jam_masuk else None
            jam_pulang = instalasi.jam_pulang if instalasi.jam_pulang else None
            if checktime and jam_masuk:
                selisih = datetime.combine(date.min, datetime.strptime(checktime.strftime('%I:%M %p'), '%I:%M %p').time()) - datetime.combine(date.min, jam_masuk)
                if selisih.total_seconds() > 0:
                    menit_terlambat = selisih.total_seconds() // 60
                    if menit_terlambat < 60:
                        display_status = f"Hadir, terlambat {int(menit_terlambat)} menit"
                    else:
                        jam_terlambat = int(menit_terlambat // 60)
                        sisa_menit = int(menit_terlambat % 60)
                        display_status = f"Hadir, terlambat {jam_terlambat} jam {sisa_menit} menit"
                else:
                    display_status = "Hadir"
            else:
                display_status = "Hadir"
        else:
            display_status = status if status else "Belum Hadir"
        
        table_data.append(list(student[:-4]) + [display_status])
    
    context = get_context()
    context.update({
        'siswa': True,
        
        'table_columns': ['ID Siswa', 'UserID', 'Nama', 'Jenjang', 'Kelas', 'Alamat', 'Username', 'Status'],
        'table_data': table_data,
        
        'jenjang_list': jenjang.objects.all(),
        'kelas_list': kelas.objects.all(),
        
        'edit_data_siswa': edit_data_siswa,
        
        'total_data_table': siswa_filter.count(),
    })
    return render(request, 'CustomAdmin/admin_siswa.html', context)

@cek_instalasi
@superuser_required
def admin_guru(request):
    today = timezone.localtime(timezone.now()).date()
    jenjang_filter = request.GET.get('jenjang')
    kelas_filter = request.GET.get('kelas')
    mata_pelajaran_filter = request.GET.get('mata_pelajaran')
    
    edit_data_guru = []
    edit_id = request.GET.get('id')
    if edit_id:
        for data_guru in Guru.objects.filter(id=edit_id):
            data_edit = {
                'idguru': data_guru.id,
                'iduser': data_guru.user.id if data_guru.user else None,
                'username': data_guru.user.username if data_guru.user else None,
                'email': data_guru.user.email if data_guru.user else None,
                'nama': data_guru.nama,
                'nuptk': data_guru.nuptk,
                'tanggal_lahir': data_guru.tanggal_lahir,
                'jenjang': data_guru.jenjang.nama if data_guru.jenjang else None,
                'kelas': data_guru.kelas.nama if data_guru.kelas else None,
                'mata_pelajaran': data_guru.mata_pelajaran if data_guru else None,
                'alamat': data_guru.alamat if data_guru else None,
                'userid': data_guru.user.userid if data_guru.user else None,
            }
            edit_data_guru.append(data_edit)
            
    guru_filter = Guru.objects.all()
    if jenjang_filter:
        guru_filter = guru_filter.filter(jenjang__nama=jenjang_filter)
    if kelas_filter:
        guru_filter = guru_filter.filter(kelas__nama=kelas_filter)
    if mata_pelajaran_filter:
        guru_filter = guru_filter.filter(mata_pelajaran__nama=mata_pelajaran_filter)
        
    if request.method == 'POST':
        action =  request.POST.get('action')
        if action == 'tambah':
            username = request.POST.get('username')
            email = request.POST.get('email')
            password = request.POST.get('password')
            userid = request.POST.get('userid')
            
            user = CustomUser.objects.create_user(username=username, email=email, password=password, userid=userid, is_staff=True)
            
            nama = request.POST.get('nama')
            nuptk = request.POST.get('nuptk')
            tanggal_lahir = request.POST.get('tanggal_lahir')
            jenjang_selected = request.POST.get('jenjang')
            kelas_selected = request.POST.get('kelas')
            mata_pelajaran_selected = request.POST.get('mata_pelajaran')
            alamat = request.POST.get('alamat')
            
            guru = Guru.objects.create(
                user=user,
                nama=nama,
                nuptk=nuptk,
                tanggal_lahir=tanggal_lahir,
                jenjang_id=jenjang_selected,
                kelas_id=kelas_selected,
                mata_pelajaran_id=mata_pelajaran_selected,
                alamat=alamat,
            )
            messages.success(request, f'Data guru {nama} berhasil ditambahkan.')
            
        if action == 'edit':
            id_guru = request.POST.get('id')
            id_user = request.POST.get('iduser')
            userid = request.POST.get('userid')
            username = request.POST.get('username')
            nama = request.POST.get('nama')
            email = request.POST.get('email')
            nuptk = request.POST.get('nuptk')
            tanggal_lahir = request.POST.get('tanggal_lahir')
            jenjang_selected = request.POST.get('jenjang')
            kelas_selected = request.POST.get('kelas')
            mata_pelajaran_selected = request.POST.get('mapel')
            alamat = request.POST.get('alamat')
            password = request.POST.get('new_password')
            
            user = CustomUser.objects.get(id=id_user)
            user.username = username
            user.email = email
            user.userid = userid
            if password not in (None, ''):
                user.set_password(password)
            user.save()
            
            guru = Guru.objects.get(id=id_guru)
            
            
            if mata_pelajaran_selected not in ('None', '', 'Pilih Mata Pelajaran', None, 0, '0'):
                guru.mata_pelajaran = mata_pelajaran.objects.get(nama=mata_pelajaran_selected)
            else:
                pass
            if kelas_selected not in ('None', '', 'Pilih Kelas', None, 0, '0'):
                guru.kelas = kelas.objects.get(nama=kelas_selected)
            else:
                pass
            if jenjang_selected not in ('None', '', 'Pilih Jenjang', None, 0, '0'):
                guru.jenjang = jenjang.objects.get(nama=jenjang_selected)
            else:
                pass
            
            guru.nama = nama
            guru.nuptk = nuptk
            guru.tanggal_lahir = tanggal_lahir
            
            guru.alamat = alamat
            guru.save()
            
            messages.success(request, f'Data guru {nama} berhasil diperbarui.')
            return redirect('admin_guru')
        
        if action == 'hapus':
            selected_ids = request.POST.getlist('selectedIds')
            # Menangani kasus di mana selectedIds berisi string dengan beberapa ID
            all_ids = []
            for id_string in selected_ids:
                all_ids.extend(id_string.split(','))
            
            guru_list = Guru.objects.filter(id__in=all_ids)
            deleted_count = 0
            for guru in guru_list:
                user = guru.user
                # Menghapus semua record_absensi terkait
                record_absensi.objects.filter(user=user).delete()
                # menghapus semua izin terkait
                izin.objects.filter(user=user).delete()
                # menghapus semua sakit terkait
                sakit.objects.filter(user=user).delete()
                # menghapus guru
                guru.delete()
                # menghapus user
                user.delete()
                deleted_count += 1
                
            messages.success(request, f'{deleted_count} data guru berhasil dihapus.')
            return redirect('admin_guru')
        
        if action == 'import':
            file_type = request.POST.get('file_type')
            file = request.FILES.get('file_input')
            
            if file_type == 'csv':
                df = pd.read_csv(file)
            elif file_type == 'excel':
                df = pd.read_excel(file)
            else:
                messages.error(request, 'Tipe file tidak didukung.')
                return redirect('admin_guru')
            
            success_count = 0
            error_count = 0
            
            for _, row in df.iterrows():
                try:
                    # Cek apakah username sudah ada
                    username = row['username']
                    counter = 1
                    while CustomUser.objects.filter(username=username).exists():
                        username = f"{row['username']}_{counter}"
                        counter += 1
                    
                    user = CustomUser.objects.create_user(
                        username=username,
                        email=row['email'],
                        password=row['password'],
                        userid=row['userid'],
                        is_staff=True
                    )
                    
                    jenjang_obj, _ = jenjang.objects.get_or_create(nama=row['jenjang'])
                    kelas_obj, _ = kelas.objects.get_or_create(nama=row['kelas'])
                    mata_pelajaran_obj, _ = mata_pelajaran.objects.get_or_create(nama=row['mata_pelajaran'])
                    
                    Guru.objects.create(
                        user=user,
                        nuptk=row['nuptk'],
                        nama=row['nama'],
                        tanggal_lahir=row['tanggal_lahir'],
                        jenjang=jenjang_obj,
                        kelas=kelas_obj,
                        mata_pelajaran=mata_pelajaran_obj,
                        alamat=row['alamat']
                    )
                    success_count += 1
                except Exception as e:
                    error_count += 1
                    print(f'Gagal mengimpor data: {str(e)}')
            
            if success_count > 0:
                messages.success(request, f'{success_count} data guru berhasil diimpor.')
            if error_count > 0:
                messages.warning(request, f'{error_count} data guru gagal diimpor. Silakan periksa log untuk detailnya.')
            
            return redirect('admin_guru')
            
    # Subquery untuk mendapatkan status record_absensi terbaru untuk setiap guru hari ini
    latest_absensi = record_absensi.objects.filter(
        user__guru=OuterRef('pk'),
        checktime__date=today
    ).order_by('-checktime').values('status', 'status_verifikasi')[:1]

    # Query utama
    guru = guru_filter.select_related('user', 'jenjang', 'kelas', 'mata_pelajaran').annotate(
        today_status=Subquery(latest_absensi.values('status')),
        today_status_verifikasi=Subquery(latest_absensi.values('status_verifikasi')),
        today_checktime=Subquery(latest_absensi.values('checktime')),
        today_tipe_absensi=Subquery(latest_absensi.values('tipe_absensi'))
    ).values_list(
        'id',
        'user__userid',
        'nama',
        'jenjang__nama',
        'kelas__nama',
        'mata_pelajaran__nama',
        'alamat',
        'user__username',
        'today_status',
        'today_status_verifikasi',
        'today_checktime',
        'today_tipe_absensi'
    )

    # Memproses queryset untuk menampilkan status yang lebih detail
    table_data = []
    for guru_data in guru:
        status = guru_data[-4]  # today_status
        status_verifikasi = guru_data[-3]  # today_status_verifikasi
        checktime = timezone.localtime(guru_data[-2])  # today_checktime
        tipe_absensi = guru_data[-1]  # today_tipe_absensi
        print(status, status_verifikasi, checktime, tipe_absensi)
        
        if status_verifikasi == 'menunggu':
            display_status = "Belum Diverifikasi"
        elif status_verifikasi == 'ditolak':
            display_status = "Ditolak"
        elif tipe_absensi == 'pulang':
            display_status = "Sudah Pulang"
        elif status == 'hadir' and tipe_absensi == 'masuk':
            instalasi = Instalasi.objects.first()
            jam_masuk = instalasi.jam_masuk if instalasi.jam_masuk else None
            jam_pulang = instalasi.jam_pulang if instalasi.jam_pulang else None
            if checktime and jam_masuk:
                selisih = datetime.combine(date.min, datetime.strptime(checktime.strftime('%I:%M %p'), '%I:%M %p').time()) - datetime.combine(date.min, jam_masuk)
                if selisih.total_seconds() > 0:
                    menit_terlambat = selisih.total_seconds() // 60
                    if menit_terlambat < 60:
                        display_status = f"Hadir, terlambat {int(menit_terlambat)} menit"
                    else:
                        jam_terlambat = int(menit_terlambat // 60)
                        sisa_menit = int(menit_terlambat % 60)
                        display_status = f"Hadir, terlambat {jam_terlambat} jam {sisa_menit} menit"
                else:
                    display_status = "Hadir"
            else:
                display_status = "Hadir"
        else:
            display_status = status if status else "Belum Hadir"
        
        table_data.append(list(guru_data[:-4]) + [display_status])
        
    context = get_context()
    context.update({
        'table_columns': ['ID Guru', 'UserID', 'Nama', 'Jenjang', 'Kelas', 'Mata Pelajaran', 'Alamat', 'Username', 'Status'],
        'table_data': table_data,
        
        'jenjang_list': jenjang.objects.all(),
        'kelas_list': kelas.objects.all(),
        'mata_pelajaran_list': mata_pelajaran.objects.all(),
        
        'edit_data_guru': edit_data_guru,
        
        'guru': True,
        
        'total_data_table': guru_filter.count(),
    })
    return render(request, 'CustomAdmin/admin_guru.html', context)

@cek_instalasi
@superuser_required
def admin_karyawan(request):
    today = timezone.localtime(timezone.now()).date()
    jabatan_filter = request.GET.get('jabatan')
    
    edit_data_karyawan = []
    edit_id = request.GET.get('id')
    if edit_id:
        for data_karyawan in Karyawan.objects.filter(id=edit_id):
            data_edit = {
                'id': data_karyawan.id,
                'iduser': data_karyawan.user.id if data_karyawan.user else None,
                'username': data_karyawan.user.username if data_karyawan.user else None,
                'email': data_karyawan.user.email if data_karyawan.user else None,
                'nama': data_karyawan.nama,
                'nip': data_karyawan.nip,
                'tanggal_lahir': data_karyawan.tanggal_lahir.strftime('%Y-%m-%d'),
                'jabatan': data_karyawan.jabatan.nama if data_karyawan.jabatan else None,
                'alamat': data_karyawan.alamat if data_karyawan else None,
                'userid': data_karyawan.user.userid if data_karyawan.user else None,
            }
            edit_data_karyawan.append(data_edit)
            
            
    karyawan_filter = Karyawan.objects.all()
    if jabatan_filter:
        karyawan_filter = karyawan_filter.filter(jabatan__nama=jabatan_filter)
        
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'tambah':
            username = request.POST.get('username')
            email = request.POST.get('email')
            password = request.POST.get('password')
            userid = request.POST.get('userid')
            
            user = CustomUser.objects.create_user(username=username, email=email, password=password, userid=userid, is_staff=True)
            
            nama = request.POST.get('nama')
            nip = request.POST.get('nip')
            tanggal_lahir = request.POST.get('tanggal_lahir')
            jabatan_karyawan = request.POST.get('jabatan')
            alamat = request.POST.get('alamat')
            
            karyawan = Karyawan.objects.create(
                user=user,
                nama=nama,
                nip=nip,
                tanggal_lahir=tanggal_lahir,
                jabatan_id=jabatan_karyawan,
                alamat=alamat,
            )
            messages.success(request, 'Data karyawan berhasil ditambahkan.')
            
        if action == 'edit':
            id_karyawan = request.POST.get('id')
            id_user = request.POST.get('iduser')
            userid = request.POST.get('userid')
            username = request.POST.get('username')
            nama = request.POST.get('nama')
            email = request.POST.get('email')
            nip = request.POST.get('nip')
            tanggal_lahir = request.POST.get('tanggal_lahir')
            jabatan_selected = request.POST.get('jabatan')
            alamat = request.POST.get('alamat')
            password = request.POST.get('new_password')
            
            user = CustomUser.objects.get(id=id_user)
            user.username = username
            user.email = email
            user.userid = userid
            if password not in (None, ''):
                user.set_password(password)
            user.save()
            
            karyawan = Karyawan.objects.get(id=id_karyawan)
            karyawan.nama = nama
            karyawan.nip = nip
            karyawan.tanggal_lahir = tanggal_lahir
            if jabatan_selected not in ('None', '', 'Pilih Jabatan', None, 0, '0'):
                jabatan_karyawan = jabatan.objects.get(nama=jabatan_selected)
                karyawan.jabatan = jabatan_karyawan
            else:
                pass
            karyawan.alamat = alamat
            karyawan.save()
            
            messages.success(request, 'Data karyawan berhasil diperbarui.')
            return redirect('admin_karyawan')
        
        if action == 'hapus':
            selected_ids = request.POST.getlist('selectedIds')
            # Menangani kasus di mana selectedIds berisi string dengan beberapa ID
            all_ids = []
            for id_string in selected_ids:
                all_ids.extend(id_string.split(','))
            
            karyawan_list = Karyawan.objects.filter(id__in=all_ids)
            deleted_count = 0
            for karyawan in karyawan_list:
                user = karyawan.user
                # menghapus semua record_absensi terkait
                record_absensi.objects.filter(user=user).delete()
                # menghapus semua izin terkait
                izin.objects.filter(user=user).delete()
                # menghapus semua sakit terkait
                sakit.objects.filter(user=user).delete()
                # menghapus karyawan
                karyawan.delete()
                # menghapus user
                user.delete()
                deleted_count += 1
            
            messages.success(request, f'{deleted_count} data karyawan berhasil dihapus.')
            return redirect('admin_karyawan')
        
        if action == 'import':
            file_type = request.POST.get('file_type')
            file = request.FILES.get('file_input')
            
            if file_type == 'csv':
                df = pd.read_csv(file)
            elif file_type == 'excel':
                df = pd.read_excel(file)
            else:
                messages.error(request, 'Tipe file tidak didukung.')
                return redirect('admin_karyawan')
            
            success_count = 0
            error_count = 0
            
            for _, row in df.iterrows():
                try:
                    # Cek apakah username sudah ada
                    username = row['username']
                    counter = 1
                    while CustomUser.objects.filter(username=username).exists():
                        username = f"{row['username']}_{counter}"
                        counter += 1
                    
                    user = CustomUser.objects.create_user(
                        username=username,
                        email=row['email'],
                        password=row['password'],
                        userid=row['userid'],
                        is_staff=True
                    )
                    
                    jabatan_obj, created = jabatan.objects.get_or_create(nama=row['jabatan'])
                    
                    Karyawan.objects.create(
                        user=user,
                        nip=row['nip'],
                        nama=row['nama'],
                        tanggal_lahir=row['tanggal_lahir'],
                        jabatan=jabatan_obj,
                        alamat=row['alamat']
                    )
                    success_count += 1
                except Exception as e:
                    error_count += 1
                    print(f'Gagal mengimpor data: {str(e)}')
            
            if success_count > 0:
                messages.success(request, f'{success_count} data karyawan berhasil diimpor.')
            if error_count > 0:
                messages.warning(request, f'{error_count} data karyawan gagal diimpor. Silakan periksa log untuk detailnya.')
            
            return redirect('admin_karyawan')
        
    
    # Subquery untuk mendapatkan status record_absensi terbaru untuk setiap karyawan hari ini
    latest_absensi = record_absensi.objects.filter(
        user__karyawan=OuterRef('pk'),
        checktime__date=today
    ).order_by('-checktime').values('status', 'status_verifikasi')[:1]

    # Query utama
    karyawan = karyawan_filter.select_related('user', 'jabatan').annotate(
        today_status=Subquery(latest_absensi.values('status')),
        today_status_verifikasi=Subquery(latest_absensi.values('status_verifikasi')),
        today_checktime=Subquery(latest_absensi.values('checktime')),
        today_tipe_absensi=Subquery(latest_absensi.values('tipe_absensi'))
    ).values_list(
        'id',
        'user__userid',
        'nama',
        'jabatan__nama',
        'alamat',
        'user__username',
        'today_status',
        'today_status_verifikasi',
        'today_checktime',
        'today_tipe_absensi'
    )

    # Memproses queryset untuk menampilkan status yang lebih detail
    table_data = []
    for karyawan_data in karyawan:
        status = karyawan_data[-4]  # today_status
        status_verifikasi = karyawan_data[-3]  # today_status_verifikasi
        checktime = timezone.localtime(karyawan_data[-2])  # today_checktime
        tipe_absensi = karyawan_data[-1]  # today_tipe_absensi
        print(status, status_verifikasi, checktime, tipe_absensi)
        
        if status_verifikasi == 'menunggu':
            display_status = "Belum Diverifikasi"
        elif status_verifikasi == 'ditolak':
            display_status = "Ditolak"
        elif tipe_absensi == 'pulang':
            display_status = "Sudah Pulang"
        elif status == 'hadir' and tipe_absensi == 'masuk':
            instalasi = Instalasi.objects.first()
            jam_masuk = instalasi.jam_masuk if instalasi.jam_masuk else None
            jam_pulang = instalasi.jam_pulang if instalasi.jam_pulang else None
            if checktime and jam_masuk:
                selisih = datetime.combine(date.min, datetime.strptime(checktime.strftime('%I:%M %p'), '%I:%M %p').time()) - datetime.combine(date.min, jam_masuk)
                if selisih.total_seconds() > 0:
                    menit_terlambat = selisih.total_seconds() // 60
                    if menit_terlambat < 60:
                        display_status = f"Hadir, terlambat {int(menit_terlambat)} menit"
                    else:
                        jam_terlambat = int(menit_terlambat // 60)
                        sisa_menit = int(menit_terlambat % 60)
                        display_status = f"Hadir, terlambat {jam_terlambat} jam {sisa_menit} menit"
                else:
                    display_status = "Hadir"
            else:
                display_status = "Hadir"
        else:
            display_status = status if status else "Belum Hadir"
        
        table_data.append(list(karyawan_data[:-4]) + [display_status])
    context = get_context()
    context.update({
        'table_columns': ['ID Karyawan', 'UserID', 'Nama', 'Jabatan', 'Alamat', 'Username', 'Status'],
        'table_data': table_data,
        
        'jabatan_list': jabatan.objects.all(),
        
        'edit_data_karyawan': edit_data_karyawan,
        
        'karyawan': True,
        
        'total_data_table': karyawan_filter.count(),
    })
    return render(request, 'CustomAdmin/admin_karyawan.html', context)

@cek_instalasi
@superuser_required
def admin_atribut(request):
    context = get_context()
    context.update({
        
    })
    return render(request, 'CustomAdmin/admin_atribut.html', context)

@cek_instalasi
@superuser_required
def admin_atribut_kelas(request):
    edit_data_atribut_kelas = []
    edit_id = request.GET.get('id')
    if edit_id:
        data_kelas = kelas.objects.filter(id=edit_id).first()
        if data_kelas:
            edit_data_atribut_kelas.append({
                'id': data_kelas.id,
                'nama_kelas': data_kelas.nama,
            })
    
    if request.method == 'POST':
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
        
        return redirect('admin_atribut_kelas')
        
    kelas_list = kelas.objects.all()
    
    table_data = [
        [kelas.id, kelas.nama]
        for kelas in kelas_list
    ]
    context = get_context()
    context.update({
        'table_columns': ['ID Kelas', 'Nama Kelas'],
        'table_data': table_data,
        'edit_data_atribut_kelas': edit_data_atribut_kelas,
        'kelas': True,
        'total_data_table': kelas_list.count(),
    })
    return render(request, 'CustomAdmin/admin_atribut_kelas.html', context)

@cek_instalasi
@superuser_required
def admin_atribut_mapel(request):
    edit_data_atribut_mapel = []
    edit_id = request.GET.get('id')
    if edit_id:
        data_mapel = mata_pelajaran.objects.filter(id=edit_id).first()
        if data_mapel:
            edit_data_atribut_mapel.append({
                'id': data_mapel.id,
                'nama_mapel': data_mapel.nama,
            })
    
    if request.method == 'POST':
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
        
        return redirect('admin_atribut_mapel')
        
    mapel_list = mata_pelajaran.objects.all()
    
    table_data = [
        [mapel.id, mapel.nama]
        for mapel in mapel_list
    ]
    context = get_context()
    context.update({
        'table_columns': ['ID Mata Pelajaran', 'Nama Mata Pelajaran'],
        'table_data': table_data,
        'edit_data_atribut_mapel': edit_data_atribut_mapel,
        'mapel': True,
        'total_data_table': mapel_list.count(),
    })
    return render(request, 'CustomAdmin/admin_atribut_mapel.html', context)

@cek_instalasi
@superuser_required
def admin_atribut_jabatan(request):
    edit_data_atribut_jabatan = []
    edit_id = request.GET.get('id')
    if edit_id:
        data_jabatan = jabatan.objects.filter(id=edit_id).first()
        if data_jabatan:
            edit_data_atribut_jabatan.append({
                'id': data_jabatan.id,
                'nama_jabatan': data_jabatan.nama,
            })
    
    if request.method == 'POST':
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
        
        return redirect('admin_atribut_jabatan')
        
    jabatan_list = jabatan.objects.all()
    
    table_data = [
        [jab.id, jab.nama]
        for jab in jabatan_list
    ]
    context = get_context()
    context.update({
        'table_columns': ['ID Jabatan', 'Nama Jabatan'],
        'table_data': table_data,
        'edit_data_atribut_jabatan': edit_data_atribut_jabatan,
        'jabatan': True,
        
        'total_data_table': jabatan_list.count(),
    })
    return render(request, 'CustomAdmin/admin_atribut_jabatan.html', context)

@cek_instalasi
@superuser_required
def admin_atribut_jenjang(request):
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
        
        return redirect('admin_atribut_jenjang')
        
    jenjang_list = jenjang.objects.all()
    
    table_data = [
        [jen.id, jen.nama]
        for jen in jenjang_list
    ]
    context = get_context()
    context.update({
        'table_columns': ['ID Jenjang', 'Nama Jenjang'],
        'table_data': table_data,
        'edit_data_atribut_jenjang': edit_data_atribut_jenjang,
        'jenjang': True,
        
        'total_data_table': jenjang_list.count(),
    })
    return render(request, 'CustomAdmin/admin_atribut_jenjang.html', context)

@cek_instalasi
@superuser_required
def admin_sakit(request):
    context = get_context()
    context.update({
    })
    return render(request, 'CustomAdmin/admin_sakit.html', context)

@cek_instalasi
@superuser_required
def admin_sakit_siswa(request):
    edit_data_sakit_siswa = []
    edit_id = request.GET.get('id')
    if edit_id:
        data_sakit = sakit.objects.filter(id=edit_id).first()
        if data_sakit:
            edit_data_sakit_siswa.append({
                'id': data_sakit.id,
                'user': data_sakit.user,
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
    
    sakit_list = sakit.objects.filter(user__siswa__isnull=False)
    
    table_data = [
        [sakit_obj.id, sakit_obj.user.username, sakit_obj.keterangan, sakit_obj.surat_sakit.name if sakit_obj.surat_sakit else '']
        for sakit_obj in sakit_list
    ]
    context = get_context()
    context.update({
        'table_columns': ['ID', 'Nama Siswa', 'Keterangan', 'Surat Sakit'],
        'table_data': table_data,
        'edit_data_sakit_siswa': edit_data_sakit_siswa,
        'siswa_list': CustomUser.objects.filter(siswa__isnull=False),
        'sakit': True,
        
        'total_data_table': sakit_list.count(),
    })
    return render(request, 'CustomAdmin/admin_sakit_siswa.html', context)

@cek_instalasi
@superuser_required
def admin_sakit_guru(request):
    edit_data_sakit_guru = []
    edit_id = request.GET.get('id')
    if edit_id:
        data_sakit = sakit.objects.filter(id=edit_id).first()
        if data_sakit:
            edit_data_sakit_guru.append({
                'id': data_sakit.id,
                'user': data_sakit.user,
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
        [sakit_obj.id, sakit_obj.user.username, sakit_obj.keterangan, sakit_obj.surat_sakit.name if sakit_obj.surat_sakit else '']
        for sakit_obj in sakit_list
    ]
       
    context = get_context()     
    context.update({
        'table_columns': ['ID', 'Nama Guru', 'Keterangan', 'Surat Sakit'],
        'table_data': table_data,
        'edit_data_sakit_guru': edit_data_sakit_guru,
        'guru_list': CustomUser.objects.filter(guru__isnull=False),
        'sakit': True,
        
        'total_data_table': sakit_list.count(),
    })
    return render(request, 'CustomAdmin/admin_sakit_guru.html', context)

@cek_instalasi
@superuser_required
def admin_sakit_karyawan(request):
    edit_data_sakit_karyawan = []
    edit_id = request.GET.get('id')
    if edit_id:
        data_sakit = sakit.objects.filter(id=edit_id).first()
        if data_sakit:
            edit_data_sakit_karyawan.append({
                'id': data_sakit.id,
                'user': data_sakit.user,
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
        [sakit_obj.id, sakit_obj.user.username, sakit_obj.keterangan, sakit_obj.surat_sakit.name if sakit_obj.surat_sakit else '']
        for sakit_obj in sakit_list
    ]
    context = get_context()
    context.update({
        'table_columns': ['ID', 'Nama Karyawan', 'Keterangan', 'Surat Sakit'],
        'table_data': table_data,
        'edit_data_sakit_karyawan': edit_data_sakit_karyawan,
        'karyawan_list': CustomUser.objects.filter(karyawan__isnull=False),
        'sakit': True,
        
        'total_data_table': sakit_list.count(),
    })
    return render(request, 'CustomAdmin/admin_sakit_karyawan.html', context)

@cek_instalasi
@superuser_required
def admin_izin(request):
    context = get_context()
    context.update({
    })
    return render(request, 'CustomAdmin/admin_izin.html', context)

@cek_instalasi
@superuser_required
def admin_izin_siswa(request):
    edit_data_izin_siswa = []
    edit_id = request.GET.get('id')
    if edit_id:
        data_izin = izin.objects.filter(id=edit_id).first()
        if data_izin:
            edit_data_izin_siswa.append({
                'id': data_izin.id,
                'user': data_izin.user,
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
        [izin_obj.id, izin_obj.user.username, izin_obj.keterangan]
        for izin_obj in izin_list
    ]
    
    context = get_context()
    context.update({
        'table_columns': ['ID', 'Nama Siswa', 'Keterangan'],
        'table_data': table_data,
        'edit_data_izin_siswa': edit_data_izin_siswa,
        'siswa_list': CustomUser.objects.filter(siswa__isnull=False),
        'izin': True,
        
        'total_data_table': izin_list.count(),
    })
    return render(request, 'CustomAdmin/admin_izin_siswa.html', context)

@cek_instalasi
@superuser_required
def admin_izin_guru(request):
    edit_data_izin_guru = []
    edit_id = request.GET.get('id')
    if edit_id:
        data_izin = izin.objects.filter(id=edit_id).first()
        if data_izin:
            edit_data_izin_guru.append({
                'id': data_izin.id,
                'user': data_izin.user,
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
        [izin_obj.id, izin_obj.user.username, izin_obj.keterangan]
        for izin_obj in izin_list
    ]
    
    context = get_context()
    context.update({
        'table_columns': ['ID', 'Nama Guru', 'Keterangan'],
        'table_data': table_data,
        'edit_data_izin_guru': edit_data_izin_guru,
        'guru_list': CustomUser.objects.filter(guru__isnull=False),
        'izin': True,
        
        'total_data_table': izin_list.count(),
    })
    return render(request, 'CustomAdmin/admin_izin_guru.html', context)

@cek_instalasi
@superuser_required
def admin_izin_karyawan(request):
    edit_data_izin_karyawan = []
    edit_id = request.GET.get('id')
    if edit_id:
        data_izin = izin.objects.filter(id=edit_id).first()
        if data_izin:
            edit_data_izin_karyawan.append({
                'id': data_izin.id,
                'user': data_izin.user,
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
        [izin_obj.id, izin_obj.user.username, izin_obj.keterangan]
        for izin_obj in izin_list
    ]
    
    context = get_context()
    context.update({
        'table_columns': ['ID', 'Nama Karyawan', 'Keterangan'],
        'table_data': table_data,
        'edit_data_izin_karyawan': edit_data_izin_karyawan,
        'karyawan_list': CustomUser.objects.filter(karyawan__isnull=False),
        'izin': True,
        
        'total_data_table': izin_list.count(),
    })
    return render(request, 'CustomAdmin/admin_izin_karyawan.html', context)

@cek_instalasi
@superuser_required
def admin_pengaturan(request):
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

@cek_instalasi
@superuser_required
def admin_verifikasi(request):
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

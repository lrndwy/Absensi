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
                    user_id = request.POST.get('user')
                    status = request.POST.get('status')
                    checktime = request.POST.get('checktime')
                    tipe_absensi = request.POST.get('tipe_absensi')
                    
                    user = CustomUser.objects.get(id=user_id)
                    guru = Guru.objects.get(user=user)
                    instalasi = Instalasi.objects.first()
                    
                    if status == 'hadir':
                        # Cek duplikasi absensi
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
                            try:
                                jam_masuk_record = record_absensi.objects.filter(
                                    user=user,
                                    status='hadir',
                                    tipe_absensi='masuk',
                                    checktime__date=datetime.strptime(checktime, '%Y-%m-%dT%H:%M').date()
                                ).latest('checktime')
                                
                                waktu_pulang = timezone.make_aware(datetime.strptime(checktime, '%Y-%m-%dT%H:%M'))
                                jam_kerja = instalasi.jam_kerja_guru
                                
                                selisih_waktu = waktu_pulang - jam_masuk_record.checktime
                                
                                if selisih_waktu < jam_kerja:
                                    messages.error(request, f'Waktu pulang tidak boleh lebih cepat dari {jam_kerja} dari jam masuk.')
                                    return redirect('admin_dashboard_absensi_guru')
                            except record_absensi.DoesNotExist:
                                messages.error(request, 'Tidak ada data absensi masuk untuk hari ini.')
                                return redirect('admin_dashboard_absensi_guru')
                        
                        record = record_absensi.objects.create(
                            user=user,
                            status=status,
                            checktime=checktime,
                            status_verifikasi='diterima',
                            tipe_absensi=tipe_absensi
                        )
                    elif status in ['izin', 'sakit']:
                        id_status = request.POST.get(f'id_{status}')
                        status_obj = globals()[status].objects.get(id=id_status)
                        record = record_absensi.objects.create(
                            user=user,
                            status=status,
                            **{f'id_{status}': status_obj},
                            checktime=checktime,
                            status_verifikasi='diterima',
                            tipe_absensi=status
                        )
                    
                    messages.success(request, f'Data absensi guru {guru.nama} berhasil ditambahkan.')
                    
                except Exception as e:
                    messages.error(request, f'Terjadi kesalahan: {str(e)}')
                
                return redirect('admin_dashboard_absensi_guru')

            elif action == 'edit':
                try:
                    record_id = request.POST.get('id')
                    status = request.POST.get('status')
                    checktime = request.POST.get('checktime')
                    tipe_absensi = request.POST.get('tipe_absensi')
                    
                    record = record_absensi.objects.get(id=record_id)
                    old_status = record.status
                    
                    if status == 'hadir':
                        if tipe_absensi == 'pulang':
                            try:
                                jam_masuk_record = record_absensi.objects.filter(
                                    user=record.user,
                                    status='hadir',
                                    tipe_absensi='masuk',
                                    checktime__date=datetime.strptime(checktime, '%Y-%m-%dT%H:%M').date()
                                ).latest('checktime')
                                
                                waktu_pulang = timezone.make_aware(datetime.strptime(checktime, '%Y-%m-%dT%H:%M'))
                                jam_kerja = Instalasi.objects.first().jam_kerja_guru
                                
                                if waktu_pulang - jam_masuk_record.checktime < jam_kerja:
                                    messages.error(request, f'Waktu pulang tidak boleh lebih cepat dari {jam_kerja} dari jam masuk.')
                                    return redirect('admin_dashboard_absensi_guru')
                            except record_absensi.DoesNotExist:
                                messages.error(request, 'Tidak ada data absensi masuk untuk hari ini.')
                                return redirect('admin_dashboard_absensi_guru')
                        
                        record.status = status
                        record.checktime = checktime
                        record.tipe_absensi = tipe_absensi
                        record.id_izin = None
                        record.id_sakit = None
                        
                    elif status in ['izin', 'sakit']:
                        id_status = request.POST.get(f'id_{status}')
                        status_obj = globals()[status].objects.get(id=id_status)
                        record.status = status
                        record.checktime = checktime
                        setattr(record, f'id_{status}', status_obj)
                        record.tipe_absensi = status
                        # Reset field lainnya
                        if status == 'izin':
                            record.id_sakit = None
                        else:
                            record.id_izin = None
                    
                    record.save()
                    messages.success(request, f'Data absensi guru berhasil diperbarui dari {old_status} menjadi {status}.')
                    
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
            'table_columns': ['ID RECORD', 'NUPTK', 'Nama Guru', 'Jenjang', 'Kelas', 'Mata Pelajaran', 'Checktime', 'Status', 'Tipe Absensi', 'Terlambat (menit)'],
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
                'terlambat'
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

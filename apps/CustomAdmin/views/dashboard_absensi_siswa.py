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
        absensi_records = record_absensi.objects.filter(
            user__siswa__isnull=False, 
            status_verifikasi='diterima'
        ).order_by('-checktime')
        
        absensi_records_charts = record_absensi.objects.filter(
            user__siswa__isnull=False, 
            status_verifikasi='diterima',
            status='hadir'
        ).order_by('-checktime')

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
                try:
                    user_id = request.POST.get('user')
                    status = request.POST.get('status')
                    checktime = request.POST.get('checktime')
                    tipe_absensi = request.POST.get('tipe_absensi')
                    
                    user = CustomUser.objects.get(id=user_id)
                    siswa = Siswa.objects.get(user=user)
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
                            return redirect('admin_dashboard_absensi_siswa')
                        
                        if tipe_absensi == 'pulang':
                            try:
                                # Ambil jam masuk terakhir
                                jam_masuk_record = record_absensi.objects.filter(
                                    user=user,
                                    status='hadir',
                                    tipe_absensi='masuk',
                                    checktime__date=datetime.strptime(checktime, '%Y-%m-%dT%H:%M').date()
                                ).latest('checktime')
                                
                                waktu_pulang = timezone.make_aware(datetime.strptime(checktime, '%Y-%m-%dT%H:%M'))
                                selisih_waktu = waktu_pulang - jam_masuk_record.checktime
                                
                                # Gunakan jam_sekolah_siswa dari instalasi
                                if selisih_waktu < instalasi.jam_sekolah_siswa:
                                    messages.error(request, f'Waktu pulang tidak boleh lebih cepat dari {instalasi.jam_sekolah_siswa} dari jam masuk.')
                                    return redirect('admin_dashboard_absensi_siswa')
                            except record_absensi.DoesNotExist:
                                messages.error(request, 'Tidak ada data absensi masuk untuk hari ini.')
                                return redirect('admin_dashboard_absensi_siswa')

                        # Buat record baru
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
                            tipe_absensi='izin'
                        )
                        
                    elif status == 'sakit':
                        id_sakit = request.POST.get('id_sakit')
                        sakit_obj = sakit.objects.get(id=id_sakit)
                        record = record_absensi.objects.create(
                            user=user,
                            status=status,
                            id_sakit=sakit_obj,
                            checktime=checktime,
                            status_verifikasi='diterima',
                            tipe_absensi='sakit'
                        )
                        
                    messages.success(request, 'Data absensi berhasil ditambahkan.')
                    
                except CustomUser.DoesNotExist:
                    messages.error(request, 'Pengguna tidak ditemukan.')
                except Siswa.DoesNotExist:
                    messages.error(request, 'Data siswa tidak ditemukan.')
                except izin.DoesNotExist:
                    messages.error(request, 'Data izin tidak ditemukan.')
                except sakit.DoesNotExist:
                    messages.error(request, 'Data sakit tidak ditemukan.')
                except Exception as e:
                    messages.error(request, f'Terjadi kesalahan: {str(e)}')
                
                return redirect('admin_dashboard_absensi_siswa')
            
            elif action == 'edit':
                try:
                    record_id = request.POST.get('id')
                    status = request.POST.get('status')
                    checktime = request.POST.get('checktime')
                    tipe_absensi = request.POST.get('tipe_absensi')
                    
                    record = record_absensi.objects.get(id=record_id)
                    old_status = record.status
                    instalasi = Instalasi.objects.first()
                    
                    record.status = status
                    record.checktime = checktime
                    
                    if status == 'hadir':
                        record.tipe_absensi = tipe_absensi
                        if tipe_absensi == 'pulang':
                            try:
                                # Ambil jam masuk terakhir siswa
                                jam_masuk_record = record_absensi.objects.filter(
                                    user=record.user,
                                    status='hadir',
                                    tipe_absensi='masuk',
                                    checktime__date=datetime.strptime(checktime, '%Y-%m-%dT%H:%M').date()
                                ).latest('checktime')
                                
                                # Hitung selisih waktu
                                waktu_pulang = timezone.make_aware(datetime.strptime(checktime, '%Y-%m-%dT%H:%M'))
                                
                                # Ambil jam sekolah siswa dari instalasi
                                jam_sekolah = instalasi.jam_sekolah_siswa
                                
                                selisih_waktu = waktu_pulang - jam_masuk_record.checktime
                                
                                if selisih_waktu < jam_sekolah:
                                    messages.error(request, f'Waktu pulang tidak boleh lebih cepat dari {jam_sekolah} dari jam masuk.')
                                    return redirect('admin_dashboard_absensi_siswa')
                            except record_absensi.DoesNotExist:
                                messages.error(request, 'Tidak ada data absensi masuk untuk hari ini.')
                                return redirect('admin_dashboard_absensi_siswa')
                    
                    elif status == 'izin':
                        id_izin = request.POST.get('id_izin')
                        izin_obj = izin.objects.get(id=id_izin)
                        record.id_izin = izin_obj
                        record.id_sakit = None
                        record.tipe_absensi = 'izin'
                        
                    elif status == 'sakit':
                        id_sakit = request.POST.get('id_sakit')
                        sakit_obj = sakit.objects.get(id=id_sakit)
                        record.id_sakit = sakit_obj
                        record.id_izin = None
                        record.tipe_absensi = 'sakit'
                    
                    record.save()
                    messages.success(request, f'Data absensi siswa berhasil diperbarui dari {old_status} menjadi {status}.')
                    
                except ValueError as e:
                    messages.error(request, str(e))
                except record_absensi.DoesNotExist:
                    messages.error(request, 'Data absensi tidak ditemukan')
                except (izin.DoesNotExist, sakit.DoesNotExist):
                    messages.error(request, 'Data izin/sakit tidak ditemukan')
                except Exception as e:
                    messages.error(request, f'Terjadi kesalahan: {str(e)}')
                
                return redirect('admin_dashboard_absensi_siswa')
            
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
            'table_columns': ['ID RECORD', 'NISN', 'Nama Siswa', 'Jenjang', 'Kelas', 'Checktime', 'Status', 'Tipe Absensi', 'Terlambat (menit)', 'Mesin'],
            'table_data': absensi_records.values_list(
                'id',
                'user__siswa__nisn',
                'user__siswa__nama',
                'user__siswa__jenjang__nama',
                'user__siswa__kelas__nama',
                'checktime',
                'status',
                'tipe_absensi',
                'terlambat',
                'mesin'
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

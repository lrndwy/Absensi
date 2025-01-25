from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils import timezone
from apps.CustomAdmin.functions import *
from apps.main.instalasi import cek_instalasi, get_context
from apps.main.models import tanggal_merah
import pandas as pd
from datetime import datetime
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.urls import reverse

@cek_instalasi
@superuser_required
def admin_tanggal_merah(request):
    try:
        edit_data_tanggal_merah = []
        edit_id = request.GET.get('id')
        if edit_id:
            data_tamer = tanggal_merah.objects.filter(id=edit_id).first()
            if data_tamer:
                edit_data_tanggal_merah.append({
                    'id': data_tamer.id,
                    'nama_acara': data_tamer.nama_acara,
                    'tanggal': data_tamer.tanggal,
                    'keterangan': data_tamer.keterangan,
                    'kategori': data_tamer.kategori
                })
                messages.info(request, 'Data tanggal merah berhasil dimuat untuk diedit.')
                
        if request.method == 'POST':
            action = request.POST.get('action')
            
            if action == 'tambah':
                nama_acara = request.POST.get('nama_acara')
                tanggal = request.POST.get('tanggal')
                keterangan = request.POST.get('keterangan')
                kategori = request.POST.get('kategori')
                
                tanggal_merah.objects.create(
                    nama_acara=nama_acara,
                    tanggal=tanggal,
                    keterangan=keterangan,
                    kategori=kategori
                )
                messages.success(request, 'Data tanggal merah berhasil ditambahkan.')
                
            elif action == 'edit':
                id_tamer = request.POST.get('id')
                nama_acara = request.POST.get('nama_acara')
                tanggal = request.POST.get('tanggal')
                keterangan = request.POST.get('keterangan')
                kategori = request.POST.get('kategori')
                
                tamer_obj = tanggal_merah.objects.get(id=id_tamer)
                tamer_obj.nama_acara = nama_acara
                tamer_obj.tanggal = tanggal
                tamer_obj.keterangan = keterangan
                tamer_obj.kategori = kategori
                tamer_obj.save()
                messages.success(request, 'Data tanggal merah berhasil diperbarui.')
                
            elif action == 'hapus':
                selected_ids = request.POST.getlist('selectedIds')
                deleted_count = 0
                for id_group in selected_ids:
                    ids = id_group.split(',')
                    for id in ids:
                        try:
                            tamer_obj = tanggal_merah.objects.get(id=int(id))
                            tamer_obj.delete()
                            deleted_count += 1
                        except ValueError:
                            messages.error(request, f'ID tidak valid: {id}')
                        except tanggal_merah.DoesNotExist:
                            messages.error(request, f'Data tanggal merah dengan ID {id} tidak ditemukan')
                
                if deleted_count > 0:
                    messages.success(request, f'{deleted_count} data tanggal merah berhasil dihapus.')
                else:
                    messages.warning(request, 'Tidak ada data tanggal merah yang dihapus.')
            
            elif action == 'import':
                try:
                    file_type = request.POST.get('file_type')
                    file = request.FILES.get('file_input')
                    
                    if file_type == 'csv':
                        df = pd.read_csv(file)
                    elif file_type == 'excel':
                        df = pd.read_excel(file)
                    else:
                        messages.error(request, 'Tipe file tidak didukung.')
                        return redirect('admin_tanggal_merah')
                    
                    success_count = 0
                    error_count = 0
                    
                    for _, row in df.iterrows():
                        try:
                            # Coba beberapa format tanggal yang umum
                            tanggal_str = str(row['tanggal'])
                            tanggal = None
                            
                            format_tanggal = [
                                '%Y-%m-%d',      # 2024-01-01
                                '%d-%m-%Y',      # 01-01-2024
                                '%d/%m/%Y',      # 01/01/2024
                                '%Y/%m/%d',      # 2024/01/01
                                '%d-%B-%Y',      # 01-January-2024
                                '%d %B %Y',      # 01 January 2024
                                '%d-%b-%Y',      # 01-Jan-2024
                                '%d %b %Y',      # 01 Jan 2024
                                '%B %d, %Y',     # January 01, 2024
                                '%Y%m%d',        # 20240101
                            ]
                            
                            for format in format_tanggal:
                                try:
                                    tanggal = datetime.strptime(tanggal_str, format).date()
                                    break
                                except ValueError:
                                    continue
                            
                            if tanggal is None:
                                # Jika masih None, coba parse dengan pandas
                                try:
                                    tanggal = pd.to_datetime(tanggal_str).date()
                                except:
                                    raise ValueError(f"Format tanggal tidak valid: {tanggal_str}")
                            
                            tanggal_merah.objects.create(
                                nama_acara=row['nama_acara'],
                                tanggal=tanggal,
                                keterangan=row['keterangan'],
                                kategori=row['kategori']
                            )
                            success_count += 1
                        except Exception as e:
                            error_count += 1
                            print(f'Gagal mengimpor data: {str(e)}')
                    
                    if success_count > 0:
                        messages.success(request, f'{success_count} data berhasil diimpor.')
                    if error_count > 0:
                        messages.error(request, f'{error_count} data gagal diimpor.')
                        
                    return redirect('admin_tanggal_merah')
                except Exception as e:
                    messages.error(request, f'Terjadi kesalahan saat mengimpor file: {str(e)}')
                    return redirect('admin_tanggal_merah')
            
            return redirect('admin_tanggal_merah')
        
        tamer_list = tanggal_merah.objects.all().order_by('tanggal')
        
        table_data = [
            [tamer_obj.id, tamer_obj.nama_acara, tamer_obj.tanggal.strftime('%d-%m-%Y'), tamer_obj.keterangan, tamer_obj.kategori]
            for tamer_obj in tamer_list
        ]
        
        context = get_context()
        context.update({
            'table_columns': ['ID', 'Nama Acara', 'Tanggal', 'Keterangan', 'Kategori'],
            'table_data': table_data,
            'edit_data_tanggal_merah': edit_data_tanggal_merah,
            'total_data_table': tamer_list.count(),
            'API_LINK': reverse('api_tanggal_merah'),
        })
        
        return render(request, 'CustomAdmin/admin_tamer.html', context)
        
    except Exception as e:
        messages.error(request, f'Terjadi kesalahan pada sistem: {str(e)}')
        return redirect('admin_tanggal_merah')

@cek_instalasi
@superuser_required
@require_http_methods(['GET'])
def api_tanggal_merah(request):
    try:
        tamer_list = tanggal_merah.objects.all().order_by('tanggal')
        data = []
        
        for tamer in tamer_list:
            data.append({
                'id': tamer.id,
                'nama_acara': tamer.nama_acara,
                'tanggal': tamer.tanggal.strftime('%d-%m-%Y'),
                'keterangan': tamer.keterangan,
                'kategori': tamer.kategori
            })
            
        return JsonResponse({'data': data})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

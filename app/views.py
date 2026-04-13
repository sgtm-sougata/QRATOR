from django.shortcuts import render, redirect, get_object_or_404, HttpResponse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import logout
from django.core.files.storage import default_storage
from django.conf import settings
from django.utils import timezone
from django.urls import reverse
from django.http import HttpResponse
import os
import zipfile
import shutil
import csv
from io import StringIO
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from pathlib import Path
import tempfile
from .models import (
    Project, UploadZip, Roi, RadiomicFeatures, RadiomicFeatureMapping, ExtractionSession
)


import sys
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'utils'))
from dicomorganizer import DicomOrganizer
from normalization import clean_contour_label
import requests
import json
import numpy as np
from bokeh.plotting import figure
from bokeh.embed import components
from bokeh.models import HoverTool
from bokeh.resources import CDN
from django.urls import reverse
from django.db.models import Count, Avg, Min, Max
from django.db.models.functions import TruncDate
from dotenv import load_dotenv
import numpy as np
import SimpleITK as sitk
from rt_utils import RTStructBuilder
import logging

# Load environment variables at the top of the file
load_dotenv()

@login_required
def dashboard_home(request):
    # Get user's recent projects
    recent_projects = Project.objects.filter(user=request.user).order_by('-updated_at')[:5]
    
    # Get total ROI count for the user
    from .models import Roi
    roi_count = Roi.objects.filter(
        rtstruct__series_instance__series__study__patient__uploaded_zip_file__uploaded_by=request.user
    ).count()
    
    context = {
        'page_title': 'Dashboard',
        'recent_projects': recent_projects,
        'roi_count': roi_count,
    }
    return render(request, 'app/home.html', context)

@login_required
def workspace(request):
    try:
        # Get all projects for the current user
        projects = Project.objects.filter(user=request.user).order_by('-updated_at')
      
    except Exception as e:
        # If there's a database error, show empty state
        projects = []
        messages.error(request, f'Database error: {str(e)}. Please ensure the Project table exists.')
    
    context = {
        'page_title': 'Workspace',
        'projects': projects,
    }
    return render(request, 'app/workspace.html', context)

@login_required
def settings(request):
    context = {
        'page_title': 'Settings',
    }
    return render(request, 'app/settings.html', context)

@login_required
def analytics(request):
    from .models import RadiomicFeatures, UploadZip, Roi, ExtractionSession
    from django.db.models import Count, Avg, Min, Max
    from django.db.models.functions import TruncDate
    
    # Get user's radiomics data
    user_radiomics = RadiomicFeatures.objects.filter(
        zip_id__uploaded_by=request.user
    ).select_related('roi', 'patient_id', 'zip_id', 'zip_id__project')
    
    # Get extraction sessions for the user
    extraction_sessions = ExtractionSession.objects.filter(
        radiomicfeatures__zip_id__uploaded_by=request.user
    ).distinct().order_by('-extraction_date')[:10]
    
    # Calculate statistics
    total_extractions = user_radiomics.count()
    unique_patients = user_radiomics.values('patient_id').distinct().count()
    unique_rois = user_radiomics.values('roi_name').distinct().count()
    
    # Get recent extraction sessions with ROI counts and project/zip info
    session_stats = []
    for session in extraction_sessions:
        # Get radiomics data for this session
        session_radiomics = RadiomicFeatures.objects.filter(
            extraction_session=session,
            zip_id__uploaded_by=request.user
        ).select_related('zip_id', 'zip_id__project').first()
        
        roi_count = RadiomicFeatures.objects.filter(
            extraction_session=session,
            zip_id__uploaded_by=request.user
        ).count()
        
        # Default values
        project_name = 'Unknown Project'
        zip_name = 'Unknown File'
        zip_id = None
        
        if session_radiomics and hasattr(session_radiomics, 'zip_id'):
            zip_id = session_radiomics.zip_id.id
            zip_name = getattr(session_radiomics.zip_id, 'name', 'Unknown File')
            
            if hasattr(session_radiomics.zip_id, 'project') and session_radiomics.zip_id.project:
                project_name = getattr(session_radiomics.zip_id.project, 'name', 'Unknown Project')
        
        session_stats.append({
            'session': session,
            'roi_count': roi_count,
            'project_name': project_name,
            'zip_name': zip_name,
            'zip_id': zip_id
        })
    
    # Get most common ROI names
    common_rois = user_radiomics.exclude(roi_name__isnull=True).exclude(roi_name='').values('roi_name').annotate(
        count=Count('roi_name')
    ).order_by('-count')[:10]
    
    # Get feature statistics (sample a few key features)
    feature_stats = {}
    if user_radiomics.exists():
        sample_features = [
            'original_shape_VoxelVolume',
            'original_shape_Sphericity', 
            'original_firstorder_Mean',
            'original_glcm_Correlation'
        ]
        
        for feature in sample_features:
            values = user_radiomics.exclude(**{feature: None}).values_list(feature, flat=True)
            if values:
                feature_stats[feature] = {
                    'avg': round(sum(values) / len(values), 3),
                    'min': round(min(values), 3),
                    'max': round(max(values), 3),
                    'count': len(values)
                }
    
    # Get extraction timeline data
    timeline_data = user_radiomics.annotate(
        date=TruncDate('extraction_session__extraction_date')
    ).values('date').annotate(
        count=Count('id')
    ).order_by('date')
    
    context = {
        'page_title': 'Radiomics Analytics',
        'total_extractions': total_extractions,
        'unique_patients': unique_patients,
        'unique_rois': unique_rois,
        'session_stats': session_stats,
        'common_rois': common_rois,
        'feature_stats': feature_stats,
        'timeline_data': list(timeline_data),
        'has_data': user_radiomics.exists()
    }
    return render(request, 'app/analytics.html', context)

@login_required
def edit_project(request, project_id):
    try:
        project = get_object_or_404(Project, id=project_id, user=request.user)
        
        if request.method == 'POST':
            name = request.POST.get('name', '').strip()
            description = request.POST.get('description', '').strip()
            
            # Validate input
            if not name or not description:
                messages.error(request, 'Please fill in all required fields.')
                return redirect('app:project_detail', project_id=project_id)
            
            if len(name) > 100:
                messages.error(request, 'Project name must be 100 characters or less.')
                return redirect('app:project_detail', project_id=project_id)
            
            # Check if project name already exists for this user (excluding current project)
            if Project.objects.filter(name=name, user=request.user).exclude(id=project_id).exists():
                messages.error(request, 'A project with this name already exists.')
                return redirect('app:project_detail', project_id=project_id)
            
            # Update project
            project.name = name
            project.description = description
            project.save()
            
            messages.success(request, f'Project "{project.name}" updated successfully!')
            return redirect('app:project_detail', project_id=project_id)
    except Exception as e:
        messages.error(request, f'An error occurred while updating the project: {str(e)}')
    
    return redirect('app:project_detail', project_id=project_id)

@login_required
def delete_project(request, project_id):
    try:
        project = get_object_or_404(Project, id=project_id, user=request.user)
        project_name = project.name
        
        # Delete all associated files
        for upload_zip in project.uploadzip_set.all():
            # Delete extracted files if they exist
            if upload_zip.extracted_path and os.path.exists(upload_zip.extracted_path):
                shutil.rmtree(upload_zip.extracted_path)
            
            # Delete the ZIP file
            if upload_zip.zip_file:
                upload_zip.zip_file.delete()
        
        # Delete the project
        project.delete()
        messages.success(request, f'Project "{project_name}" and all associated files have been deleted.')
    except Exception as e:
        messages.error(request, f'An error occurred while deleting the project: {str(e)}')
    
    return redirect('app:workspace')

@login_required
def delete_zip(request, zip_id):
    try:
        upload_zip = get_object_or_404(UploadZip, id=zip_id, uploaded_by=request.user)
        project_id = upload_zip.project.id
        zip_name = upload_zip.name
        
        # Delete extracted files if they exist
        if upload_zip.extracted_path and os.path.exists(upload_zip.extracted_path):
            shutil.rmtree(upload_zip.extracted_path)
        
        # Delete the ZIP file
        if upload_zip.zip_file:
            upload_zip.zip_file.delete()
        
        # Delete the database record
        upload_zip.delete()
        
        messages.success(request, f'ZIP file "{zip_name}" and all associated files have been deleted.')
        return redirect('app:project_detail', project_id=project_id)
    except Exception as e:
        messages.error(request, f'An error occurred while deleting the ZIP file: {str(e)}')
        return redirect('app:workspace')

@login_required
def create_project(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        
        # Validate input
        if not name or not description:
            messages.error(request, 'Please fill in all required fields.')
            return redirect('app:workspace')
        
        if len(name) > 50:
            messages.error(request, 'Project name must be 50 characters or less.')
            return redirect('app:workspace')
        
        try:
            # Check if project name already exists for this user
            if Project.objects.filter(name=name, user=request.user).exists():
                messages.error(request, 'A project with this name already exists.')
                return redirect('app:workspace')
            
            # Create new project
            project = Project.objects.create(
                name=name,
                description=description,
                user=request.user
            )
            messages.success(request, f'Project "{project.name}" created successfully!')
        except Exception as e:
            messages.error(request, f'An error occurred while creating the project: {str(e)}')
        
        return redirect('app:workspace')
    
    # If not POST, redirect to workspace
    return redirect('app:workspace')

@login_required
def project_detail(request, project_id):
    try:
        project = get_object_or_404(Project, id=project_id, user=request.user)
        # Get all uploaded zip files for this project
        uploaded_zips = UploadZip.objects.filter(project=project).order_by('-uploaded_at')
    except Exception as e:
        uploaded_zips = []
        messages.error(request, f'Error loading project: {str(e)}')
    
    context = {
        'page_title': f'Project: {project.name}',
        'project': project,
        'uploaded_zips': uploaded_zips,
    }
    return render(request, 'app/project_detail.html', context)

@login_required
def upload_zip(request, project_id):
    try:
        project = get_object_or_404(Project, id=project_id, user=request.user)
    except Exception as e:
        messages.error(request, f'Project not found: {str(e)}')
        return redirect('app:workspace')
    
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        version = request.POST.get('version', '').strip()
        description = request.POST.get('description', '').strip()
        zip_file = request.FILES.get('zip_file')
        
        # Validate input
        if not all([name, version, description, zip_file]):
            messages.error(request, 'Please fill in all required fields and select a ZIP file.')
            return redirect('app:project_detail', project_id=project_id)
        
        try:
            version = int(version)
        except ValueError:
            messages.error(request, 'Version must be a number.')
            return redirect('app:project_detail', project_id=project_id)
        
        if not zip_file.name.endswith('.zip'):
            messages.error(request, 'Please upload a ZIP file.')
            return redirect('app:project_detail', project_id=project_id)
        
        try:
            # Create new upload zip record
            upload_zip = UploadZip.objects.create(
                project=project,
                zip_file=zip_file,
                name=name,
                version=version,
                description=description,
                zip_file_size=zip_file.size,
                extracted_path='',  # Will be set after extraction
                extracted_folder_size=0,  # Will be calculated after extraction
                uploaded_by=request.user
            )
            messages.success(request, f'ZIP file "{name}" uploaded successfully!')
        except Exception as e:
            messages.error(request, f'An error occurred while uploading: {str(e)}')
        
        return redirect('app:project_detail', project_id=project_id)
    
    # If not POST, redirect to project detail
    return redirect('app:project_detail', project_id=project_id)

@login_required
def zip_detail(request, zip_id):
    try:
        upload_zip = get_object_or_404(UploadZip, id=zip_id, uploaded_by=request.user)
        # Get all patients associated with this ZIP file
        from .models import Patient, Rtstruct, Roi
        patients = Patient.objects.filter(uploaded_zip_file=upload_zip)
        
        # Get all RTSTRUCT data associated with this ZIP file
        rtstructs = Rtstruct.objects.filter(
            series_instance__series__study__patient__uploaded_zip_file=upload_zip
        ).select_related(
            'series_instance__series__study__patient',
            'series_instance__series__study'
        )
        # Build unique ROI names for this ZIP for selective conversion
        rois_for_zip = Roi.objects.filter(
            rtstruct__series_instance__series__study__patient__uploaded_zip_file_id=upload_zip.id
        )
        import os, re
        def _normalize_name(name: str):
            try:
                return re.sub(r"\s+", " ", str(name)).strip()
            except Exception:
                return str(name).strip() if name is not None else ""
        unique_roi_names = {}
        # Build allowed ROI directories for this ZIP only (kept for potential future use)
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        for roi in rois_for_zip:
            raw_display = roi.user_modified_name if roi.user_modified_name and roi.user_modified_name.strip() else roi.roi_name
            display_name = _normalize_name(raw_display)
            # Identify the patient this ROI belongs to
            try:
                patient_id_for_roi = roi.rtstruct.series_instance.series.study.patient.patient_id
            except Exception:
                patient_id_for_roi = None
            if display_name in unique_roi_names:
                # Increment total occurrences
                unique_roi_names[display_name]['count'] += 1
                # Track unique patients (kept for potential future use)
                if patient_id_for_roi is not None:
                    unique_roi_names[display_name]['patient_ids'].add(patient_id_for_roi)
                # Mark converted if any instance has an existing file or a glob match
                if not unique_roi_names[display_name].get('nifti_converted'):
                    if roi.roi_nrrd_file_path and os.path.exists(roi.roi_nrrd_file_path):
                        unique_roi_names[display_name]['nifti_converted'] = True
            else:
                unique_roi_names[display_name] = {
                    'count': 1,
                    'sample_roi_id': roi.id,
                    'original_roi_name': roi.roi_name,
                    'has_modified_name': bool(roi.user_modified_name and roi.user_modified_name.strip()),
                    'nifti_converted': False,
                    'patient_ids': set([patient_id_for_roi]) if patient_id_for_roi is not None else set(),
                }
                # Initial status check for first occurrence
                if roi.roi_nrrd_file_path and os.path.exists(roi.roi_nrrd_file_path):
                    unique_roi_names[display_name]['nifti_converted'] = True
    except Exception as e:
        patients = []
        rtstructs = []
        messages.error(request, f'Error loading ZIP file details: {str(e)}')
        return redirect('app:workspace')
    
    context = {
        'page_title': f'ZIP: {upload_zip.name}',
        'upload_zip': upload_zip,
        'patients': patients,
        'rtstructs': rtstructs,
        'unique_roi_names': unique_roi_names,
        'total_studies': sum(getattr(p, 'study_set').count() for p in patients),
    }
    return render(request, 'app/zip_detail.html', context)

@login_required
def extract_zip(request, zip_id):
    try:
        upload_zip = get_object_or_404(UploadZip, id=zip_id, uploaded_by=request.user)
        
        # Check if already extracted
        if upload_zip.extracted_path:
            messages.info(request, f'ZIP file "{upload_zip.name}" has already been extracted.')
            return redirect('app:zip_detail', zip_id=zip_id)
        
        # Get the path to the uploaded ZIP file
        zip_file_path = upload_zip.zip_file.path
        messages.info(request, f'ZIP file path: {zip_file_path}')
        
        if not os.path.exists(zip_file_path):
            messages.error(request, f'ZIP file not found at path: {zip_file_path}')
            return redirect('app:zip_detail', zip_id=zip_id)
        
        # Hardcode the path to the media directory
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        media_dir = os.path.join(base_dir, 'media', 'extracted_zip_files')
        os.makedirs(media_dir, exist_ok=True)
        
        # Create extraction directory
        zip_base_name = os.path.splitext(os.path.basename(zip_file_path))[0]
        extract_dir_path = os.path.join(media_dir, zip_base_name)
        messages.info(request, f'Extraction directory: {extract_dir_path}')
        
        # Create the directory if it doesn't exist
        os.makedirs(extract_dir_path, exist_ok=True)
        
        # Check if the directory was created successfully
        if not os.path.exists(extract_dir_path):
            messages.error(request, f'Failed to create extraction directory: {extract_dir_path}')
            return redirect('app:zip_detail', zip_id=zip_id)
        
        # Extract the ZIP file
        try:
            with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
                file_list = zip_ref.namelist()
                messages.info(request, f'ZIP contains {len(file_list)} files')
                
                # Extract the ZIP file
                zip_ref.extractall(extract_dir_path)
                messages.info(request, f'Files extracted to {extract_dir_path}')
        except zipfile.BadZipFile:
            messages.error(request, f'The file "{upload_zip.name}" is not a valid ZIP file.')
            return redirect('app:zip_detail', zip_id=zip_id)
        except Exception as e:
            messages.error(request, f'Error during ZIP extraction: {str(e)}')
            return redirect('app:zip_detail', zip_id=zip_id)
        
        # Check if files were actually extracted
        extracted_files = []
        for root, dirs, files in os.walk(extract_dir_path):
            for file in files:
                extracted_files.append(os.path.join(root, file))
        
        if not extracted_files:
            messages.warning(request, f'No files were extracted from the ZIP file.')
            return redirect('app:zip_detail', zip_id=zip_id)
        
        messages.info(request, f'Extracted {len(extracted_files)} files')
        
        # Calculate the extracted folder size
        total_size = 0
        for fp in extracted_files:
            total_size += os.path.getsize(fp)
        
        # Update the UploadZip record
        upload_zip.extracted_path = extract_dir_path
        upload_zip.extracted_folder_size = total_size
        upload_zip.save()
        
        messages.info(request, f'Updated database with extracted_path: {upload_zip.extracted_path}')
        messages.success(request, f'ZIP file "{upload_zip.name}" has been successfully extracted!')
    except Exception as e:
        messages.error(request, f'An error occurred while extracting the ZIP file: {str(e)}')
        
        # Clean up any partially extracted files if there was an error
        if 'extract_dir_path' in locals() and os.path.exists(extract_dir_path):
            shutil.rmtree(extract_dir_path)
    
    return redirect('app:zip_detail', zip_id=zip_id)

@login_required
def patient_details(request, zip_id):
    try:
        upload_zip = get_object_or_404(UploadZip, id=zip_id, uploaded_by=request.user)
        
        # Check if ZIP has been extracted
        if not upload_zip.extracted_path:
            messages.error(request, f'ZIP file "{upload_zip.name}" has not been extracted yet.')
            return redirect('app:zip_detail', zip_id=zip_id)
        
        # Source directory is the extracted path
        source_dir = upload_zip.extracted_path
        
        if not os.path.exists(source_dir):
            messages.error(request, f'Extracted directory not found: {source_dir}')
            return redirect('app:zip_detail', zip_id=zip_id)
        
        # Get the zip basename from the zip file name
        zip_file_path = upload_zip.zip_file.path
        zip_base_name = os.path.splitext(os.path.basename(zip_file_path))[0]
        
        # Create output directory: media/patients/{zip_basename}_{zip_id}
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        media_dir = os.path.join(base_dir, 'media')
        patients_dir = os.path.join(media_dir, 'patients')
        output_dir = os.path.join(patients_dir, f'{zip_base_name}_{zip_id}')
        
        # Create the patients directory if it doesn't exist
        os.makedirs(patients_dir, exist_ok=True)
        
        # Create the specific output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Check if directories were created successfully
        if not os.path.exists(output_dir):
            messages.error(request, f'Failed to create output directory: {output_dir}')
            return redirect('app:zip_detail', zip_id=zip_id)
        
        messages.info(request, f'Source directory: {source_dir}')
        messages.info(request, f'Output directory: {output_dir}')
        
        # Use DicomOrganizer to organize DICOM files
        try:
            # Import models to pass to DicomOrganizer
            from .models import Patient, Study, Series, Instance, Rtstruct, Roi
            models = {
                'Patient': Patient,
                'Study': Study,
                'Series': Series,
                'Instance': Instance,
                'Rtstruct': Rtstruct,
                'Roi': Roi
            }
            
            messages.info(request, f'Starting DICOM organization with upload_zip: {upload_zip.id}')
            messages.info(request, f'Models passed: {list(models.keys())}')
            
            organizer = DicomOrganizer(source_dir, output_dir, upload_zip, models)
            organizer.organize_files()
            messages.success(request, f'DICOM files organized successfully in: {output_dir}')
        except Exception as e:
            messages.error(request, f'Error organizing DICOM files: {str(e)}')
            import traceback
            messages.error(request, f'Full error: {traceback.format_exc()}')
        
        # Redirect back to zip_detail page
        return redirect('app:zip_detail', zip_id=zip_id)
        
    except Exception as e:
        messages.error(request, f'An error occurred while processing patient details: {str(e)}')
        return redirect('app:zip_detail', zip_id=zip_id)

@login_required
def get_roi_data(request, rtstruct_id):
    """Get ROI data for a specific RTSTRUCT"""
    try:
        from .models import Rtstruct, Roi
        from django.http import JsonResponse
        
        # Get the RTSTRUCT and verify user has access
        rtstruct = get_object_or_404(Rtstruct, id=rtstruct_id)
        
        # Verify user has access to this RTSTRUCT through the uploaded ZIP
        if rtstruct.series_instance.series.study.patient.uploaded_zip_file.uploaded_by != request.user:
            return JsonResponse({'success': False, 'error': 'Access denied'})
        
        # Get all ROIs for this RTSTRUCT
        rois = Roi.objects.filter(rtstruct=rtstruct)
        
        roi_data = []
        for roi in rois:
            roi_data.append({
                'id': roi.id,
                'roi_number': roi.roi_number,
                'roi_name': roi.roi_name,
                'clean_roi_name': roi.clean_roi_name or '',
                'tg263_primary_name': roi.tg263_primary_name,
                'roi_of_clean_roi_name_match_tg263': roi.roi_of_clean_roi_name_match_tg263,
                'user_modified_name': roi.user_modified_name or ''
            })
        
        return JsonResponse({
            'success': True,
            'rois': roi_data
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
def harmonize_rtstruct_form(request, rtstruct_id):
    """Display RTSTRUCT harmonization form"""
    try:
        from .models import Rtstruct, Roi
        import json
        
        # Get the RTSTRUCT and verify user has access
        rtstruct = get_object_or_404(Rtstruct, id=rtstruct_id)
        
        # Verify user has access to this RTSTRUCT through the uploaded ZIP
        if rtstruct.series_instance.series.study.patient.uploaded_zip_file.uploaded_by != request.user:
            messages.error(request, 'Access denied')
            return redirect('app:workspace')
        
        # Get all ROIs for this RTSTRUCT
        rois = Roi.objects.filter(rtstruct=rtstruct).order_by('roi_number')
        messages.info(request, f'Found {rois.count()} ROIs for harmonization')
        zip_id = rtstruct.series_instance.series.study.patient.uploaded_zip_file.id
        
        # Get TG263 data (with fallback to sample data)
        tg263_data = get_tg263_data()
        tg263_available = bool(tg263_data)
        
        if not tg263_available:
            messages.warning(request, 'TG263 service is currently unavailable. Using sample data.')
        
        # Extract just the TG263 primary names for simpler handling in the template
        tg263_primary_names = [item['TG263_Primary_Name'] for item in tg263_data]
        
        context = {
            'page_title': 'ROI Harmonization',
            'rtstruct': rtstruct,
            'rois': rois,
            'zip_id': zip_id,
            'tg263_available': tg263_available,
            'tg263_data': json.dumps(tg263_data),
            'tg263_primary_names': json.dumps(tg263_primary_names)
        }
        
        return render(request, 'app/harmonize_rtstruct.html', context)
        
    except Exception as e:
        messages.error(request, f'Error loading harmonization form: {str(e)}')
        return redirect('app:workspace')

def get_tg263_data():
    """Get TG263 data with fallback to sample data"""
    data = fetch_tg263_data()
    if data:
        return data
   
def fetch_tg263_data():
    """Fetch TG263 data from the API"""
    try:
        # Get the API URL from environment variable
        tg263_api_url = os.getenv('TG263_API')
        
        if not tg263_api_url:
            print("TG263_API environment variable not found")
            return []
        
        response = requests.get(tg263_api_url, timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error fetching TG263 data: HTTP {response.status_code}")
            return []
    except requests.exceptions.RequestException as e:
        print(f"Error fetching TG263 data: {str(e)}")
        return []

def match_roi_with_tg263(roi_name, clean_roi_name, tg263_data):
    """Match ROI name or clean ROI name with TG263 data"""
    # Check for match with original ROI name
    for item in tg263_data:
        if (item.get('TG263_Primary_Name', '').lower() == roi_name.lower() or
            item.get('TG263_Reverse_Order_Name', '').lower() == roi_name.lower()):
            return item, True, "roi_name"  # Match found with original ROI name
    
    # Check for match with clean ROI name
    for item in tg263_data:
        if (item.get('TG263_Primary_Name', '').lower() == clean_roi_name.lower() or
            item.get('TG263_Reverse_Order_Name', '').lower() == clean_roi_name.lower()):
            return item, True, "clean_roi_name"  # Match found with clean ROI name
    
    return None, False, None  # No match found

def update_roi_with_tg263_data(roi, tg263_match, is_perfect_match, match_type=None):
    """Update ROI fields with TG263 data"""
    # Make sure clean_roi_name is set
    if not roi.clean_roi_name:
        roi.clean_roi_name = clean_contour_label(roi.roi_name)
    
    if tg263_match:
        # Update with TG263 data if there's a match
        roi.target_type = tg263_match.get('Target_Type', '')
        roi.major_category = tg263_match.get('Major_Category', '')
        roi.minor_category = tg263_match.get('Minor_Category', '')
        roi.anatomic_group = tg263_match.get('Anatomic_Group', '')
        roi.fma_id = tg263_match.get('FMAID', '')
        roi.tg263_primary_name = tg263_match.get('TG263_Primary_Name', '')
        roi.tg263_reverse_order_name = tg263_match.get('TG263_Reverse_Order_Name', roi.tg263_primary_name)
        roi.roi_of_clean_roi_name_match_tg263 = is_perfect_match
        
        # Lock user_modified_name if perfect match
        if is_perfect_match:
            roi.user_modified_name = roi.tg263_primary_name
        
        return True
    else:
        # No match, leave fields blank
        roi.roi_of_clean_roi_name_match_tg263 = False
        roi.target_type = ''
        roi.major_category = ''
        roi.minor_category = ''
        roi.anatomic_group = ''
        roi.fma_id = ''
        roi.tg263_primary_name = ''
        roi.tg263_reverse_order_name = ''
        
        return False

def update_dicom_roi_names(rtstruct_path, modified_rois, request=None, messages=None):
    """Helper function to update ROI names in DICOM file"""
    try:
        import pydicom
        
        if not os.path.exists(rtstruct_path):
            if messages:
                messages.warning(request, f'RTStruct file not found at path: {rtstruct_path}')
            return 0
            
        ds = pydicom.dcmread(rtstruct_path)
        if not hasattr(ds, 'StructureSetROISequence'):
            if messages:
                messages.warning(request, 'RTSTRUCT file does not contain StructureSetROISequence')
            return 0
            
        roi_count = len(ds.StructureSetROISequence)
        if messages:
            messages.info(request, f'Found {roi_count} ROIs in RTSTRUCT StructureSetROISequence')
        
        # Create ROI number mapping
        roi_number_map = {
            int(getattr(roi_seq, 'ROINumber', 0)): (i, roi_seq)
            for i, roi_seq in enumerate(ds.StructureSetROISequence)
        }
        
        updated_count = 0
        for roi in modified_rois:
            if roi.roi_number not in roi_number_map:
                if messages:
                    messages.warning(request, f'ROI #{roi.roi_number} not found in DICOM file')
                continue
                
            _, roi_seq = roi_number_map[roi.roi_number]
            original_name = getattr(roi_seq, 'ROIName', 'Unknown')
            
            # Use the ROI's user_modified_name directly
            new_name = roi.user_modified_name
            
            if new_name and original_name != new_name:
                roi_seq.ROIName = new_name
                updated_count += 1
                if messages:
                    messages.info(request, f'Updated ROI #{roi.roi_number} from "{original_name}" to "{new_name}"')
        
        if updated_count > 0:
            ds.save_as(rtstruct_path)
            if messages:
                messages.success(request, f'Updated {updated_count} ROI names in RTSTRUCT file')
        
        return updated_count
        
    except Exception as e:
        if messages:
            messages.error(request, f'Error updating DICOM file: {str(e)}')
        return 0

@login_required
def harmonize_rtstruct(request, rtstruct_id):
    """Handle RTSTRUCT harmonization form submission with automatic ROI normalization"""
    from django.http import JsonResponse
    try:
        from .models import Rtstruct, Roi
        
        # Get the RTSTRUCT and verify user has access
        rtstruct = get_object_or_404(Rtstruct, id=rtstruct_id)
        if rtstruct.series_instance.series.study.patient.uploaded_zip_file.uploaded_by != request.user:
            messages.error(request, 'Access denied')
            return redirect('app:workspace')
        
        rtstruct_path = rtstruct.rtstruct_dir
        messages.info(request, f'RTSTRUCT Path: {rtstruct_path}')
        
        if request.method == 'POST':
            # Check if this is a single ROI update via AJAX
            roi_id = request.POST.get('roi_id')
            if roi_id and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                try:
                    roi = get_object_or_404(Roi, id=roi_id, rtstruct=rtstruct)
                    original_name = roi.roi_name
                    
                    # Ensure clean_roi_name is set
                    if not roi.clean_roi_name:
                        clean_name = clean_contour_label(original_name)
                        roi.clean_roi_name = clean_name
                    else:
                        clean_name = roi.clean_roi_name
                    
                    # Get TG263 data
                    tg263_data = get_tg263_data()
                    
                    # Try to match with TG263 data
                    tg263_match, is_perfect_match, match_type = match_roi_with_tg263(original_name, clean_name, tg263_data)
                    
                    if tg263_match:
                        # Update ROI with TG263 data
                        update_roi_with_tg263_data(roi, tg263_match, is_perfect_match, match_type)
                        roi.save()
                        
                        # Update DICOM file
                        dicom_updated = update_dicom_roi_names(rtstruct_path, [roi], request, messages)
                        
                        match_message = f'ROI "{original_name}" matched to TG263 name "{tg263_match["TG263_Primary_Name"]}"'
                        if match_type == "clean_roi_name":
                            match_message += f' (via cleaned name "{clean_name}")'
                        
                        messages.success(request, match_message)
                        
                        return JsonResponse({
                            'success': True,
                            'message': match_message,
                            'normalized_count': 1,
                            'updated_count': 0
                        })
                    else:
                        # Check for user-provided modified name
                        modified_name_key = f'user_modified_name_{roi_id}'
                        if modified_name_key in request.POST:
                            modified_name = request.POST[modified_name_key].strip()
                            if modified_name and modified_name != roi.user_modified_name:
                                roi.user_modified_name = modified_name
                                roi.roi_of_clean_roi_name_match_tg263 = False
                                roi.save()
                                
                                # Update DICOM file
                                dicom_updated = update_dicom_roi_names(rtstruct_path, [roi], request, messages)
                                
                                return JsonResponse({
                                    'success': True,
                                    'message': f'ROI "{original_name}" updated with modified name',
                                    'normalized_count': 0,
                                    'updated_count': 1 if dicom_updated else 0
                                })
                        
                        return JsonResponse({
                            'success': False,
                            'message': 'No valid TG263 match or modified name provided'
                        })
                    
                except Exception as e:
                    return JsonResponse({
                        'success': False,
                        'message': f'Error updating ROI: {str(e)}'
                    })
            
            # Handle full form submission
            rois = Roi.objects.filter(rtstruct=rtstruct)
            messages.info(request, f'Found {rois.count()} ROIs for RTSTRUCT')
            
            updated_count = 0
            normalized_count = 0
            modified_rois = []
            
            for roi in rois:
                try:
                    original_name = roi.roi_name
                    
                    # Ensure clean_roi_name is set
                    if not roi.clean_roi_name:
                        clean_name = clean_contour_label(original_name)
                        roi.clean_roi_name = clean_name
                    else:
                        clean_name = roi.clean_roi_name
                    
                    # Get TG263 data
                    tg263_data = get_tg263_data()
                    
                    # Try to match with TG263 data
                    tg263_match, is_perfect_match, match_type = match_roi_with_tg263(original_name, clean_name, tg263_data)
                    
                    if tg263_match:
                        # Update ROI with TG263 data
                        update_roi_with_tg263_data(roi, tg263_match, is_perfect_match, match_type)
                        normalized_count += 1
                        
                        match_message = f'ROI "{original_name}" matched to TG263 name "{tg263_match["TG263_Primary_Name"]}"'
                        if match_type == "clean_roi_name":
                            match_message += f' (via cleaned name "{clean_name}")'
                        
                        messages.success(request, match_message)
                        modified_rois.append(roi)
                    else:
                        # Check if user provided a modified name
                        modified_name_key = f'user_modified_name_{roi.id}'
                        if modified_name_key in request.POST:
                            new_name = request.POST[modified_name_key].strip()
                            if new_name and new_name != roi.user_modified_name:
                                roi.user_modified_name = new_name
                                roi.roi_of_clean_roi_name_match_tg263 = False
                                updated_count += 1
                                modified_rois.append(roi)
                    
                    roi.save()
                    
                except Exception as e:
                    messages.error(request, f'Error processing ROI {roi.roi_name}: {str(e)}')
                    continue
            
            # Update DICOM file with all modified ROIs
            if modified_rois:
                update_dicom_roi_names(rtstruct_path, modified_rois, request, messages)
            
            # Provide summary messages
            if normalized_count > 0:
                messages.success(request, f'Successfully normalized {normalized_count} ROI name(s)')
            if updated_count > 0:
                messages.success(request, f'Successfully updated {updated_count} user-modified ROI name(s)')
            if normalized_count == 0 and updated_count == 0:
                messages.info(request, 'No changes were made')
            
            # Return response based on request type
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': 'ROI names updated successfully',
                    'normalized_count': normalized_count,
                    'updated_count': updated_count
                })
            else:
                zip_id = rtstruct.series_instance.series.study.patient.uploaded_zip_file.id
                return redirect('app:zip_detail', zip_id=zip_id)
        
    except Exception as e:
        error_message = f'Error during harmonization: {str(e)}'
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'message': error_message
            })
        else:
            messages.error(request, error_message)
            return redirect('app:workspace')

@login_required
def batch_harmonize_rois(request, zip_id):
    """Batch harmonization of all unique ROI names in a ZIP file"""
    try:
        from .models import UploadZip, Roi, Rtstruct
        import json
        from django.utils.text import slugify
        
        # Get the ZIP file and verify user has access
        upload_zip = get_object_or_404(UploadZip, id=zip_id, uploaded_by=request.user)
        
        # Get all ROIs for this ZIP file
        rois = Roi.objects.filter(
            rtstruct__series_instance__series__study__patient__uploaded_zip_file=upload_zip
        )
        
        if not rois.exists():
            messages.warning(request, 'No ROIs found for this ZIP file.')
            return redirect('app:zip_detail', zip_id=zip_id)
        
        # Get unique ROI names and their counts
        unique_roi_names = {}
        for roi in rois:
            if roi.roi_name in unique_roi_names:
                unique_roi_names[roi.roi_name]['count'] += 1
            else:
                unique_roi_names[roi.roi_name] = {
                    'count': 1,
                    'clean_roi_name': roi.clean_roi_name or clean_contour_label(roi.roi_name),
                    'tg263_primary_name': roi.tg263_primary_name,
                    'roi_of_clean_roi_name_match_tg263': roi.roi_of_clean_roi_name_match_tg263,
                    'sample_roi_id': roi.id
                }
        
        # Get TG263 data
        tg263_data = get_tg263_data()
        tg263_available = bool(tg263_data)
        
        if not tg263_available:
            messages.warning(request, 'TG263 service is currently unavailable. Using sample data.')
        
        # Extract just the TG263 primary names for simpler handling in the template
        tg263_primary_names = [item['TG263_Primary_Name'] for item in tg263_data]
        
        # Handle form submission
        if request.method == 'POST':
            updated_count = 0
            
            for roi_name, roi_info in unique_roi_names.items():
                # Use Django's slugify function (hyphens) and accept common underscore variants
                base_slug = slugify(roi_name)
                candidate_keys = [
                    f"user_modified_name_{base_slug}",                                 # e.g., small-bowel
                    f"user_modified_name_{base_slug.replace('-', '_')}",               # e.g., small_bowel
                    f"user_modified_name_{roi_name.lower().replace(' ', '_').replace('-', '_')}",  # resilient fallback
                ]
                
                # Debug logging
                print(f"Available keys: {list(request.POST.keys())}")
                print(f"Looking for any of: {candidate_keys}")
                
                # Pick the first matching key
                found_key = next((k for k in candidate_keys if k in request.POST), None)
                if found_key:
                    new_name = request.POST[found_key].strip()
                    print(f"Found key {found_key} with value: {new_name}")
                    
                    if new_name:
                        # Find matching TG263 data
                        tg263_match = None
                        for item in tg263_data:
                            if item['TG263_Primary_Name'] == new_name:
                                tg263_match = item
                                break
                        
                        # Update all ROIs with this name
                        matching_rois = rois.filter(roi_name=roi_name)
                        modified_rois_by_rtstruct = {}  # Group ROIs by RTSTRUCT for efficient file updates
                        
                        for roi in matching_rois:
                            if tg263_match:
                                # Update with TG263 data
                                roi.tg263_primary_name = tg263_match.get('TG263_Primary_Name', '')
                                roi.tg263_reverse_order_name = tg263_match.get('TG263_Reverse_Order_Name', roi.tg263_primary_name)
                                roi.target_type = tg263_match.get('Target_Type', '')
                                roi.major_category = tg263_match.get('Major_Category', '')
                                roi.minor_category = tg263_match.get('Minor_Category', '')
                                roi.anatomic_group = tg263_match.get('Anatomic_Group', '')
                                roi.fma_id = tg263_match.get('FMAID', '')
                                roi.roi_of_clean_roi_name_match_tg263 = True
                                roi.user_modified_name = tg263_match.get('TG263_Primary_Name', '')
                            else:
                                # Just update the user modified name
                                roi.user_modified_name = new_name
                            
                            roi.save()
                            updated_count += 1
                            
                            # Group ROIs by RTSTRUCT for efficient file updates
                            rtstruct_id = roi.rtstruct_id
                            if rtstruct_id not in modified_rois_by_rtstruct:
                                modified_rois_by_rtstruct[rtstruct_id] = []
                            modified_rois_by_rtstruct[rtstruct_id].append(roi)
                        
                        # Update RTSTRUCT files
                        for rtstruct_id, rois_to_update in modified_rois_by_rtstruct.items():
                            try:
                                rtstruct = get_object_or_404(Rtstruct, id=rtstruct_id)
                                rtstruct_path = rtstruct.rtstruct_dir
                                
                                # Update DICOM file with modified ROIs
                                dicom_updated = update_dicom_roi_names(rtstruct_path, rois_to_update, request, messages)
                                if dicom_updated:
                                    messages.success(request, f'Updated {dicom_updated} ROI names in RTSTRUCT file: {rtstruct_path}')
                            except Exception as e:
                                messages.error(request, f'Error updating RTSTRUCT file: {str(e)}')
            
            if updated_count > 0:
                messages.success(request, f'Successfully updated {updated_count} ROIs.')
            else:
                messages.info(request, 'No changes were made.')
            
            return redirect('app:zip_detail', zip_id=zip_id)
        
        context = {
            'page_title': 'Batch ROI Harmonization',
            'upload_zip': upload_zip,
            'unique_roi_names': unique_roi_names,
            'zip_id': zip_id,
            'tg263_available': tg263_available,
            'tg263_data': json.dumps(tg263_data),
            'tg263_primary_names': json.dumps(tg263_primary_names)
        }
        
        return render(request, 'app/batch_harmonize_rois.html', context)
        
    except Exception as e:
        messages.error(request, f'Error loading batch harmonization: {str(e)}')
        return redirect('app:workspace')

@login_required
def generate_nifti_for_radiomics_rois(request, zip_id):
    """
    For all patients in the given ZIP, convert CT and RTSTRUCT to NIfTI/NRRD.
    Output is saved under media/nifti/{patient_id}_{zip_id}/
    """
    import os
    from django.conf import settings
    from .models import (
        UploadZip, 
        Patient, 
        Study,
        Series, 
        Instance, 
        Rtstruct,
        Roi
    )
    from dicom_to_nrrd import dicom_ct_to_nrrd, rtstruct_to_nrrd, convert_patient_data

    try:
        # Get the upload zip object
        upload_zip = UploadZip.objects.get(id=zip_id)
        
        # Get all patients for this zip
        patients = Patient.objects.filter(uploaded_zip_file_id=zip_id)
        
        success_count = 0
        total_count = 0
        
        for patient in patients:
            print(f"\nPatient ID: {patient.patient_id}")
            
            studies = Study.objects.filter(patient=patient)
            for study in studies:
                ct_series = Series.objects.filter(study=study, modality='CT')
                for series in ct_series:
                    print(f"CT Directory: {series.series_dir}")
                    
                    instances = Instance.objects.filter(series__study=study)
                    rtstructs = Rtstruct.objects.filter(series_instance__in=instances)
                    
                    for rtstruct in rtstructs:
                        print(f"RTSTRUCT Directory: {rtstruct.rtstruct_dir}")
                        
                        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                        output_folder = os.path.join(base_dir, 'media', 'nifti', f"{patient.patient_id}_{zip_id}")
                        os.makedirs(output_folder, exist_ok=True)
                        
                        try:
                            ct_path, roi_info = convert_patient_data(series.series_dir, rtstruct.rtstruct_dir, output_folder)
                            print(f"Generated CT path: {ct_path}")
                            print(f"Generated ROI info: {roi_info}")
                            
                            # Get all ROIs for this RTSTRUCT
                            rois = Roi.objects.filter(rtstruct=rtstruct)
                            print(f"Found {rois.count()} ROIs in database for RTSTRUCT {rtstruct.id}")
                            
                            for roi in rois:
                                total_count += 1
                                print(f"Processing ROI: {roi.roi_name} (number: {roi.roi_number})")
                                print(f"  User modified name: {roi.user_modified_name}")
                                print(f"  Clean ROI name: {roi.clean_roi_name}")
                                print(f"  TG263 match: {roi.roi_of_clean_roi_name_match_tg263}")
                                
                                # Try to match by ROI number first
                                matched_roi_info = None
                                for info in roi_info:
                                    if str(roi.roi_number) == str(info['number']):
                                        matched_roi_info = info
                                        print(f"  Matched by ROI number: {roi.roi_number}")
                                        break
                                
                                # If no match by number, try by original ROI name
                                if not matched_roi_info:
                                    for info in roi_info:
                                        if roi.roi_name == info['name']:
                                            matched_roi_info = info
                                            print(f"  Matched by original ROI name: {roi.roi_name}")
                                            break
                                
                                # If still no match, try by clean ROI name
                                if not matched_roi_info:
                                    for info in roi_info:
                                        if roi.clean_roi_name == info['name']:
                                            matched_roi_info = info
                                            print(f"  Matched by clean ROI name: {roi.clean_roi_name}")
                                            break
                                
                                # If still no match, try by user modified name
                                if not matched_roi_info:
                                    for info in roi_info:
                                        if roi.user_modified_name == info['name']:
                                            matched_roi_info = info
                                            print(f"  Matched by user modified name: {roi.user_modified_name}")
                                            break
                                
                                if matched_roi_info:
                                    roi.ct_nrrd_file_path = ct_path
                                    roi.roi_nrrd_file_path = matched_roi_info['path']
                                    roi.save()
                                    success_count += 1
                                    print(f"Updated paths for ROI {roi.roi_name} (number {roi.roi_number})")
                                    print(f"  CT path: {ct_path}")
                                    print(f"  ROI path: {matched_roi_info['path']}")
                                else:
                                    print(f"No matching ROI info found for ROI {roi.roi_name} (number {roi.roi_number})")
                                    print(f"Available ROI info: {[info['name'] for info in roi_info]}")
                                    
                        except Exception as e:
                            print(f"Error processing patient {patient.patient_id}: {str(e)}")
                            import traceback
                            print(f"Full traceback: {traceback.format_exc()}")
        
        # Always update the flag after processing, regardless of partial success
        upload_zip.radiomics_data_prepared = True
        upload_zip.save()
        
        # Double-check with direct update
        UploadZip.objects.filter(id=zip_id).update(radiomics_data_prepared=True)
        
        if success_count < total_count:
            messages.warning(request, f"Processed {success_count} out of {total_count} ROIs. Some ROIs had issues but data preparation is marked as complete.")
        else:
            messages.success(request, f"Successfully prepared radiomics data for all {success_count} ROIs!")
                        
    except Exception as e:
        messages.error(request, f"Error during NIfTI/NRRD conversion: {str(e)}")
        print(f"Error: {str(e)}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")

    return redirect('app:zip_detail', zip_id=zip_id)

@login_required
def select_rois_for_radiomics(request, zip_id):
    from django.urls import reverse
    if request.method == 'POST':
        selected_roi_names = request.POST.getlist('selected_roi_names[]')
        request.session['selected_roi_names'] = selected_roi_names
        return redirect(reverse('app:selected_rois_paths', args=[zip_id]))

    # Get all ROIs for this zip_id
    from .models import Roi
    rois = Roi.objects.filter(
        rtstruct__series_instance__series__study__patient__uploaded_zip_file_id=zip_id
    )
    
    # Group by ROI name and count frequency
    # Use user_modified_name if available and not empty, otherwise use roi_name
    import os
    unique_roi_names = {}
    for roi in rois:
        # Determine the display name: user_modified_name if exists and not empty, otherwise roi_name
        display_name = roi.user_modified_name if roi.user_modified_name and roi.user_modified_name.strip() else roi.roi_name
        
        if display_name in unique_roi_names:
            unique_roi_names[display_name]['count'] += 1
            # Update NIfTI status if any instance has a saved path present on disk
            if roi.roi_nrrd_file_path and os.path.exists(roi.roi_nrrd_file_path):
                unique_roi_names[display_name]['nifti_converted'] = True
        else:
            unique_roi_names[display_name] = {
                'count': 1,
                'sample_roi_id': roi.id,
                'original_roi_name': roi.roi_name,  # Keep original name for reference
                'has_modified_name': bool(roi.user_modified_name and roi.user_modified_name.strip()),  # Flag to indicate if modified
                'nifti_converted': bool(roi.roi_nrrd_file_path and os.path.exists(roi.roi_nrrd_file_path))
            }
    
    context = {
        'unique_roi_names': unique_roi_names,
        'zip_id': zip_id,
    }
    return render(request, 'app/select_rois_for_radiomics.html', context)

@login_required
def generate_nifti_for_selected_rois(request, zip_id):
    """Convert CT and RTSTRUCT to NIfTI/NRRD but only for selected ROI display names.
    Display name = user_modified_name if present, else roi_name.
    """
    if request.method != 'POST':
        return redirect('app:zip_detail', zip_id=zip_id)

    selected_names = set(request.POST.getlist('selected_roi_names'))
    if not selected_names:
        messages.warning(request, 'No structures selected.')
        return redirect('app:zip_detail', zip_id=zip_id)

    from .models import UploadZip, Patient, Study, Series, Instance, Rtstruct, Roi

    try:
        upload_zip = UploadZip.objects.get(id=zip_id)
        patients = Patient.objects.filter(uploaded_zip_file_id=zip_id)

        success_count = 0
        total_count = 0

        for patient in patients:
            studies = Study.objects.filter(patient=patient)
            for study in studies:
                ct_series = Series.objects.filter(study=study, modality='CT')
                for series in ct_series:
                    instances = Instance.objects.filter(series__study=study)
                    rtstructs = Rtstruct.objects.filter(series_instance__in=instances)

                    for rtstruct in rtstructs:
                        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                        output_folder = os.path.join(base_dir, 'media', 'nifti', f"{patient.patient_id}_{zip_id}")
                        os.makedirs(output_folder, exist_ok=True)

                        # Use the same conversion function as full conversion
                        from dicom_to_nrrd import convert_patient_data
                        try:
                            # Determine which ROI NUMBERS to convert for this RTSTRUCT (more robust than names)
                            rois = Roi.objects.filter(rtstruct=rtstruct)
                            selected_numbers = []
                            for roi in rois:
                                display_name = roi.user_modified_name.strip() if roi.user_modified_name and roi.user_modified_name.strip() else roi.roi_name
                                if display_name in selected_names:
                                    selected_numbers.append(roi.roi_number)

                            # If none selected for this RTSTRUCT, skip
                            if not selected_numbers:
                                continue

                            # Convert only selected ROI numbers
                            ct_path, roi_info = convert_patient_data(
                                series.series_dir,
                                rtstruct.rtstruct_dir,
                                output_folder,
                                roi_numbers=list(set(selected_numbers))
                            )
                            # Map roi_info by multiple keys for matching
                            roi_info_list = list(roi_info)

                            # Update DB paths only for selected display names
                            for roi in rois:
                                display_name = roi.user_modified_name.strip() if roi.user_modified_name and roi.user_modified_name.strip() else roi.roi_name
                                if display_name not in selected_names:
                                    continue

                                total_count += 1

                                matched = None
                                for info in roi_info_list:
                                    if str(roi.roi_number) == str(info.get('number')):
                                        matched = info
                                        break
                                if not matched:
                                    for info in roi_info_list:
                                        if roi.roi_name == info.get('name'):
                                            matched = info
                                            break
                                if not matched and roi.clean_roi_name:
                                    for info in roi_info_list:
                                        if roi.clean_roi_name == info.get('name'):
                                            matched = info
                                            break
                                if not matched and roi.user_modified_name:
                                    for info in roi_info_list:
                                        if roi.user_modified_name == info.get('name'):
                                            matched = info
                                            break

                                if matched:
                                    roi.ct_nrrd_file_path = ct_path
                                    roi.roi_nrrd_file_path = matched.get('path')
                                    roi.save()
                                    success_count += 1
                        except Exception as e:
                            print(f"Selective conversion error for patient {patient.patient_id}: {str(e)}")
                            import traceback
                            print(traceback.format_exc())

        # Do not flip the global prepared flag here; this is a selective conversion step
        if success_count:
            messages.success(request, f"Prepared NIfTI/NRRD for {success_count} selected ROIs.")
        else:
            messages.warning(request, "No selected ROIs were prepared. Check selections and data.")

    except Exception as e:
        messages.error(request, f"Error during selective NIfTI/NRRD conversion: {str(e)}")

    return redirect('app:zip_detail', zip_id=zip_id)

@login_required
def selected_rois_paths(request, zip_id):
    try:
        from .models import Roi, Series, RadiomicFeatures, UploadZip, Patient, RadiomicFeatureMapping, ExtractionSession
        import os
        import SimpleITK as sitk
        import glob
        
        selected_roi_names = request.session.get('selected_roi_names', [])
        
        # Get all ROIs for this zip_id
        rois = Roi.objects.filter(
            rtstruct__series_instance__series__study__patient__uploaded_zip_file_id=zip_id
        ).select_related(
            'rtstruct',
            'rtstruct__series_instance',
            'rtstruct__series_instance__series',
            'rtstruct__series_instance__series__study',
            'rtstruct__series_instance__series__study__patient'
        )
        
        # Filter ROIs based on display names (user_modified_name or roi_name)
        filtered_rois = []
        for roi in rois:
            # Determine the display name: user_modified_name if exists and not empty, otherwise roi_name
            display_name = roi.user_modified_name if roi.user_modified_name and roi.user_modified_name.strip() else roi.roi_name
            
            if display_name in selected_roi_names:
                filtered_rois.append(roi)
        
        # Create a new extraction session for this batch
        extraction_session = ExtractionSession.objects.create()
        
        roi_info_list = []
        feature_data_list = []
        skipped_rois = []  # collect skipped items with reasons
        
        for roi in filtered_rois:
            study = roi.rtstruct.series_instance.series.study
            patient = study.patient
            upload_zip = patient.uploaded_zip_file

            # Use display name for logging and context
            display_name = roi.user_modified_name if roi.user_modified_name and roi.user_modified_name.strip() else roi.roi_name
            print(f"Processing ROI: {display_name} (original: {roi.roi_name})")
            
            # Find the NRRD files for this patient
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            nifti_folder = os.path.join(base_dir, 'media', 'nifti', f"{patient.patient_id}_{zip_id}")
            
            # Look for CT file
            ct_path = os.path.join(nifti_folder, "ct.nrrd")
            if not os.path.exists(ct_path):
                msg = f"CT file does not exist: {ct_path}"
                print(msg)
                skipped_rois.append({"roi": display_name, "patient_id": patient.patient_id, "reason": msg})
                continue
            
            # Look for ROI files in the rois subfolder
            roi_folder = os.path.join(nifti_folder, "rois")
            if not os.path.exists(roi_folder):
                msg = f"ROI folder does not exist: {roi_folder}"
                print(msg)
                skipped_rois.append({"roi": display_name, "patient_id": patient.patient_id, "reason": msg})
                continue
            
            # Find ROI file using multiple strategies
            roi_path = None
            
            # Strategy 1: Try to match by ROI number first
            roi_files = glob.glob(os.path.join(roi_folder, f"roi_{roi.roi_number}_*.nrrd"))
            if roi_files:
                roi_path = roi_files[0]
                print(f"Found ROI file by ROI number {roi.roi_number}: {roi_path}")
            
            # Strategy 2: If no match by ROI number, try to match by original ROI name
            if not roi_path:
                # Get all ROI files in the folder
                all_roi_files = glob.glob(os.path.join(roi_folder, "roi_*.nrrd"))
                print(f"All ROI files in folder: {all_roi_files}")
                
                for roi_file in all_roi_files:
                    filename = os.path.basename(roi_file)
                    # Check if the filename contains the original ROI name
                    if roi.roi_name.lower() in filename.lower():
                        roi_path = roi_file
                        print(f"Found ROI file by original name '{roi.roi_name}': {roi_path}")
                        break
            
            # Strategy 3: If still no match, try to match by clean ROI name
            if not roi_path and roi.clean_roi_name:
                for roi_file in all_roi_files:
                    filename = os.path.basename(roi_file)
                    if roi.clean_roi_name.lower() in filename.lower():
                        roi_path = roi_file
                        print(f"Found ROI file by clean name '{roi.clean_roi_name}': {roi_path}")
                        break
            
            # Strategy 4: If still no match, try to match by user modified name
            if not roi_path and roi.user_modified_name:
                for roi_file in all_roi_files:
                    filename = os.path.basename(roi_file)
                    if roi.user_modified_name.lower() in filename.lower():
                        roi_path = roi_file
                        print(f"Found ROI file by user modified name '{roi.user_modified_name}': {roi_path}")
                        break
            
            # Strategy 5: If still no match, try to find any file that might contain the ROI name
            if not roi_path:
                # Look for any file that might contain the ROI name (case insensitive)
                for roi_file in all_roi_files:
                    filename = os.path.basename(roi_file)
                    # Remove the "roi_" prefix and ".nrrd" suffix for comparison
                    roi_name_in_file = filename.replace("roi_", "").replace(".nrrd", "")
                    
                    # Check if the original ROI name is contained in the filename
                    if roi.roi_name.lower() in roi_name_in_file.lower():
                        roi_path = roi_file
                        print(f"Found ROI file by partial name match '{roi.roi_name}': {roi_path}")
                        break
            
            if not roi_path:
                msg = f"No ROI file found for ROI {roi.roi_name} (#{roi.roi_number}) in {roi_folder}"
                print(msg)
                skipped_rois.append({"roi": display_name, "patient_id": patient.patient_id, "reason": msg})
                continue
            
            print(f"Using ROI file: {roi_path}")
            
            # Validate file sizes
            try:
                ct_size = os.path.getsize(ct_path)
                roi_size = os.path.getsize(roi_path)
                
                if ct_size == 0:
                    msg = f"CT file is empty: {ct_path}"
                    print(msg)
                    skipped_rois.append({"roi": display_name, "patient_id": patient.patient_id, "reason": msg})
                    continue
                    
                if roi_size == 0:
                    msg = f"ROI file is empty: {roi_path}"
                    print(msg)
                    skipped_rois.append({"roi": display_name, "patient_id": patient.patient_id, "reason": msg})
                    continue
                    
                print(f"File sizes - CT: {ct_size} bytes, ROI: {roi_size} bytes")
                
            except OSError as e:
                msg = f"Error checking file sizes: {e}"
                print(msg)
                skipped_rois.append({"roi": display_name, "patient_id": patient.patient_id, "reason": msg})
                continue
            
            # Try to read files with SimpleITK first to validate
            try:
                ct_image = sitk.ReadImage(ct_path)
                roi_mask = sitk.ReadImage(roi_path)
                print(f"Successfully read images with SimpleITK for ROI: {display_name}")
            except Exception as e:
                msg = f"Error reading images with SimpleITK for ROI {display_name}: {e}"
                print(msg)
                skipped_rois.append({"roi": display_name, "patient_id": patient.patient_id, "reason": msg})
                continue
            
            # Now try PyRadiomics extraction (guard against missing package)
            extractor = None
            try:
                from radiomics import featureextractor
                extractor = featureextractor.RadiomicsFeatureExtractor()
                result = extractor.execute(ct_path, roi_path)
                print(f"Successfully extracted features for ROI: {display_name}")
            except Exception as e:
                print(f"Error during PyRadiomics extraction for ROI {display_name}: {e}")
                # If extractor was created, attempt with SimpleITK images; otherwise skip this ROI
                if extractor is not None:
                    try:
                        result = extractor.execute(ct_image, roi_mask)
                        print(f"Successfully extracted features using SimpleITK objects for ROI: {display_name}")
                    except Exception as e2:
                        msg = f"Error with SimpleITK objects for ROI {display_name}: {e2}"
                        print(msg)
                        skipped_rois.append({"roi": display_name, "patient_id": patient.patient_id, "reason": msg})
                        continue
                else:
                    msg = f"PyRadiomics not available; skipping ROI {display_name}"
                    print(msg)
                    skipped_rois.append({"roi": display_name, "patient_id": patient.patient_id, "reason": msg})
                    continue

            # Always create a new RadiomicFeatures record
            radiomic_features = RadiomicFeatures.objects.create(
                roi=roi,
                zip_id=upload_zip,
                patient_id=patient,
                patient_identifier=patient.patient_id,
                roi_name=display_name,  # Use display name instead of original roi_name
                extraction_session=extraction_session
            )

            # Update features directly using PyRadiomics keys
            feature_data = []
            for key, value in result.items():
                # Skip diagnostic features
                if key.startswith('diagnostics_'):
                    continue
                
                try:
                    if hasattr(radiomic_features, key) and value is not None:
                        setattr(radiomic_features, key, float(value))
                        print(f"Updated {key} = {value}")
                        
                        # Get feature mapping if exists
                        feature_mapping = RadiomicFeatureMapping.objects.filter(feature_name=key).first()
                        feature_data.append({
                            'feature_name': key,
                            'value': float(value),
                            'feature_class': feature_mapping.feature_class if feature_mapping else '',
                            'feature': feature_mapping.feature if feature_mapping else '',
                            'description': feature_mapping.description if feature_mapping else ''
                        })
                except (ValueError, AttributeError) as e:
                    print(f"Error setting {key}: {e}")

            # Save the features
            radiomic_features.save()
            print(f"Saved radiomic features for ROI: {display_name} with patient ID: {patient.patient_id}")

            roi_info_list.append({
                'roi': roi,
                'ct_nrrd_file_path': ct_path,
                'roi_nrrd_file_path': roi_path,
                'patient_id': patient.patient_id,
                'patient_name': patient.patient_name,
                'extraction_id': extraction_session.extraction_id,
                'display_name': display_name  # Add display name to context
            })
            
            feature_data_list.append({
                'roi_name': display_name,  # Use display name instead of original roi_name
                'patient_id': patient.patient_id,
                'extraction_id': extraction_session.extraction_id,
                'features': feature_data
            })

        context = {
            'roi_info_list': roi_info_list,
            'feature_data_list': feature_data_list,
            'skipped_rois': skipped_rois,
            'zip_id': zip_id,
            'extraction_id': extraction_session.extraction_id,
            'extraction_date': extraction_session.extraction_date
        }
        return render(request, 'app/selected_rois_paths.html', context)
    except Exception as e:
        import traceback
        logging.error(f"Error in selected_rois_paths for zip {zip_id}: {e}")
        logging.error(traceback.format_exc())
        messages.error(request, f"Error generating radiomics features: {e}")
        return redirect('app:zip_detail', zip_id=zip_id)

@login_required
def zip_extraction_sessions(request, zip_id):
    from .models import ExtractionSession, RadiomicFeatures, UploadZip
    
    # Get the zip file
    upload_zip = UploadZip.objects.get(id=zip_id)
    
    # Get all unique extraction sessions for this zip
    extraction_sessions = ExtractionSession.objects.filter(
        radiomicfeatures__zip_id=zip_id
    ).distinct().order_by('-extraction_date')
    
    # Get count of ROIs for each session
    session_data = []
    for session in extraction_sessions:
        roi_count = RadiomicFeatures.objects.filter(
            zip_id=zip_id,
            extraction_session=session
        ).count()
        
        session_data.append({
            'extraction_id': session.extraction_id,
            'extraction_date': session.extraction_date,
            'roi_count': roi_count
        })
    
    context = {
        'zip_id': zip_id,
        'upload_zip': upload_zip,
        'session_data': session_data
    }
    
    return render(request, 'app/zip_extraction_sessions.html', context)

def generate_distribution_chart(radiomic_features, feature_field, selected_roi=''):
    """Generate a Bokeh histogram chart for radiomic feature distribution"""
    
    # Collect feature values
    values = []
    roi_names = []
    
    for feature_obj in radiomic_features:
        value = getattr(feature_obj, feature_field, None)
        if value is not None:
            roi_name = feature_obj.roi_name or (feature_obj.roi.roi_name if feature_obj.roi else 'Unknown')
            
            # Filter by ROI if specified
            if not selected_roi or selected_roi == 'all' or roi_name == selected_roi:
                values.append(float(value))
                roi_names.append(roi_name)
    
    if not values:
        return None, None, None
    
    # Calculate statistics
    values_array = np.array(values)
    stats = {
        'mean': np.mean(values_array),
        'median': np.median(values_array),
        'std': np.std(values_array),
        'count': len(values_array),
        'min': np.min(values_array),
        'max': np.max(values_array)
    }
    
    # Create histogram
    hist, edges = np.histogram(values, bins=20)
    
    # Create Bokeh figure
    feature_display_name = feature_field.replace('original_', '').replace('_', ' ').title()
    title = f"Distribution of {feature_display_name}"
    if selected_roi and selected_roi != 'all':
        title += f" - {selected_roi}"
    
    p = figure(
        title=title,
        x_axis_label=feature_display_name,
        y_axis_label='Frequency',
        width=800,
        height=400,
        tools='pan,wheel_zoom,box_zoom,reset,save'
    )
    
    # Add histogram bars
    p.quad(top=hist, bottom=0, left=edges[:-1], right=edges[1:],
           fill_color='navy', line_color='white', alpha=0.7)
    
    # Add hover tool
    hover = HoverTool(tooltips=[
        ('Range', '@left - @right'),
        ('Count', '@top')
    ])
    p.add_tools(hover)
    
    # Generate script and div
    script, div = components(p)
    
    return script, div, stats


def detect_outliers_zscore(radiomic_features, threshold=2.0):
    """
    Detect outliers using Z-score analysis for specific shape features.
    Returns a dictionary with outlier information for each ROI and feature.
    """
    import numpy as np
    from scipy import stats
    
    # Define the shape features to analyze with display names
    shape_features = {
        'original_shape_Elongation': 'Elongation',
        'original_shape_LeastAxisLength': 'Least Axis Length', 
        'original_shape_MajorAxisLength': 'Major Axis Length',
        'original_shape_MeshVolume': 'Mesh Volume',
        'original_shape_SurfaceArea': 'Surface Area',
        'original_shape_SurfaceVolumeRatio': 'Surface Volume Ratio'
    }
    
    outlier_results = {}
    
    # Group features by ROI
    roi_groups = {}
    for feature in radiomic_features:
        roi_name = feature.roi_name or (feature.roi.roi_name if feature.roi else 'Unknown')
        if roi_name not in roi_groups:
            roi_groups[roi_name] = []
        roi_groups[roi_name].append(feature)
    
    # Analyze each ROI separately
    for roi_name, roi_features in roi_groups.items():
        outlier_results[roi_name] = {}
        
        for shape_feature, display_name in shape_features.items():
            # Collect values for this feature across all patients in this ROI
            values = []
            patient_data = []
            
            for feature_obj in roi_features:
                value = getattr(feature_obj, shape_feature, None)
                if value is not None:
                    values.append(float(value))
                    patient_id = feature_obj.patient_id.patient_id if feature_obj.patient_id else 'Unknown'
                    patient_data.append({
                        'patient_id': patient_id,
                        'value': float(value),
                        'feature_obj': feature_obj
                    })
            
            if len(values) > 1:  # Need at least 2 values to calculate Z-score
                # Calculate Z-scores
                z_scores = np.abs(stats.zscore(values))
                
                # Find outliers
                outliers = []
                for i, z_score in enumerate(z_scores):
                    if z_score > threshold:
                        outliers.append({
                            'patient_id': patient_data[i]['patient_id'],
                            'value': patient_data[i]['value'],
                            'z_score': float(z_score),
                            'feature_obj': patient_data[i]['feature_obj']
                        })
                
                outlier_results[roi_name][shape_feature] = {
                    'display_name': display_name,
                    'outliers': outliers,
                    'total_patients': len(values),
                    'outlier_count': len(outliers),
                    'mean': float(np.mean(values)),
                    'std': float(np.std(values)),
                    'threshold': threshold
                }
    
    return outlier_results


def detect_multivariate_outliers(radiomic_features, threshold=2.0):
    """
    Detect multivariate outliers using Mahalanobis distance for shape features.
    This considers correlations between features, unlike univariate Z-score.
    """
    import numpy as np
    from scipy.spatial.distance import mahalanobis
    from scipy.stats import chi2
    
    # Define the shape features to analyze
    shape_features = {
        'original_shape_Elongation': 'Elongation',
        'original_shape_LeastAxisLength': 'Least Axis Length', 
        'original_shape_MajorAxisLength': 'Major Axis Length',
        'original_shape_MeshVolume': 'Mesh Volume',
        'original_shape_SurfaceArea': 'Surface Area',
        'original_shape_SurfaceVolumeRatio': 'Surface Volume Ratio'
    }
    
    multivariate_results = {}
    
    # Group features by ROI
    roi_groups = {}
    for feature in radiomic_features:
        roi_name = feature.roi_name or (feature.roi.roi_name if feature.roi else 'Unknown')
        if roi_name not in roi_groups:
            roi_groups[roi_name] = []
        roi_groups[roi_name].append(feature)
    
    # Analyze each ROI separately
    for roi_name, roi_features in roi_groups.items():
        # Collect feature matrix for this ROI
        feature_matrix = []
        patient_data = []
        
        for feature_obj in roi_features:
            feature_values = []
            valid_feature = True
            
            # Get all shape feature values for this patient
            for shape_feature in shape_features.keys():
                value = getattr(feature_obj, shape_feature, None)
                if value is not None:
                    feature_values.append(float(value))
                else:
                    valid_feature = False
                    break
            
            if valid_feature and len(feature_values) == len(shape_features):
                feature_matrix.append(feature_values)
                patient_id = feature_obj.patient_id.patient_id if feature_obj.patient_id else 'Unknown'
                patient_data.append({
                    'patient_id': patient_id,
                    'feature_obj': feature_obj,
                    'values': feature_values
                })
        
        if len(feature_matrix) >= 3:  # Need at least 3 samples for covariance matrix
            feature_matrix = np.array(feature_matrix)
            
            # Calculate mean and covariance matrix
            mean_vector = np.mean(feature_matrix, axis=0)
            cov_matrix = np.cov(feature_matrix.T)
            
            # Calculate Mahalanobis distances
            try:
                cov_inv = np.linalg.inv(cov_matrix)
                outliers = []
                
                for i, (patient_info, feature_values) in enumerate(zip(patient_data, feature_matrix)):
                    # Calculate Mahalanobis distance
                    mahal_dist = mahalanobis(feature_values, mean_vector, cov_inv)
                    
                    # Convert to Z-score equivalent (approximate)
                    # For multivariate normal, squared Mahalanobis distance follows chi-square
                    p_value = 1 - chi2.cdf(mahal_dist**2, df=len(shape_features))
                    z_score_equiv = abs(chi2.ppf(1 - p_value/2, df=1)**0.5)  # Approximate Z-score
                    
                    if z_score_equiv > threshold:
                        outliers.append({
                            'patient_id': patient_info['patient_id'],
                            'mahalanobis_distance': float(mahal_dist),
                            'z_score_equivalent': float(z_score_equiv),
                            'p_value': float(p_value),
                            'feature_values': {shape_features[feat]: val for feat, val in zip(shape_features.keys(), feature_values)},
                            'feature_obj': patient_info['feature_obj']
                        })
                
                multivariate_results[roi_name] = {
                    'outliers': outliers,
                    'total_patients': len(patient_data),
                    'outlier_count': len(outliers),
                    'threshold': threshold,
                    'mean_vector': mean_vector.tolist(),
                    'feature_names': list(shape_features.values())
                }
                
            except np.linalg.LinAlgError:
                # Singular covariance matrix - cannot compute Mahalanobis distance
                multivariate_results[roi_name] = {
                    'outliers': [],
                    'total_patients': len(patient_data),
                    'outlier_count': 0,
                    'threshold': threshold,
                    'error': 'Singular covariance matrix - insufficient variation in features',
                    'feature_names': list(shape_features.values())
                }
    
    return multivariate_results


def generate_hierarchical_clustering(radiomic_features):
    """
    Generate hierarchical clustering visualization of features based on their correlation patterns within each ROI.
    Shows which radiomic features are similar to each other.
    """
    import numpy as np
    from scipy.cluster.hierarchy import dendrogram, linkage
    from scipy.spatial.distance import pdist
    from bokeh.plotting import figure
    from bokeh.models import HoverTool, ColumnDataSource
    from bokeh.layouts import column
    from bokeh.models.annotations import Title
    import pandas as pd
    
    # Get all available radiomic features from the model
    sample_feature = radiomic_features.first()
    if not sample_feature:
        return {}
    
    # Get all numeric field names from the model
    all_features = {}
    for field in sample_feature._meta.fields:
        field_name = field.name
        # Skip non-numeric fields
        if field_name in ['id', 'patient_id', 'roi', 'roi_name', 'created_at', 'updated_at']:
            continue
        
        # Check if field contains numeric data
        try:
            value = getattr(sample_feature, field_name, None)
            if value is not None and isinstance(value, (int, float)):
                # Create a clean display name
                display_name = field_name.replace('original_', '')
                
                # Better cleaning for radiomic feature names
                if display_name.startswith('shape_'):
                    display_name = display_name.replace('shape_', '')
                elif display_name.startswith('firstorder_'):
                    display_name = display_name.replace('firstorder_', '')
                elif display_name.startswith('glcm_'):
                    display_name = display_name.replace('glcm_', '')
                elif display_name.startswith('glrlm_'):
                    display_name = display_name.replace('glrlm_', '')
                elif display_name.startswith('glszm_'):
                    display_name = display_name.replace('glszm_', '')
                elif display_name.startswith('gldm_'):
                    display_name = display_name.replace('gldm_', '')
                elif display_name.startswith('ngtdm_'):
                    display_name = display_name.replace('ngtdm_', '')
                
                # Replace underscores with spaces and title case
                display_name = display_name.replace('_', ' ').title()
                all_features[field_name] = display_name
        except:
            continue
    
    # Limit to most important features if too many (for better visualization)
    if len(all_features) > 50:
        # Prioritize certain feature types
        priority_keywords = ['shape', 'firstorder', 'glcm', 'glrlm', 'glszm']
        prioritized_features = {}
        
        for keyword in priority_keywords:
            for field_name, display_name in all_features.items():
                if keyword in field_name.lower() and len(prioritized_features) < 40:
                    prioritized_features[field_name] = display_name
        
        # If still too few, add remaining features
        if len(prioritized_features) < 30:
            for field_name, display_name in all_features.items():
                if field_name not in prioritized_features and len(prioritized_features) < 40:
                    prioritized_features[field_name] = display_name
        
        all_features = prioritized_features
    
    clustering_results = {}
    
    # Group features by ROI
    roi_groups = {}
    for feature in radiomic_features:
        roi_name = feature.roi_name or (feature.roi.roi_name if feature.roi else 'Unknown')
        if roi_name not in roi_groups:
            roi_groups[roi_name] = []
        roi_groups[roi_name].append(feature)
    
    # Generate clustering for each ROI
    for roi_name, roi_features in roi_groups.items():
        # Collect data matrix for this ROI (patients x features)
        patient_data = []
        patient_labels = []
        
        for feature_obj in roi_features:
            feature_values = []
            valid_patient = True
            
            # Get all feature values for this patient
            for feature_field in all_features.keys():
                value = getattr(feature_obj, feature_field, None)
                if value is not None:
                    feature_values.append(float(value))
                else:
                    valid_patient = False
                    break
            
            if valid_patient and len(feature_values) == len(all_features):
                patient_data.append(feature_values)
                patient_id = feature_obj.patient_id.patient_id if feature_obj.patient_id else 'Unknown'
                patient_labels.append(patient_id)
        
        if len(patient_data) >= 3:  # Need at least 3 patients for meaningful correlation
            patient_data = np.array(patient_data)  # Shape: (n_patients, n_features)
            
            # Transpose to get features x patients for feature clustering
            feature_data = patient_data.T  # Shape: (n_features, n_patients)
            
            # Standardize each feature across patients
            try:
                from sklearn.preprocessing import StandardScaler
                scaler = StandardScaler()
                feature_data_scaled = scaler.fit_transform(feature_data.T).T  # Standardize across patients
            except ImportError:
                # Fallback to manual standardization if sklearn not available
                feature_data_scaled = (feature_data - np.mean(feature_data, axis=1, keepdims=True)) / np.std(feature_data, axis=1, keepdims=True)
            
            # Perform hierarchical clustering on features
            try:
                # Calculate correlation-based distance matrix between features
                # Use 1 - correlation as distance metric
                correlation_matrix = np.corrcoef(feature_data_scaled)
                
                # Convert correlation to distance (1 - |correlation|)
                distance_matrix = 1 - np.abs(correlation_matrix)
                
                # Convert to condensed distance matrix for linkage
                distances = pdist(distance_matrix, metric='euclidean')
                
                # Perform linkage (average method works well for correlation-based clustering)
                linkage_matrix = linkage(distances, method='average')
                
                # Create feature labels for dendrogram
                feature_labels = list(all_features.values())
                
                # Generate dendrogram data
                dend = dendrogram(linkage_matrix, labels=feature_labels, no_plot=True)
                
                # Create Bokeh visualization with improved styling
                # Adjust width based on number of features
                plot_width = max(1000, min(1600, len(all_features) * 25))
                
                p = figure(
                    width=plot_width, 
                    height=600,
                    title=f"Feature Clustering - {roi_name} ({len(all_features)} features)",
                    x_axis_label="Radiomic Features",
                    y_axis_label="Correlation Distance",
                    tools="pan,wheel_zoom,box_zoom,reset,save",
                    toolbar_location="above",
                    background_fill_color="white",
                    border_fill_color="white"
                )
                
                # Extract dendrogram coordinates
                icoord = np.array(dend['icoord'])
                dcoord = np.array(dend['dcoord'])
                
                # Color scheme for different cluster levels
                max_height = np.max(dcoord)
                
                # Plot dendrogram lines with gradient colors
                for i in range(len(icoord)):
                    x_coords = icoord[i]
                    y_coords = dcoord[i]
                    
                    # Color based on height (distance)
                    avg_height = np.mean(y_coords)
                    color_intensity = avg_height / max_height
                    
                    # Use a color gradient from blue (low) to red (high)
                    if color_intensity < 0.3:
                        line_color = '#2E86AB'  # Dark blue
                        line_width = 3
                    elif color_intensity < 0.6:
                        line_color = '#A23B72'  # Purple
                        line_width = 2.5
                    else:
                        line_color = '#F18F01'  # Orange
                        line_width = 2
                    
                    # Draw the dendrogram segments
                    p.line([x_coords[0], x_coords[1]], [y_coords[0], y_coords[1]], 
                          line_width=line_width, line_color=line_color, alpha=0.8)
                    p.line([x_coords[1], x_coords[2]], [y_coords[1], y_coords[2]], 
                          line_width=line_width, line_color=line_color, alpha=0.8)
                    p.line([x_coords[2], x_coords[3]], [y_coords[2], y_coords[3]], 
                          line_width=line_width, line_color=line_color, alpha=0.8)
                
                # Add feature labels at the bottom with hover
                leaf_positions = []
                leaf_labels = []
                shortened_labels = []
                feature_colors = []
                
                # Define color scheme for different feature types
                feature_type_colors = {
                    'shape': '#E74C3C',      # Red
                    'firstorder': '#3498DB',  # Blue  
                    'glcm': '#2ECC71',       # Green
                    'glrlm': '#F39C12',      # Orange
                    'glszm': '#9B59B6',      # Purple
                    'gldm': '#1ABC9C',       # Teal
                    'ngtdm': '#E67E22',      # Dark Orange
                    'other': '#34495E'       # Dark Gray
                }
                
                # Get leaf positions from dendrogram
                for i, label in enumerate(dend['ivl']):
                    x_pos = (i + 1) * 10  # Dendrogram spacing
                    leaf_positions.append(x_pos)
                    leaf_labels.append(label)
                    
                    # Create shortened labels for display
                    if len(label) > 15:
                        short_label = label[:12] + "..."
                    else:
                        short_label = label
                    shortened_labels.append(short_label)
                    
                    # Determine feature type and color
                    original_field_name = None
                    for field_name, display_name in all_features.items():
                        if display_name == label:
                            original_field_name = field_name
                            break
                    
                    if original_field_name:
                        if 'shape_' in original_field_name:
                            feature_colors.append(feature_type_colors['shape'])
                        elif 'firstorder_' in original_field_name:
                            feature_colors.append(feature_type_colors['firstorder'])
                        elif 'glcm_' in original_field_name:
                            feature_colors.append(feature_type_colors['glcm'])
                        elif 'glrlm_' in original_field_name:
                            feature_colors.append(feature_type_colors['glrlm'])
                        elif 'glszm_' in original_field_name:
                            feature_colors.append(feature_type_colors['glszm'])
                        elif 'gldm_' in original_field_name:
                            feature_colors.append(feature_type_colors['gldm'])
                        elif 'ngtdm_' in original_field_name:
                            feature_colors.append(feature_type_colors['ngtdm'])
                        else:
                            feature_colors.append(feature_type_colors['other'])
                    else:
                        feature_colors.append(feature_type_colors['other'])
                
                # Calculate correlation values for hover info
                feature_correlations = []
                for label in leaf_labels:
                    if label in all_features.values():
                        # Find the feature index
                        feature_idx = list(all_features.values()).index(label)
                        # Get average correlation with other features
                        avg_corr = np.mean(np.abs(correlation_matrix[feature_idx]))
                        feature_correlations.append(f"{avg_corr:.3f}")
                    else:
                        feature_correlations.append("N/A")
                
                # Create hover data source
                hover_source = ColumnDataSource(data=dict(
                    x=leaf_positions,
                    y=[0] * len(leaf_labels),
                    feature_name=leaf_labels,
                    short_name=shortened_labels,
                    avg_correlation=feature_correlations,
                    feature_color=feature_colors,
                    cluster_info=[f"Feature: {label}" for label in leaf_labels]
                ))
                
                # Add hover tool with better formatting
                hover = HoverTool(
                    tooltips=[
                        ("Feature", "@feature_name"),
                        ("Avg Correlation", "@avg_correlation"),
                        ("Position", "@x"),
                        ("Type", "@cluster_info")
                    ],
                    renderers=[]
                )
                p.add_tools(hover)
                
                # Add visible markers for hover detection with feature-type colors
                circles = p.circle('x', 'y', size=10, source=hover_source, 
                                 alpha=0.8, color='feature_color', line_color='white', line_width=2)
                hover.renderers = [circles]
                
                # Customize x-axis with shortened feature labels
                p.xaxis.ticker = leaf_positions
                p.xaxis.major_label_overrides = {pos: label for pos, label in zip(leaf_positions, shortened_labels)}
                p.xaxis.major_label_orientation = 90  # Changed back to 90 degrees (vertical)
                p.xaxis.major_label_text_font_size = "9pt"  # Back to 9pt for vertical text
                p.xaxis.major_label_text_color = "#2C3E50"  # Make labels visible
                
                # Don't hide the default labels - they will show properly now
                # p.xaxis.major_label_text_alpha = 0  # Commented out to show labels
                
                # Add legend for feature types
                from bokeh.models import Legend, LegendItem
                from bokeh.plotting import figure
                
                # Create legend items for each feature type present in the data
                legend_items = []
                feature_types_present = set()
                
                for pos, label, color in zip(leaf_positions, shortened_labels, feature_colors):
                    # Determine feature type from color
                    for ftype, fcolor in feature_type_colors.items():
                        if color == fcolor and ftype not in feature_types_present:
                            feature_types_present.add(ftype)
                            
                            # Create a small invisible circle for legend
                            legend_circle = p.circle([0], [0], size=8, color=color, alpha=0, 
                                                   line_color='white', line_width=1)
                            
                            # Map feature type to display name
                            type_display_names = {
                                'shape': 'Shape',
                                'firstorder': 'First-order Statistics', 
                                'glcm': 'GLCM (Texture)',
                                'glrlm': 'GLRLM (Run-length)',
                                'glszm': 'GLSZM (Size-zone)',
                                'gldm': 'GLDM (Dependence)',
                                'ngtdm': 'NGTDM (Tone)',
                                'other': 'Other'
                            }
                            
                            legend_items.append(LegendItem(
                                label=type_display_names.get(ftype, ftype.title()),
                                renderers=[legend_circle]
                            ))
                
                # Add legend to plot
                if legend_items:
                    legend = Legend(items=legend_items, location="top_right", 
                                  background_fill_alpha=0.8, border_line_color="gray")
                    p.add_layout(legend, 'right')
                
                # Add grid for better readability
                p.grid.grid_line_alpha = 0.3
                p.grid.grid_line_color = "gray"
                
                # Enhanced plot styling
                p.title.text_font_size = "16pt"
                p.title.text_font_style = "bold"
                p.title.align = "center"
                p.title.text_color = "#2C3E50"
                
                p.xaxis.axis_label_text_font_size = "12pt"
                p.xaxis.axis_label_text_font_style = "bold"
                p.xaxis.axis_label_text_color = "#34495E"
                p.xaxis.major_label_text_color = "#2C3E50"
                
                p.yaxis.axis_label_text_font_size = "12pt"
                p.yaxis.axis_label_text_font_style = "bold"
                p.yaxis.axis_label_text_color = "#34495E"
                p.yaxis.major_label_text_color = "#2C3E50"
                
                # Add subtle border
                p.outline_line_color = "#BDC3C7"
                p.outline_line_width = 2
                
                # Adjust margins for better label visibility
                p.min_border_bottom = 100
                p.min_border_left = 80
                p.min_border_right = 50
                p.min_border_top = 50
                
                clustering_results[roi_name] = {
                    'plot': p,
                    'patient_count': len(patient_labels),
                    'feature_names': list(all_features.values()),
                    'feature_count': len(all_features),
                    'linkage_matrix': linkage_matrix.tolist(),
                    'correlation_matrix': correlation_matrix.tolist()
                }
                
            except Exception as e:
                clustering_results[roi_name] = {
                    'error': f"Feature clustering failed: {str(e)}",
                    'patient_count': len(patient_labels),
                    'feature_names': list(all_features.values())
                }
        else:
            clustering_results[roi_name] = {
                'error': f"Insufficient data: only {len(patient_data)} patients (minimum 3 required)",
                'patient_count': len(patient_data) if patient_data else 0,
                'feature_names': list(all_features.values())
            }
    
    return clustering_results


@login_required
def show_results(request, zip_id, extraction_id):
    from .models import ExtractionSession, RadiomicFeatures, UploadZip, Roi, Patient
    import inspect
    import json
    
    # Get the zip file and extraction session
    upload_zip = UploadZip.objects.get(id=zip_id)
    extraction_session = ExtractionSession.objects.get(extraction_id=extraction_id)
    
    # Get all radiomic features for this extraction session
    radiomic_features = RadiomicFeatures.objects.filter(
        zip_id=zip_id,
        extraction_session=extraction_session
    ).select_related('roi', 'roi__rtstruct', 'roi__rtstruct__series_instance__series__study__patient', 'patient_id')
    
    # Get all feature field names from the RadiomicFeatures model
    feature_fields = [field.name for field in RadiomicFeatures._meta.get_fields() 
                     if field.name.startswith('original_') and hasattr(field, 'null')]
    
    # Collect ROI names and feature options for dropdowns
    roi_names = set()
    feature_options = {}
    
    for feature_obj in radiomic_features:
        roi_name = feature_obj.roi_name or (feature_obj.roi.roi_name if feature_obj.roi else 'Unknown')
        roi_names.add(roi_name)
    
    # Prepare feature options grouped by category
    for field_name in feature_fields:
        if field_name.startswith('original_') and '_' in field_name:
            parts = field_name.split('_')
            if len(parts) >= 2:
                category = parts[1]
                display_name = field_name.replace('original_', '').replace('_', ' ').title()
                
                if category not in feature_options:
                    feature_options[category] = []
                feature_options[category].append({
                    'field_name': field_name,
                    'display_name': display_name
                })
    
    # Generate chart if requested
    chart_script = None
    chart_div = None
    chart_stats = None
    
    selected_roi = request.GET.get('roi', '')
    selected_feature = request.GET.get('feature', '')
    
    if selected_feature and selected_feature in [field.name for field in RadiomicFeatures._meta.get_fields()]:
        chart_script, chart_div, chart_stats = generate_distribution_chart(
            radiomic_features, selected_feature, selected_roi
        )
    
    # Generate outlier detection results
    outlier_results = detect_outliers_zscore(radiomic_features, threshold=2.0)
    
    # Generate multivariate outlier detection results
    multivariate_outliers = detect_multivariate_outliers(radiomic_features, threshold=2.0)
    
    # Generate hierarchical clustering results
    clustering_results = generate_hierarchical_clustering(radiomic_features)
    
    # Prepare table view data for outliers
    outlier_table_data = []
    for roi_name, roi_data in outlier_results.items():
        # Group outliers by patient for this ROI
        patient_outliers = {}
        
        for feature_name, feature_data in roi_data.items():
            for outlier in feature_data['outliers']:
                patient_id = outlier['patient_id']
                if patient_id not in patient_outliers:
                    patient_outliers[patient_id] = []
                patient_outliers[patient_id].append({
                    'feature_name': feature_data['display_name'],
                    'value': outlier['value'],
                    'z_score': outlier['z_score']
                })
        
        # Create table rows
        for patient_id, outlier_features in patient_outliers.items():
            outlier_table_data.append({
                'roi_name': roi_name,
                'patient_id': patient_id,
                'outlier_features': outlier_features,
                'feature_names_str': ', '.join([f['feature_name'] for f in outlier_features]),
                'outlier_count': len(outlier_features)
            })
    
    # Prepare outlier combination analysis
    outlier_combinations = {}
    for roi_name, roi_data in outlier_results.items():
        # Collect all patients with outliers in this ROI
        patient_outlier_features = {}
        
        for feature_name, feature_data in roi_data.items():
            for outlier in feature_data['outliers']:
                patient_id = outlier['patient_id']
                if patient_id not in patient_outlier_features:
                    patient_outlier_features[patient_id] = []
                patient_outlier_features[patient_id].append(feature_data['display_name'])
        
        # Group by feature combinations
        combination_groups = {}
        for patient_id, features in patient_outlier_features.items():
            # Sort features to ensure consistent combination keys
            feature_combination = tuple(sorted(features))
            combination_str = ', '.join(feature_combination)
            
            if combination_str not in combination_groups:
                combination_groups[combination_str] = {
                    'features': list(feature_combination),
                    'patients': [],
                    'count': 0
                }
            
            combination_groups[combination_str]['patients'].append(patient_id)
            combination_groups[combination_str]['count'] += 1
        
        # Sort combinations by frequency (most common first)
        sorted_combinations = sorted(
            combination_groups.items(),
            key=lambda x: x[1]['count'],
            reverse=True
        )
        
        outlier_combinations[roi_name] = sorted_combinations
    
    # Prepare clustering Bokeh components
    clustering_components = {}
    for roi_name, cluster_data in clustering_results.items():
        if 'plot' in cluster_data:
            script, div = components(cluster_data['plot'])
            clustering_components[roi_name] = {
                'script': script,
                'div': div,
                'patient_count': cluster_data['patient_count'],
                'feature_names': cluster_data['feature_names']
            }
        else:
            clustering_components[roi_name] = {
                'error': cluster_data.get('error', 'Unknown error'),
                'patient_count': cluster_data.get('patient_count', 0),
                'feature_names': cluster_data.get('feature_names', [])
            }
    
    context = {
        'zip_id': zip_id,
        'extraction_id': extraction_id,
        'upload_zip': upload_zip,
        'extraction_date': extraction_session.extraction_date,
        'roi_count': len(roi_names),
        'roi_names': sorted(list(roi_names)),
        'feature_options': feature_options,
        'total_feature_fields': len(feature_fields),
        'selected_roi': selected_roi,
        'selected_feature': selected_feature,
        'chart_script': chart_script,
        'chart_div': chart_div,
        'chart_stats': chart_stats,
        'outlier_results': outlier_results,
        'outlier_table_data': outlier_table_data,
        'outlier_combinations': outlier_combinations,
        'multivariate_outliers': multivariate_outliers,
        'clustering_components': clustering_components,
        'bokeh_css': CDN.render_css(),
        'bokeh_js': CDN.render_js(),
    }
    
    return render(request, 'app/show_results.html', context)

@login_required
def export_outliers(request, zip_id):
    """Export outlier detection results to CSV or PDF"""
    upload_zip = get_object_or_404(UploadZip, id=zip_id, uploaded_by=request.user)
    format = request.GET.get('format', 'csv')
    
    # Get all features for this zip file
    features = RadiomicFeatures.objects.filter(
        zip_id=upload_zip
    ).select_related('roi')
    
    if not features.exists():
        messages.error(request, "No radiomic features found for this upload.")
        return redirect('app:zip_detail', zip_id=zip_id)
    
    # Generate outlier results
    outlier_results = detect_outliers_zscore(features)
    
    # Prepare table data with better error handling
    table_data = []
    if outlier_results:  # Check if we have any results
        for roi_name, roi_data in outlier_results.items():
            if not roi_data:  # Skip empty ROI data
                continue
                
            for feature_name, feature_data in roi_data.items():
                if not feature_data.get('outliers'):  # Skip features with no outliers
                    continue
                    
                for outlier in feature_data['outliers']:
                    try:
                        table_data.append({
                            'roi_name': roi_name or 'N/A',
                            'feature_name': feature_data.get('display_name', feature_name) or 'N/A',
                            'patient_id': str(outlier.get('patient_id', 'N/A')),
                            'value': float(outlier.get('value', 0)),
                            'z_score': float(outlier.get('z_score', 0)),
                            'mean': float(feature_data.get('mean', 0)),
                            'std': float(feature_data.get('std', 0)),
                            'threshold': float(feature_data.get('threshold', 0))
                        })
                    except (TypeError, ValueError) as e:
                        print(f"Error processing outlier data: {e}")
                        continue
    
    if format == 'csv':
        # Create CSV response
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="outliers_export_{upload_zip.id}.csv"'
        
        writer = csv.writer(response)
        # Write header
        writer.writerow([
            'ROI Name', 'Feature Name', 'Patient ID', 'Value', 
            'Z-Score', 'Population Mean', 'Population Std Dev', 'Threshold'
        ])
        
        # Write data
        for row in table_data:
            writer.writerow([
                row['roi_name'],
                row['feature_name'],
                row['patient_id'],
                f"{row['value']:.4f}",
                f"{row['z_score']:.2f}",
                f"{row['mean']:.4f}",
                f"{row['std']:.4f}",
                f"{row['threshold']:.1f}"
            ])
            
        return response
        
    elif format == 'pdf':
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib import colors
            from io import BytesIO
            import os
            
            buffer = BytesIO()
            doc = SimpleDocTemplate(
                buffer, 
                pagesize=letter, 
                rightMargin=30, 
                leftMargin=30,
                topMargin=30, 
                bottomMargin=30
            )
            
            elements = []
            styles = getSampleStyleSheet()
            
            # Title
            title_style = ParagraphStyle(
                'Title',
                parent=styles['Heading1'],
                fontSize=16,
                spaceAfter=20,
                alignment=1
            )
            elements.append(Paragraph(f"Outlier Detection Results - {os.path.basename(upload_zip.zip_file.name) or 'Untitled'}", title_style))
            
            # Details
            details_style = ParagraphStyle(
                'Details',
                parent=styles['Normal'],
                fontSize=10,
                spaceAfter=20
            )
            
            elements.append(Paragraph(f"<b>Export Date:</b> {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}", details_style))
            elements.append(Paragraph(f"<b>Total Outliers Found:</b> {len(table_data)}", details_style))
            elements.append(Spacer(1, 20))
            
            if table_data:
                # Prepare table data with proper formatting
                data = [
                    ['ROI', 'Feature', 'Patient ID', 'Value', 'Z-Score', 'Mean', 'Std Dev']
                ]
                
                for row in table_data:
                    data.append([
                        row['roi_name'][:20] + ('...' if len(row['roi_name']) > 20 else ''),  # Truncate long ROI names
                        row['feature_name'][:20] + ('...' if len(row['feature_name']) > 20 else ''),  # Truncate long feature names
                        row['patient_id'],
                        f"{row['value']:.4f}",
                        f"{row['z_score']:.2f}",
                        f"{row['mean']:.4f}",
                        f"{row['std']:.4f}"
                    ])
                
                # Create and style the table
                table = Table(data, repeatRows=1, colWidths=[80, 80, 60, 60, 50, 60, 50])
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4B5563')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 8),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                    ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
                    ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 1), (-1, -1), 7),
                    ('ALIGN', (3, 1), (6, -1), 'RIGHT'),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
                    ('BOX', (0, 0), (-1, -1), 1, colors.black),
                    ('ROWBREAK', (0, 0), (-1, -1), 1, 1, 1, None, None, 1),
                ]))
                
                elements.append(table)
            else:
                elements.append(Paragraph("No outliers were detected in the data.", styles['Normal']))
            
            # Build the PDF
            doc.build(elements)
            
            # Prepare the response
            buffer.seek(0)
            response = HttpResponse(buffer, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="outliers_export_{upload_zip.id}.pdf"'
            return response
            
        except Exception as e:
            print(f"Error generating PDF: {str(e)}")
            messages.error(request, f"Error generating PDF: {str(e)}")
            return redirect('app:zip_detail', zip_id=zip_id)
    
    # Default redirect if format is not recognized
    return redirect('app:zip_detail', zip_id=zip_id)

@login_required
@login_required
@login_required
def regenerate_nrrd_with_harmonized_names(request, zip_id):
    """
    Regenerate NRRD files with harmonized ROI names.
    This is a placeholder function - implementation depends on your NRRD generation logic.
    """
    upload_zip = get_object_or_404(UploadZip, id=zip_id)
    
    try:
        # TODO: Implement NRRD regeneration logic here
        # This is a placeholder - you'll need to implement the actual NRRD regeneration
        # using your preferred method (e.g., SimpleITK, pydicom, etc.)
        
        messages.success(request, "NRRD files regenerated successfully with harmonized ROI names.")
    except Exception as e:
        messages.error(request, f"Error regenerating NRRD files: {str(e)}")
    
    return redirect('app:zip_detail', zip_id=zip_id)


from .models import RadiomicFeatures, Roi, Patient

@login_required
def user_logout(request):
    """Log out the current user and redirect to login page."""
    logout(request)
    return redirect('login')  # Redirect to Django's built-in login view


def extraction_session_details(request, zip_id, extraction_id):
    """View details of a specific extraction session"""
    upload_zip = get_object_or_404(UploadZip, id=zip_id)
    extraction_session = get_object_or_404(ExtractionSession, extraction_id=extraction_id)
    
    # Get all radiomic features for this extraction session
    radiomic_features = RadiomicFeatures.objects.filter(
        zip_id=zip_id,
        extraction_session=extraction_session
    ).select_related('roi', 'patient_id')
    
    # Prepare feature data for the template
    feature_data_list = []
    for feature in radiomic_features:
        # Get all feature fields that start with 'original_'
        feature_fields = [field.name for field in RadiomicFeatures._meta.get_fields() 
                         if field.name.startswith('original_') and hasattr(field, 'null')]
        
        # Get feature values for this ROI
        features = []
        for field in feature_fields:
            value = getattr(feature, field, None)
            if value is not None:
                # Get feature mapping if exists
                feature_mapping = None
                if hasattr(feature, 'get_feature_mapping'):
                    feature_mapping = feature.get_feature_mapping(field)
                
                features.append({
                    'feature_name': field,
                    'value': value,
                    'feature_class': getattr(feature_mapping, 'feature_class', '') if feature_mapping else '',
                    'feature': getattr(feature_mapping, 'feature', '') if feature_mapping else '',
                    'description': getattr(feature_mapping, 'description', '') if feature_mapping else ''
                })
        
        feature_data_list.append({
            'patient_id': feature.patient_identifier or (feature.patient_id.patient_id if feature.patient_id else 'N/A'),
            'roi_name': feature.roi_name or (feature.roi.roi_name if feature.roi else 'N/A'),
            'features': features
        })
    
    # Get basic extraction session details
    context = {
        'zip': upload_zip,
        'zip_id': zip_id,
        'extraction_session': extraction_session,
        'extraction_id': extraction_id,
        'extraction_date': extraction_session.extraction_date,
        'feature_data_list': feature_data_list,
        'title': f'Extraction Session {extraction_id}'
    }
    
    return render(request, 'app/extraction_session_details.html', context)

@login_required
def export_multivariate_outliers(request, zip_id, extraction_id):
    """Export multivariate outlier detection results to CSV or PDF"""
    format = request.GET.get('format', 'csv').lower()

    if format not in ['csv', 'pdf']:
        messages.error(request, "Invalid export format. Please use 'csv' or 'pdf'.")
        return redirect('app:show_results', zip_id=zip_id, extraction_id=extraction_id)

    upload_zip = get_object_or_404(UploadZip, id=zip_id)
    extraction_session = get_object_or_404(ExtractionSession, extraction_id=extraction_id)

    features = RadiomicFeatures.objects.filter(
        zip_id=zip_id,
        extraction_session=extraction_session
    ).select_related('roi')

    if not features.exists():
        messages.error(request, "No radiomic features found for this upload.")
        return redirect('app:show_results', zip_id=zip_id, extraction_id=extraction_id)
    
    # Generate multivariate outlier results
    multivariate_outliers = detect_multivariate_outliers(features)
    
    # Prepare table data with better error handling
    table_data = []
    if multivariate_outliers:  # Check if we have any results
        for roi_name, roi_data in multivariate_outliers.items():
            if not roi_data or 'outliers' not in roi_data:  # Skip invalid ROI data
                continue
                
            for outlier in roi_data.get('outliers', []):
                try:
                    table_data.append({
                        'roi_name': roi_name or 'N/A',
                        'patient_id': str(outlier.get('patient_id', 'Unknown')),
                        'distance': float(outlier.get('mahalanobis_distance', 0)),
                        'p_value': float(outlier.get('p_value', 0)),
                        'threshold': float(roi_data.get('threshold', 2.0)),
                        'z_score_equivalent': float(outlier.get('z_score_equivalent', 0))
                    })
                except (TypeError, ValueError) as e:
                    print(f"Error processing multivariate outlier data: {e}")
                    continue
    
    if format == 'csv':
        # Create CSV response
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="multivariate_outliers_export_{upload_zip.id}.csv"'
        
        writer = csv.writer(response)
        # Write header
        writer.writerow([
            'ROI Name', 'Patient ID', 'Mahalanobis Distance', 'Z-Score Equivalent', 'P-Value', 'Threshold'
        ])
        
        # Write data
        for row in table_data:
            writer.writerow([
                row['roi_name'],
                row['patient_id'],
                f"{row['distance']:.4f}",
                f"{row['z_score_equivalent']:.4f}",
                f"{row['p_value']:.4e}",  # Scientific notation for p-values
                f"{row['threshold']:.2f}"
            ])
            
        return response
        
    elif format == 'pdf':
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib import colors
            from io import BytesIO
            import os
            
            buffer = BytesIO()
            doc = SimpleDocTemplate(
                buffer, 
                pagesize=letter, 
                rightMargin=30, 
                leftMargin=30,
                topMargin=30, 
                bottomMargin=30
            )
            
            elements = []
            styles = getSampleStyleSheet()
            
            # Title
            title_style = ParagraphStyle(
                'Title',
                parent=styles['Heading1'],
                fontSize=16,
                spaceAfter=20,
                alignment=1
            )
            elements.append(Paragraph(f"Multivariate Outlier Detection Results - {os.path.basename(upload_zip.zip_file.name) or 'Untitled'}", title_style))
            
            # Details
            details_style = ParagraphStyle(
                'Details',
                parent=styles['Normal'],
                fontSize=10,
                spaceAfter=20
            )
            
            elements.append(Paragraph(f"<b>Export Date:</b> {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}", details_style))
            elements.append(Paragraph(f"<b>Total Outliers Found:</b> {len(table_data)}", details_style))
            elements.append(Spacer(1, 20))
            
            if table_data:
                # Prepare table data with proper formatting
                data = [
                    ['ROI', 'Patient ID', 'Distance', 'P-Value', 'Threshold']
                ]
                
                for row in table_data:
                    data.append([
                        row['roi_name'][:20] + ('...' if len(row['roi_name']) > 20 else ''),  # Truncate long ROI names
                        row['patient_id'],
                        f"{row['distance']:.4f}",
                        f"{row['p_value']:.4f}",
                        f"{row['threshold']:.4f}"
                    ])
                
                # Create and style the table
                table = Table(data, repeatRows=1, colWidths=[80, 60, 60, 60, 50])
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4B5563')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 8),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                    ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
                    ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 1), (-1, -1), 7),
                    ('ALIGN', (2, 1), (4, -1), 'RIGHT'),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
                    ('BOX', (0, 0), (-1, -1), 1, colors.black),
                    ('ROWBREAK', (0, 0), (-1, -1), 1, 1, 1, None, None, 1),
                ]))
                
                elements.append(table)
            else:
                elements.append(Paragraph("No multivariate outliers were detected in the data.", styles['Normal']))
            
            # Build the PDF
            doc.build(elements)
            
            # Prepare the response
            buffer.seek(0)
            response = HttpResponse(buffer, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="multivariate_outliers_export_{upload_zip.id}.pdf"'
            return response
            
        except Exception as e:
            print(f"Error generating PDF: {str(e)}")
            messages.error(request, f"Error generating PDF: {str(e)}")
            return redirect('app:zip_detail', zip_id=zip_id)
    
    # Default redirect if format is not recognized
    return redirect('app:zip_detail', zip_id=zip_id)
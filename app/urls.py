from django.urls import path
from . import views

app_name = 'app'

urlpatterns = [
    path('', views.dashboard_home, name='home'),
    path('workspace/', views.workspace, name='workspace'),
    path('workspace/create-project/', views.create_project, name='create_project'),
    path('project/<int:project_id>/', views.project_detail, name='project_detail'),
    path('project/<int:project_id>/upload-zip/', views.upload_zip, name='upload_zip'),
    path('zip/<int:zip_id>/', views.zip_detail, name='zip_detail'),
    path('zip/<int:zip_id>/extract/', views.extract_zip, name='extract_zip'),
    path('zip/<int:zip_id>/patient-details/', views.patient_details, name='patient_details'),
    path('get_roi_data/<int:rtstruct_id>/', views.get_roi_data, name='get_roi_data'),
    path('harmonize_rtstruct/<int:rtstruct_id>/form/', views.harmonize_rtstruct_form, name='harmonize_rtstruct_form'),
    path('harmonize_rtstruct/<int:rtstruct_id>/', views.harmonize_rtstruct, name='harmonize_rtstruct'),
    path('project/<int:project_id>/edit/', views.edit_project, name='edit_project'),
    path('project/<int:project_id>/delete/', views.delete_project, name='delete_project'),
    path('zip/<int:zip_id>/delete/', views.delete_zip, name='delete_zip'),
    path('settings/', views.settings, name='settings'),
    path('analytics/', views.analytics, name='analytics'),
    path('zip/<int:zip_id>/batch-harmonize/', views.batch_harmonize_rois, name='batch_harmonize_rois'),
    # path('zip/<int:zip_id>/extract-radiomics/', views.extract_radiomics, name='extract_radiomics'),
    # path('zip/<int:zip_id>/radiomics-results/', views.radiomics_results, name='radiomics_results'),
    path('zip/<int:zip_id>/select-rois/', views.select_rois_for_radiomics, name='select_rois_for_radiomics'),
    path('zip/<int:zip_id>/selected-rois-paths/', views.selected_rois_paths, name='selected_rois_paths'),
    path('zip/<int:zip_id>/nifti_convert/', views.generate_nifti_for_radiomics_rois, name='generate_nifti_for_radiomics_rois'),
    path('zip/<int:zip_id>/nifti_convert_selected/', views.generate_nifti_for_selected_rois, name='generate_nifti_for_selected_rois'),
    path('zip/<int:zip_id>/extraction-sessions/', views.zip_extraction_sessions, name='zip_extraction_sessions'),
    path('logout/', views.user_logout, name='logout'),
    path('zip/<int:zip_id>/extraction/<int:extraction_id>/', views.extraction_session_details, name='extraction_session_details'),
    path('zip/<int:zip_id>/extraction/<int:extraction_id>/results/', views.show_results, name='show_results'),
    path('zip/<int:zip_id>/export-outliers/', views.export_outliers, name='export_outliers'),
    path('zip/<int:zip_id>/extraction/<int:extraction_id>/export-multivariate-outliers/', views.export_multivariate_outliers, name='export_multivariate_outliers'),
    path('zip/<int:zip_id>/regenerate-nrrd/', views.regenerate_nrrd_with_harmonized_names, name='regenerate_nrrd_with_harmonized_names'),
]

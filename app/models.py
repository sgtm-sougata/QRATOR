from django.db import models
from django.contrib.auth.models import User
from datetime import datetime

# Project
class Project(models.Model):
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    
    def __str__(self):
        return self.name
    

# Upload Zip File
class UploadZip(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    zip_file = models.FileField(upload_to='zip_files/')
    name = models.CharField(max_length=50)
    version = models.IntegerField()
    description = models.TextField(max_length=255)
    zip_file_size = models.BigIntegerField()
    zip_extracted = models.BooleanField(default=False)
    extracted_path = models.CharField(max_length=255)
    extracted_folder_size = models.BigIntegerField()
    radiomics_data_prepared = models.BooleanField(default=False)
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    extracted_at = models.DateTimeField(auto_now_add=True)
   
    def __str__(self):
        return self.zip_file.name
    
# Patient Data
class Patient(models.Model):
    uploaded_zip_file = models.ForeignKey(UploadZip, on_delete=models.CASCADE)
    patient_dir = models.CharField(max_length=500)
    patient_id = models.CharField(max_length=100)
    patient_name = models.CharField(max_length=200)
    patient_gender = models.CharField(max_length=10)
    patient_dob = models.CharField(max_length=20)
    institution_name = models.CharField(max_length=200)
 
    def __str__(self):
        return self.patient_id
    

# Patient Study
class Study(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    study_dir = models.CharField(max_length=500)
    study_id = models.CharField(max_length=100)
    study_date = models.CharField(max_length=20)
    study_description = models.CharField(max_length=500)
    study_instance_uid = models.CharField(max_length=100)
    frame_of_reference_uid = models.CharField(max_length=100) # need to be checked

    def __str__(self):
        return self.study_id
    
# Patient Series
class Series(models.Model):
    study = models.ForeignKey(Study, on_delete=models.CASCADE)
    series_dir = models.CharField(max_length=500)
    series_instance_uid = models.CharField(max_length=100)
    series_description = models.CharField(max_length=500)
    series_number = models.IntegerField()
    modality = models.CharField(max_length=20)

    def __str__(self):
        return f"Series {self.series_number} - {self.series_description}"

# Series Instance
class Instance(models.Model):
    series = models.ForeignKey(Series, on_delete=models.CASCADE)
    instance_dir = models.CharField(max_length=500)
    sop_instance_uid = models.CharField(max_length=100)
    modality = models.CharField(max_length=20)
    instance_number = models.IntegerField()

    def __str__(self):
        return self.sop_instance_uid
    

# RTSTRUCT
class Rtstruct(models.Model):
    series_instance = models.ForeignKey(Instance, on_delete=models.CASCADE)
    rtstruct_dir = models.CharField(max_length=500)
    rtstruct_date = models.CharField(max_length=20)
    rtstruct_time = models.CharField(max_length=20)
    rtstruct_sop_instance_uid = models.CharField(max_length=100)
    rtstruct_series_instance_uid = models.CharField(max_length=100)
    rtstruct_study_instance_uid = models.CharField(max_length=100)
    rtstruct_frame_of_reference_uid = models.CharField(max_length=100)
    rtstruct_series_description = models.CharField(max_length=500)


    def __str__(self):
        return self.rtstruct_sop_instance_uid

# RTPlan
class Rtplan(models.Model):
    rtstruct = models.ForeignKey(Rtstruct, on_delete=models.CASCADE)
    

# RTDose
class Rtdose(models.Model):
    rtplan = models.ForeignKey(Rtplan, on_delete=models.CASCADE)

# ROI
class Roi(models.Model):
    rtstruct = models.ForeignKey(Rtstruct, on_delete=models.CASCADE)    
    roi_number = models.IntegerField()
    roi_name = models.CharField(max_length=200)
    clean_roi_name = models.CharField(max_length=200, blank=True, null=True)
    roi_of_clean_roi_name_match_tg263 = models.BooleanField(default=False)
    tg263_primary_name = models.CharField(max_length=16)
    tg263_reverse_order_name = models.CharField(max_length=16)
    target_type = models.CharField(max_length=255)
    major_category = models.CharField(max_length=255, null=True, blank=True)
    minor_category = models.CharField(max_length=255, null=True, blank=True)
    anatomic_group = models.CharField(max_length=255, null=True, blank=True)
    fma_id = models.CharField(max_length=255, null=True, blank=True)
    add_for_radiomics = models.BooleanField(default=False, null=True, blank=True)
    ct_nrrd_file_path = models.CharField(max_length=500, blank=True, null=True)
    roi_nrrd_file_path = models.CharField(max_length=500, blank=True, null=True)
    user_modified_name = models.CharField(max_length=200)

    class Meta:
        unique_together = ['rtstruct', 'roi_number']

    def __str__(self):
        return self.tg263_primary_name
    
class ExtractionSession(models.Model):
    extraction_id = models.AutoField(primary_key=True)
    extraction_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Extraction {self.extraction_id} - {self.extraction_date}"

class RadiomicFeatures(models.Model):
    """All Radiomic Features in a single table"""
    zip_id = models.ForeignKey(UploadZip, on_delete=models.CASCADE, null=True, blank=True)
    patient_id = models.ForeignKey(Patient, on_delete=models.CASCADE, null=True, blank=True)
    patient_identifier = models.CharField(max_length=200, null=True, blank=True)
    roi = models.ForeignKey(Roi, on_delete=models.CASCADE)
    roi_name = models.CharField(max_length=200, null=True, blank=True)
    extraction_session = models.ForeignKey(ExtractionSession, on_delete=models.CASCADE, null=True, blank=True)
    
    # Shape Features
    original_shape_VoxelVolume = models.FloatField(null=True)
    original_shape_Maximum3DDiameter = models.FloatField(null=True)
    original_shape_MeshVolume = models.FloatField(null=True)
    original_shape_MajorAxisLength = models.FloatField(null=True)
    original_shape_Sphericity = models.FloatField(null=True)
    original_shape_LeastAxisLength = models.FloatField(null=True)
    original_shape_Elongation = models.FloatField(null=True)
    original_shape_SurfaceVolumeRatio = models.FloatField(null=True)
    original_shape_Maximum2DDiameterSlice = models.FloatField(null=True)
    original_shape_Flatness = models.FloatField(null=True)
    original_shape_SurfaceArea = models.FloatField(null=True)
    original_shape_MinorAxisLength = models.FloatField(null=True)
    original_shape_Maximum2DDiameterColumn = models.FloatField(null=True)
    original_shape_Maximum2DDiameterRow = models.FloatField(null=True)

    # GLCM Features
    original_glcm_JointAverage = models.FloatField(null=True)
    original_glcm_JointEntropy = models.FloatField(null=True)
    original_glcm_ClusterShade = models.FloatField(null=True)
    original_glcm_MaximumProbability = models.FloatField(null=True)
    original_glcm_Idmn = models.FloatField(null=True)
    original_glcm_JointEnergy = models.FloatField(null=True)
    original_glcm_Contrast = models.FloatField(null=True)
    original_glcm_DifferenceEntropy = models.FloatField(null=True)
    original_glcm_InverseVariance = models.FloatField(null=True)
    original_glcm_DifferenceVariance = models.FloatField(null=True)
    original_glcm_Idn = models.FloatField(null=True)
    original_glcm_Idm = models.FloatField(null=True)
    original_glcm_Correlation = models.FloatField(null=True)
    original_glcm_Autocorrelation = models.FloatField(null=True)
    original_glcm_SumEntropy = models.FloatField(null=True)
    original_glcm_SumSquares = models.FloatField(null=True)
    original_glcm_ClusterProminence = models.FloatField(null=True)
    original_glcm_Imc2 = models.FloatField(null=True)
    original_glcm_Imc1 = models.FloatField(null=True)
    original_glcm_DifferenceAverage = models.FloatField(null=True)
    original_glcm_Id = models.FloatField(null=True)
    original_glcm_ClusterTendency = models.FloatField(null=True)

    # GLDM Features
    original_gldm_GrayLevelVariance = models.FloatField(null=True)
    original_gldm_HighGrayLevelEmphasis = models.FloatField(null=True)
    original_gldm_DependenceEntropy = models.FloatField(null=True)
    original_gldm_DependenceNonUniformity = models.FloatField(null=True)
    original_gldm_GrayLevelNonUniformity = models.FloatField(null=True)
    original_gldm_SmallDependenceEmphasis = models.FloatField(null=True)
    original_gldm_SmallDependenceHighGrayLevelEmphasis = models.FloatField(null=True)
    original_gldm_DependenceNonUniformityNormalized = models.FloatField(null=True)
    original_gldm_LargeDependenceEmphasis = models.FloatField(null=True)
    original_gldm_LargeDependenceLowGrayLevelEmphasis = models.FloatField(null=True)
    original_gldm_DependenceVariance = models.FloatField(null=True)
    original_gldm_LargeDependenceHighGrayLevelEmphasis = models.FloatField(null=True)
    original_gldm_SmallDependenceLowGrayLevelEmphasis = models.FloatField(null=True)
    original_gldm_LowGrayLevelEmphasis = models.FloatField(null=True)

    # First Order Features
    original_firstorder_InterquartileRange = models.FloatField(null=True)
    original_firstorder_Skewness = models.FloatField(null=True)
    original_firstorder_Uniformity = models.FloatField(null=True)
    original_firstorder_Median = models.FloatField(null=True)
    original_firstorder_Energy = models.FloatField(null=True)
    original_firstorder_RobustMeanAbsoluteDeviation = models.FloatField(null=True)
    original_firstorder_MeanAbsoluteDeviation = models.FloatField(null=True)
    original_firstorder_TotalEnergy = models.FloatField(null=True)
    original_firstorder_Maximum = models.FloatField(null=True)
    original_firstorder_RootMeanSquared = models.FloatField(null=True)
    original_firstorder_90Percentile = models.FloatField(null=True)
    original_firstorder_Minimum = models.FloatField(null=True)
    original_firstorder_Entropy = models.FloatField(null=True)
    original_firstorder_Range = models.FloatField(null=True)
    original_firstorder_Variance = models.FloatField(null=True)
    original_firstorder_10Percentile = models.FloatField(null=True)
    original_firstorder_Kurtosis = models.FloatField(null=True)
    original_firstorder_Mean = models.FloatField(null=True)

    # GLRLM Features
    original_glrlm_ShortRunLowGrayLevelEmphasis = models.FloatField(null=True)
    original_glrlm_GrayLevelVariance = models.FloatField(null=True)
    original_glrlm_LowGrayLevelRunEmphasis = models.FloatField(null=True)
    original_glrlm_GrayLevelNonUniformityNormalized = models.FloatField(null=True)
    original_glrlm_RunVariance = models.FloatField(null=True)
    original_glrlm_GrayLevelNonUniformity = models.FloatField(null=True)
    original_glrlm_LongRunEmphasis = models.FloatField(null=True)
    original_glrlm_ShortRunHighGrayLevelEmphasis = models.FloatField(null=True)
    original_glrlm_RunLengthNonUniformity = models.FloatField(null=True)
    original_glrlm_ShortRunEmphasis = models.FloatField(null=True)
    original_glrlm_LongRunHighGrayLevelEmphasis = models.FloatField(null=True)
    original_glrlm_RunPercentage = models.FloatField(null=True)
    original_glrlm_LongRunLowGrayLevelEmphasis = models.FloatField(null=True)
    original_glrlm_RunEntropy = models.FloatField(null=True)
    original_glrlm_HighGrayLevelRunEmphasis = models.FloatField(null=True)
    original_glrlm_RunLengthNonUniformityNormalized = models.FloatField(null=True)

    # GLSZM Features
    original_glszm_GrayLevelVariance = models.FloatField(null=True)
    original_glszm_ZoneVariance = models.FloatField(null=True)
    original_glszm_GrayLevelNonUniformityNormalized = models.FloatField(null=True)
    original_glszm_SizeZoneNonUniformityNormalized = models.FloatField(null=True)
    original_glszm_SizeZoneNonUniformity = models.FloatField(null=True)
    original_glszm_GrayLevelNonUniformity = models.FloatField(null=True)
    original_glszm_LargeAreaEmphasis = models.FloatField(null=True)
    original_glszm_SmallAreaHighGrayLevelEmphasis = models.FloatField(null=True)
    original_glszm_ZonePercentage = models.FloatField(null=True)
    original_glszm_LargeAreaLowGrayLevelEmphasis = models.FloatField(null=True)
    original_glszm_LargeAreaHighGrayLevelEmphasis = models.FloatField(null=True)
    original_glszm_HighGrayLevelZoneEmphasis = models.FloatField(null=True)
    original_glszm_SmallAreaEmphasis = models.FloatField(null=True)
    original_glszm_LowGrayLevelZoneEmphasis = models.FloatField(null=True)
    original_glszm_ZoneEntropy = models.FloatField(null=True)
    original_glszm_SmallAreaLowGrayLevelEmphasis = models.FloatField(null=True)
    class Meta:
        verbose_name = "Radiomic Features"
        verbose_name_plural = "Radiomic Features"


class RadiomicFeatureMapping(models.Model):
    feature_name = models.CharField(max_length=255, null=True, blank=True)
    feature_class = models.CharField(max_length=255, null=True, blank=True)
    feature = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField(null=True, blank=True)

    class Meta:
        verbose_name = "Radiomic Feature Mapping"
        verbose_name_plural = "Radiomic Feature Mappings"

    def __str__(self):
        return f"{self.feature_name} - {self.feature_class}"
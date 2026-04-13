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
    zip_file_size = models.IntegerField()
    zip_extracted = models.BooleanField(default=False)
    extracted_path = models.CharField(max_length=255)
    extracted_folder_size = models.IntegerField()
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
    major_category = models.CharField(max_length=255)
    minor_category = models.CharField(max_length=255)
    anatomic_group = models.CharField(max_length=255)
    fma_id = models.CharField(max_length=255)
    add_for_radiomics = models.BooleanField(default=False, null=True, blank=True)
    ct_nrrd_file_path = models.CharField(max_length=500, blank=True, null=True)
    roi_nrrd_file_path = models.CharField(max_length=500, blank=True, null=True)
    user_modified_name = models.CharField(max_length=200)

    class Meta:
        unique_together = ['rtstruct', 'roi_number']

    def __str__(self):
        return self.tg263_primary_name
    

# First Order Radiomic Features
class FirstOrderFeatures(models.Model):
    """First Order Statistics Features"""
    roi = models.OneToOneField(Roi, on_delete=models.CASCADE)
    energy = models.FloatField(null=True, help_text="Sum of squared pixels")
    total_energy = models.FloatField(null=True, help_text="Total energy of image array")
    entropy = models.FloatField(null=True, help_text="Entropy value")
    minimum = models.FloatField(null=True, help_text="Minimum gray level intensity")
    maximum = models.FloatField(null=True, help_text="Maximum gray level intensity")
    mean = models.FloatField(null=True, help_text="Mean gray level intensity")
    median = models.FloatField(null=True, help_text="Median gray level intensity")
    standard_deviation = models.FloatField(null=True, help_text="Standard deviation of gray level intensity")
    mean_absolute_deviation = models.FloatField(null=True, help_text="Mean absolute deviation")
    robust_mean_absolute_deviation = models.FloatField(null=True, help_text="Robust mean absolute deviation")
    root_mean_squared = models.FloatField(null=True, help_text="Root mean squared of gray level intensity")
    skewness = models.FloatField(null=True, help_text="Skewness of gray level intensity")
    kurtosis = models.FloatField(null=True, help_text="Kurtosis of gray level intensity")
    variance = models.FloatField(null=True, help_text="Variance of gray level intensity")
    uniformity = models.FloatField(null=True, help_text="Uniformity of gray level intensity")
    percentile_10 = models.FloatField(null=True, help_text="10th percentile")
    percentile_90 = models.FloatField(null=True, help_text="90th percentile")
    interquartile_range = models.FloatField(null=True, help_text="Interquartile range")
    range = models.FloatField(null=True, help_text="Range of gray levels")

    class Meta:
        verbose_name = "First Order Features"
        verbose_name_plural = "First Order Features"

# 3D Shape Radiomic Features
class Shape3DFeatures(models.Model):
    """3D Shape Features"""
    roi = models.OneToOneField(Roi, on_delete=models.CASCADE)
    mesh_volume = models.FloatField(null=True, help_text="Volume of the mesh")
    voxel_count = models.IntegerField(null=True, help_text="Number of voxels")
    surface_area = models.FloatField(null=True, help_text="Surface area of mesh")
    surface_volume_ratio = models.FloatField(null=True, help_text="Surface to volume ratio")
    sphericity = models.FloatField(null=True, help_text="Sphericity of 3D segment")
    compactness1 = models.FloatField(null=True, help_text="First compactness metric")
    compactness2 = models.FloatField(null=True, help_text="Second compactness metric")
    spherical_disproportion = models.FloatField(null=True, help_text="Spherical disproportion")
    maximum_3d_diameter = models.FloatField(null=True, help_text="Largest pairwise Euclidean distance")
    major_axis_length = models.FloatField(null=True, help_text="Length of major axis")
    minor_axis_length = models.FloatField(null=True, help_text="Length of minor axis")
    least_axis_length = models.FloatField(null=True, help_text="Length of least axis")
    elongation = models.FloatField(null=True, help_text="Major to minor axis ratio")
    flatness = models.FloatField(null=True, help_text="Minor to least axis ratio")

    class Meta:
        verbose_name = "3D Shape Features"
        verbose_name_plural = "3D Shape Features"

# 2D Shape Radiomic Feature
class Shape2DFeatures(models.Model):
    """2D Shape Features"""
    roi = models.OneToOneField(Roi, on_delete=models.CASCADE)
    pixel_surface = models.FloatField(null=True, help_text="Number of pixels")
    perimeter = models.FloatField(null=True, help_text="Perimeter length")
    perimeter_to_surface_ratio = models.FloatField(null=True, help_text="Perimeter to surface ratio")
    sphericity = models.FloatField(null=True, help_text="Sphericity")
    spherical_disproportion = models.FloatField(null=True, help_text="Spherical disproportion")
    maximum_2d_diameter = models.FloatField(null=True, help_text="Largest diameter")
    major_axis_length = models.FloatField(null=True, help_text="Major axis length")
    minor_axis_length = models.FloatField(null=True, help_text="Minor axis length")
    elongation = models.FloatField(null=True, help_text="Major to minor axis ratio")
    circularity = models.FloatField(null=True, help_text="Perimeter-area relationship")

    class Meta:
        verbose_name = "2D Shape Features"
        verbose_name_plural = "2D Shape Features"

# Gray Level Co-occurrence Matrix Features
class GLCMFeatures(models.Model):
    """Gray Level Co-occurrence Matrix Features"""
    roi = models.OneToOneField(Roi, on_delete=models.CASCADE)
    autocorrelation = models.FloatField(null=True, help_text="Measure of magnitude of fineness and coarseness")
    joint_average = models.FloatField(null=True, help_text="Joint average")
    cluster_prominence = models.FloatField(null=True, help_text="Measure of asymmetry")
    cluster_shade = models.FloatField(null=True, help_text="Measure of skewness")
    cluster_tendency = models.FloatField(null=True, help_text="Complexity measure")
    contrast = models.FloatField(null=True, help_text="Local intensity variation")
    correlation = models.FloatField(null=True, help_text="Linear dependency measure")
    difference_average = models.FloatField(null=True, help_text="Mean of difference histogram")
    difference_entropy = models.FloatField(null=True, help_text="Entropy of difference histogram")
    difference_variance = models.FloatField(null=True, help_text="Variance of difference histogram")
    joint_energy = models.FloatField(null=True, help_text="Angular Second Moment")
    joint_entropy = models.FloatField(null=True, help_text="Randomness of distribution")
    imc1 = models.FloatField(null=True, help_text="Information measure of correlation 1")
    imc2 = models.FloatField(null=True, help_text="Information measure of correlation 2")
    idm = models.FloatField(null=True, help_text="Inverse Difference Moment")
    idmn = models.FloatField(null=True, help_text="Inverse Difference Moment Normalized")
    inverse_difference = models.FloatField(null=True, help_text="Inverse Difference")
    idn = models.FloatField(null=True, help_text="Inverse Difference Normalized")
    inverse_variance = models.FloatField(null=True, help_text="Inverse variance")
    maximum_probability = models.FloatField(null=True, help_text="Maximum probability")
    sum_average = models.FloatField(null=True, help_text="Sum average")
    sum_entropy = models.FloatField(null=True, help_text="Sum entropy")
    sum_squares = models.FloatField(null=True, help_text="Sum of squares")

    class Meta:
        verbose_name = "GLCM Features"
        verbose_name_plural = "GLCM Features"

# Gray Level Size Zone Matrix Features
class GLSZMFeatures(models.Model):
    """Gray Level Size Zone Matrix Features"""
    roi = models.OneToOneField(Roi, on_delete=models.CASCADE)
    small_area_emphasis = models.FloatField(null=True, help_text="Emphasis on small size zones")
    large_area_emphasis = models.FloatField(null=True, help_text="Emphasis on large size zones")
    gray_level_non_uniformity = models.FloatField(null=True, help_text="Value distribution variability")
    gray_level_non_uniformity_normalized = models.FloatField(null=True, help_text="Normalized value distribution")
    size_zone_non_uniformity = models.FloatField(null=True, help_text="Size zone distribution variability")
    size_zone_non_uniformity_normalized = models.FloatField(null=True, help_text="Normalized size zone distribution")
    zone_percentage = models.FloatField(null=True, help_text="Fraction of zones")
    gray_level_variance = models.FloatField(null=True, help_text="Variance in gray level")
    zone_variance = models.FloatField(null=True, help_text="Variance in zone size")
    zone_entropy = models.FloatField(null=True, help_text="Randomness in distribution")
    low_gray_level_zone_emphasis = models.FloatField(null=True, help_text="Distribution of lower gray-level values")
    high_gray_level_zone_emphasis = models.FloatField(null=True, help_text="Distribution of higher gray-level values")
    small_area_low_gray_level_emphasis = models.FloatField(null=True, help_text="Small zones with low gray levels")
    small_area_high_gray_level_emphasis = models.FloatField(null=True, help_text="Small zones with high gray levels")
    large_area_low_gray_level_emphasis = models.FloatField(null=True, help_text="Large zones with low gray levels")
    large_area_high_gray_level_emphasis = models.FloatField(null=True, help_text="Large zones with high gray levels")

    class Meta:
        verbose_name = "GLSZM Features"
        verbose_name_plural = "GLSZM Features"

# Gray Level Run Length Matrix Features
class GLRLMFeatures(models.Model):
    """Gray Level Run Length Matrix Features"""
    roi = models.OneToOneField(Roi, on_delete=models.CASCADE)
    short_run_emphasis = models.FloatField(null=True, help_text="Emphasis on short runs")
    long_run_emphasis = models.FloatField(null=True, help_text="Emphasis on long runs")
    gray_level_non_uniformity = models.FloatField(null=True, help_text="Non-uniformity of gray-levels")
    gray_level_non_uniformity_normalized = models.FloatField(null=True, help_text="Normalized gray-level non-uniformity")
    run_length_non_uniformity = models.FloatField(null=True, help_text="Non-uniformity of run lengths")
    run_length_non_uniformity_normalized = models.FloatField(null=True, help_text="Normalized run length non-uniformity")
    run_percentage = models.FloatField(null=True, help_text="Fraction of runs")
    gray_level_variance = models.FloatField(null=True, help_text="Variance in gray level")
    run_variance = models.FloatField(null=True, help_text="Variance in run length")
    run_entropy = models.FloatField(null=True, help_text="Randomness of run distribution")
    low_gray_level_run_emphasis = models.FloatField(null=True, help_text="Emphasis on low gray levels")
    high_gray_level_run_emphasis = models.FloatField(null=True, help_text="Emphasis on high gray levels")
    short_run_low_gray_level_emphasis = models.FloatField(null=True, help_text="Emphasis on short runs with low gray levels")
    short_run_high_gray_level_emphasis = models.FloatField(null=True, help_text="Emphasis on short runs with high gray levels")
    long_run_low_gray_level_emphasis = models.FloatField(null=True, help_text="Emphasis on long runs with low gray levels")
    long_run_high_gray_level_emphasis = models.FloatField(null=True, help_text="Emphasis on long runs with high gray levels")

    class Meta:
        verbose_name = "GLRLM Features"
        verbose_name_plural = "GLRLM Features"

# Neighbouring Gray Tone Difference Matrix Features
class NGTDMFeatures(models.Model):
    """Neighbouring Gray Tone Difference Matrix Features"""
    roi = models.OneToOneField(Roi, on_delete=models.CASCADE)
    coarseness = models.FloatField(null=True, help_text="Measure of spatial rate of change")
    contrast = models.FloatField(null=True, help_text="Intensity difference between regions")
    busyness = models.FloatField(null=True, help_text="Spatial frequency of intensity changes")
    complexity = models.FloatField(null=True, help_text="Visual information content")
    strength = models.FloatField(null=True, help_text="Primitives' distinguishability")

    class Meta:
        verbose_name = "NGTDM Features"
        verbose_name_plural = "NGTDM Features"

# Gray Level Dependence Matrix Features
class GLDMFeatures(models.Model):
    """Gray Level Dependence Matrix Features"""
    roi = models.OneToOneField(Roi, on_delete=models.CASCADE)
    small_dependence_emphasis = models.FloatField(null=True, help_text="Emphasis on small dependencies")
    large_dependence_emphasis = models.FloatField(null=True, help_text="Emphasis on large dependencies")
    gray_level_non_uniformity = models.FloatField(null=True, help_text="Non-uniformity of gray-levels")
    gray_level_non_uniformity_normalized = models.FloatField(null=True, help_text="Normalized gray-level non-uniformity")
    dependence_non_uniformity = models.FloatField(null=True, help_text="Non-uniformity of dependencies")
    dependence_non_uniformity_normalized = models.FloatField(null=True, help_text="Normalized dependence non-uniformity")
    gray_level_variance = models.FloatField(null=True, help_text="Variance in gray level")
    dependence_variance = models.FloatField(null=True, help_text="Variance in dependence size")
    dependence_entropy = models.FloatField(null=True, help_text="Randomness of dependencies")
    low_gray_level_emphasis = models.FloatField(null=True, help_text="Emphasis on low gray levels")
    high_gray_level_emphasis = models.FloatField(null=True, help_text="Emphasis on high gray levels")
    small_dependence_low_gray_level_emphasis = models.FloatField(null=True, help_text="Emphasis on small dependencies with low gray levels")
    small_dependence_high_gray_level_emphasis = models.FloatField(null=True, help_text="Emphasis on small dependencies with high gray levels")
    large_dependence_low_gray_level_emphasis = models.FloatField(null=True, help_text="Emphasis on large dependencies with low gray levels")
    large_dependence_high_gray_level_emphasis = models.FloatField(null=True, help_text="Emphasis on large dependencies with high gray levels")

    class Meta:
        verbose_name = "GLDM Features"
        verbose_name_plural = "GLDM Features"

class RadiomicFeatureMapping(models.Model):
    feature_name = models.CharField(max_length=100)
    feature_class = models.CharField(max_length=100)

    class Meta:
        verbose_name = "Radiomic Feature Mapping"
        verbose_name_plural = "Radiomic Feature Mappings"

    def __str__(self):
        return f"{self.feature_name} - {self.feature_class}"
# QRATOR - Function Reference

This document provides detailed documentation of the key functions in the QRATOR application, organized by functionality.

## Table of Contents
1. [Core Application Views](#core-application-views)
2. [Project Management](#project-management)
3. [DICOM Processing](#dicom-processing)
4. [ROI Management](#roi-management)
5. [Radiomic Analysis](#radiomic-analysis)
6. [Visualization](#visualization)
7. [Data Processing](#data-processing)

## Core Application Views

### `dashboard_home(request)`
- **Description**: Renders the main dashboard view with user's recent projects and ROI statistics.
- **Parameters**: `request` - Django HTTP request object
- **Returns**: Rendered dashboard template with context

### `workspace(request)`
- **Description**: Displays the user's workspace with all their projects.
- **Parameters**: `request` - Django HTTP request object
- **Returns**: Rendered workspace template with user's projects

### `analytics(request)`
- **Description**: Provides analytics and statistics about the user's radiomics data.
- **Parameters**: `request` - Django HTTP request object
- **Returns**: Rendered analytics template with statistics and visualizations

## Project Management

### `create_project(request)`
- **Description**: Handles creation of new projects.
- **Parameters**: `request` - Django HTTP request object with project data
- **Returns**: Redirects to project detail or shows form with errors

### `project_detail(request, project_id)`
- **Description**: Displays details of a specific project.
- **Parameters**: 
  - `request` - Django HTTP request object
  - `project_id` - ID of the project to display
- **Returns**: Rendered project detail template

### `edit_project(request, project_id)`
- **Description**: Handles editing of existing projects.
- **Parameters**:
  - `request` - Django HTTP request object
  - `project_id` - ID of the project to edit
- **Returns**: Redirects to project detail or shows form with errors

### `delete_project(request, project_id)`
- **Description**: Handles project deletion.
- **Parameters**:
  - `request` - Django HTTP request object
  - `project_id` - ID of the project to delete
- **Returns**: Redirects to workspace or shows error message

## DICOM Processing

### `upload_zip(request, project_id)`
- **Description**: Handles uploading of DICOM zip files.
- **Parameters**:
  - `request` - Django HTTP request object with file data
  - `project_id` - ID of the project to associate the upload with
- **Returns**: Redirects to project detail or shows upload form

### `extract_zip(request, zip_id)`
- **Description**: Extracts and processes uploaded DICOM zip files.
- **Parameters**:
  - `request` - Django HTTP request object
  - `zip_id` - ID of the zip file to extract
- **Returns**: JSON response with extraction status

## ROI Management

### `harmonize_rtstruct(request, rtstruct_id)`
- **Description**: Handles RTSTRUCT harmonization with TG263 standard.
- **Parameters**:
  - `request` - Django HTTP request object
  - `rtstruct_id` - ID of the RTSTRUCT to harmonize
- **Returns**: JSON response with harmonization results

### `batch_harmonize_rois(request, zip_id)`
- **Description**: Batch harmonizes all ROIs in a zip file.
- **Parameters**:
  - `request` - Django HTTP request object
  - `zip_id` - ID of the zip file containing ROIs to harmonize
- **Returns**: JSON response with batch harmonization results

## Radiomic Analysis

### `generate_nifti_for_radiomics_rois(request, zip_id)`
- **Description**: Converts DICOM and RTSTRUCT to NIfTI/NRRD format for radiomics analysis.
- **Parameters**:
  - `request` - Django HTTP request object
  - `zip_id` - ID of the zip file to process
- **Returns**: JSON response with conversion status

### `detect_outliers_zscore(radiomic_features, threshold=2.0)`
- **Description**: Detects outliers using Z-score analysis for specific shape features.
- **Parameters**:
  - `radiomic_features` - QuerySet of RadiomicFeatures
  - `threshold` - Z-score threshold for outlier detection (default: 2.0)
- **Returns**: Dictionary with outlier information for each ROI and feature

### `detect_multivariate_outliers(radiomic_features, threshold=2.0)`
- **Description**: Detects multivariate outliers using Mahalanobis distance.
- **Parameters**:
  - `radiomic_features` - QuerySet of RadiomicFeatures
  - `threshold` - Threshold for outlier detection (default: 2.0)
- **Returns**: Dictionary with multivariate outlier analysis results

## Visualization

### `generate_distribution_chart(radiomic_features, feature_field, selected_roi='')`
- **Description**: Generates a Bokeh histogram chart for radiomic feature distribution.
- **Parameters**:
  - `radiomic_features` - QuerySet of RadiomicFeatures
  - `feature_field` - Name of the feature field to visualize
  - `selected_roi` - Optional ROI name to filter by
- **Returns**: Bokeh components (script, div) for embedding in templates

### `generate_hierarchical_clustering(radiomic_features)`
- **Description**: Generates hierarchical clustering visualization of features.
- **Parameters**:
  - `radiomic_features` - QuerySet of RadiomicFeatures
- **Returns**: Bokeh components for the clustering visualization

## Data Processing

### `update_dicom_roi_names(rtstruct_path, modified_rois, request=None, messages=None)`
- **Description**: Updates ROI names in a DICOM RTSTRUCT file.
- **Parameters**:
  - `rtstruct_path` - Path to the RTSTRUCT DICOM file
  - `modified_rois` - Dictionary of ROI modifications
  - `request` - Optional Django request object
  - `messages` - Optional Django messages framework
- **Returns**: Success status and message

### `regenerate_nrrd_with_harmonized_names(request, zip_id)`
- **Description**: Regenerates NRRD files using harmonized ROI names.
- **Parameters**:
  - `request` - Django HTTP request object
  - `zip_id` - ID of the zip file to process
- **Returns**: JSON response with regeneration status

## Helper Functions

### `get_tg263_data()`
- **Description**: Fetches TG263 standard data with fallback to sample data.
- **Returns**: Dictionary containing TG263 standard data

### `match_roi_with_tg263(roi_name, clean_roi_name, tg263_data)`
- **Description**: Matches ROI names with TG263 standard.
- **Parameters**:
  - `roi_name` - Original ROI name
  - `clean_roi_name` - Cleaned ROI name
  - `tg263_data` - TG263 standard data
- **Returns**: Tuple of (matched_data, is_perfect_match, match_type)

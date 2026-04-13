QRATOR (Quantitative Radiomics for Auto-segmentation Training Optimization in Radiotherapy) is a Python-based, flexible, extensible, and user-friendly Django web application that processes DICOM data, harmonizes RTSTRUCT labels (based on TG-263), extracts radiomic features and saves them as CSV files, visualizes features for selected ROIs, and performs univariate and multivariate outlier detection and feature clustering on radiotherapy planning images.

## Features
- Project-based version control
- Sequential organization of DICOM files
- RTSTRUCT harmonization based on TG-263
- Radiomic feature extraction and saving as comma-separated (CSV) files
- Graphical representation of radiomic features for selected ROIs
- Univariate and multivariate outlier detection
- Radiomic feature clustering for selected ROIs

### Project-based version control
 A project is a container to which you can upload patient ZIP files repeatedly (e.g., new acquisitions or corrected RTSTRUCT). Each upload creates a versioned snapshot and peform all the upper assign features.

### Sequential organization of DICOM files
DICOM (Digital Imaging and Communications in Medicine) is the global standard for medical image storage and transmission. In radiotherapy workflows, four DICOM modalities are commonly used: CT, RTSTRUCT, RTPLAN, and RTDOSE. CT provides image volumes, RTSTRUCT defines ROIs, RTPLAN encodes the treatment plan, and RTDOSE stores dose distributions. QRATOR processes uploaded DICOM files using python library pydicom, separates patient- and modality-specific sets, and lets users download organized bundles as a ZIP archive. Internally, QRATOR stores essential identifiers in the database (for example: patient ID, patient name, modality UIDs) to support downstream harmonization and feature extraction.

### RTSTRUCT harmonization based on TG-263
RTSTRUCT harmonization based on TG-263 is a process that standardizes RTSTRUCT labels to a common format. This is important for ensuring that the labels are consistent across different patients and can be used for radiomic feature extraction. QRATOR uses python library pydicom to read and write RTSTRUCT files, and uses the TG-263 standard to harmonize the labels.Single patient Harmonization and Batch Harmonization for multiple patients are available.Based on case and time user perform Harmonization process.

### Radiomic feature extraction and saving as comma-separated (CSV) files
Radiomic feature extraction is the process of using computational alogrithms to extract a large number of quantitative features from medical images.This is done to find information beyon waht is visible to the human eye. pyradiomics is a python based radiomics extraction library to extract:

1. Frist Order Features
2. 2D Shape Features
2. 3D Shape Features
3. GLCMFeatures
4. GLSZMFeatures
5. GLRLMFeatures
6. NGTDMFeatures
7. GLDMFeatures
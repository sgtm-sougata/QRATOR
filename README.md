# QRATOR - Quantitative Radiomics for Auto Segmentation Training Optimization in Radiotherapy

## Overview
QRATOR is a Django-based web application designed for medical image analysis, specifically focusing on radiomic feature extraction and statistical analysis. The application provides powerful tools for processing DICOM images, extracting radiomic features, and performing advanced statistical analyses with interactive visualizations.

## Features

### Core Functionality
- **DICOM Image Processing**: Upload and process medical images in DICOM format
- **Radiomic Feature Extraction**: Extract detailed shape and texture features from medical images
- **Interactive Visualization**: Built with Bokeh for interactive data exploration
- **User-Friendly Interface**: Web-based interface for easy access and operation

### Advanced Analysis
- **Univariate Statistics**: Basic statistical analysis of individual features
- **Multivariate Outlier Detection**: Mahalanobis distance-based outlier analysis
- **Hierarchical Clustering**: Interactive dendrograms for patient grouping
- **Z-Score Analysis**: Statistical outlier detection for quality control

### Visualization Tools
- Interactive histograms for feature distribution analysis
- Hierarchical clustering visualizations
- Statistical summary tables
- Patient-specific analysis views

## Technical Stack
- **Backend**: Python 3.x, Django
- **Frontend**: HTML5, CSS3, JavaScript
- **Data Analysis**: NumPy, SciPy, scikit-learn
- **Visualization**: Bokeh (≥3.0.0)
- **Medical Imaging**: pydicom

## Installation

### Prerequisites
- Python 3.8+
- pip (Python package manager)
- Virtual environment (recommended)

### Setup
1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd drawprep
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Run migrations:
   ```bash
   python manage.py migrate
   ```

5. Start the development server:
   ```bash
   python manage.py runserver
   ```

6. Open your browser and navigate to: http://127.0.0.1:8000/

## Usage
1. **Upload DICOM Images**: Use the upload interface to add your medical images
2. **Process Images**: Extract radiomic features from the uploaded images
3. **Analyze Results**: Explore the interactive visualizations and statistical analyses
4. **Export Data**: Download analysis results for further processing

## Dependencies
Key dependencies include:
- Django (≥4.0.0)
- Bokeh (≥3.0.0)
- NumPy (≥1.21.0)
- SciPy (≥1.9.0)
- scikit-learn (≥1.0.0)
- pydicom

[![DOI](https://zenodo.org/badge/1209066507.svg)](https://doi.org/10.5281/zenodo.19551677)

For a complete list of dependencies, see `requirements.txt`.


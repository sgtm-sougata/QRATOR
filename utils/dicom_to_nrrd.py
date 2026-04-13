import os
import re
import numpy as np
import pydicom
import SimpleITK as sitk
from rt_utils import RTStructBuilder
import nrrd

def dicom_ct_to_nrrd(dicom_folder, output_nrrd_path):
    """
    Convert DICOM CT series to NRRD format
    
    Args:
        dicom_folder: Path to folder containing DICOM CT series
        output_nrrd_path: Path to save the output NRRD file
    
    Returns:
        Path to the saved NRRD file
    """
    # Read the DICOM series
    reader = sitk.ImageSeriesReader()
    dicom_names = reader.GetGDCMSeriesFileNames(dicom_folder)
    reader.SetFileNames(dicom_names)
    ct_image = reader.Execute()
    
    # Write to NRRD format
    sitk.WriteImage(ct_image, output_nrrd_path)
    
    return output_nrrd_path

def rtstruct_to_nrrd(dicom_folder, rtstruct_path, output_folder, roi_names=None, roi_numbers=None):
    """
    Convert DICOM RTSTRUCT ROIs to NRRD format
    
    Args:
        dicom_folder: Path to folder containing DICOM CT series
        rtstruct_path: Path to RTSTRUCT DICOM file
        output_folder: Folder to save the output NRRD ROI files
        roi_names: List of ROI names to convert (if None, converts all)
    
    Returns:
        List of dictionaries containing ROI information:
            - name: ROI name
            - number: ROI number
            - path: Path to ROI NRRD file
    """
    os.makedirs(output_folder, exist_ok=True)
    
    try:
        # Load the RTSTRUCT file
        rtstruct = RTStructBuilder.create_from(
            dicom_series_path=dicom_folder,
            rt_struct_path=rtstruct_path
        )
        print(f"CT: {dicom_folder} RTSTRUCT: {rtstruct_path} RTSTRUCT object: {rtstruct}")
        
        # Read RTSTRUCT DICOM dataset to map names<->numbers
        rtstruct_ds = pydicom.dcmread(rtstruct_path)
        roi_numbers_map = {}
        for roi in rtstruct_ds.StructureSetROISequence:
            roi_numbers_map[roi.ROIName] = roi.ROINumber

        # If numbers are provided, map them to the exact DICOM ROI names
        if roi_numbers is not None:
            target_names = []
            for name, num in roi_numbers_map.items():
                if int(num) in set(int(n) for n in roi_numbers):
                    target_names.append(name)
        else:
            # Get list of ROI names if not specified
            target_names = roi_names if roi_names is not None else rtstruct.get_roi_names()
        
        # Build ROI number lookup by name
        name_to_number = {}
        for roi in rtstruct_ds.StructureSetROISequence:
            name_to_number[roi.ROIName] = roi.ROINumber
            
        # Convert each ROI to NRRD
        roi_info = []  # List to store ROI information
        for roi_name in target_names:
            try:
                # Get ROI number
                roi_number = name_to_number.get(roi_name, 0)
                
                # Get the mask for this ROI
                mask_3d = rtstruct.get_roi_mask_by_name(roi_name)
                
                # Transpose the mask to match CT dimensions
                mask_3d = np.transpose(mask_3d, (2, 0, 1))
                
                # Get the reference CT image
                reader = sitk.ImageSeriesReader()
                dicom_names = reader.GetGDCMSeriesFileNames(dicom_folder)
                reader.SetFileNames(dicom_names)
                ct_image = reader.Execute()
                
                # Create mask image with CT metadata
                mask_sitk = sitk.GetImageFromArray(mask_3d.astype(np.uint8))
                mask_sitk.SetOrigin(ct_image.GetOrigin())
                mask_sitk.SetSpacing(ct_image.GetSpacing())
                mask_sitk.SetDirection(ct_image.GetDirection())
                
                # Save to NRRD (sanitize ROI name for filesystem safety)
                safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", str(roi_name))
                output_path = os.path.join(output_folder, f"roi_{roi_number}_{safe_name}.nrrd")
                sitk.WriteImage(mask_sitk, output_path)
                
                # Store ROI information
                roi_info.append({
                    'name': roi_name,
                    'number': roi_number,
                    'path': output_path
                })
                print(f"Converted ROI: {roi_name}")
                
            except Exception as e:
                print(f"Error processing ROI {roi_name}: {str(e)}")
                continue
        
        return roi_info
        
    except Exception as e:
        print(f"Error loading RTSTRUCT: {str(e)}")
        return []

def convert_patient_data(dicom_folder, rtstruct_path, output_folder, roi_names=None, roi_numbers=None):
    """
    Convert both CT and RTSTRUCT data for a patient
    
    Args:
        dicom_folder: Path to folder containing DICOM CT series
        rtstruct_path: Path to RTSTRUCT DICOM file
        output_folder: Folder to save all output NRRD files
    
    Returns:
        Tuple containing:
        - ct_path: Path to the CT NRRD file
        - roi_info: List of dictionaries containing ROI information:
            - name: ROI name
            - number: ROI number
            - path: Path to ROI NRRD file
    """
    # Create output folder
    os.makedirs(output_folder, exist_ok=True)
    
    # Convert CT to NRRD
    ct_nrrd_path = os.path.join(output_folder, "ct.nrrd")
    ct_path = dicom_ct_to_nrrd(dicom_folder, ct_nrrd_path)
    
    # Convert RTSTRUCT ROIs to NRRD (filter list if provided)
    roi_folder = os.path.join(output_folder, "rois")
    os.makedirs(roi_folder, exist_ok=True)
    roi_info = rtstruct_to_nrrd(
        dicom_folder,
        rtstruct_path,
        roi_folder,
        roi_names=roi_names,
        roi_numbers=roi_numbers,
    )
    
    return ct_path, roi_info
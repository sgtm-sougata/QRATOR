from dicom_to_nrrd import dicom_ct_to_nrrd, rtstruct_to_nrrd, convert_patient_data
import os
# Example usage
if __name__ == "__main__":
    # Paths to your DICOM data
    dicom_folder = "/home/sougata/Documents/Python/radiomics feature extract/412197120/CT/"
    rtstruct_path = "/home/sougata/Documents/Python/radiomics feature extract/412197120/RTSTRUCT.412197120.243.dcm"
    output_folder = "output"
    
    # Example 1: Convert only CT to NRRD
    ct_nrrd_path = dicom_ct_to_nrrd(dicom_folder, output_folder + "/ct.nrrd")
    print(f"CT converted to NRRD: {ct_nrrd_path}")
    
    # Example 2: Convert only specific ROIs from RTSTRUCT to NRRD
    roi_names = ["Femur_Head_R"]  # Replace with your actual ROI names
    roi_paths = rtstruct_to_nrrd(dicom_folder, rtstruct_path, output_folder + "/rois", roi_names)
    print(f"ROIs converted to NRRD:")
    for roi_name, path in roi_paths.items():
        print(f"  - {roi_name}: {path}")
    
    # Example 3: Convert both CT and all ROIs in one go
    ct_path, all_roi_paths = convert_patient_data(dicom_folder, rtstruct_path, output_folder + "/complete")
    print(f"Complete conversion done:")
    print(f"  - CT: {ct_path}")
    print(f"  - ROIs: {len(all_roi_paths)} structures converted")
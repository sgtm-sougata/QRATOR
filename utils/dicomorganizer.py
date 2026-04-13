import pydicom
from pathlib import Path
from multiprocessing import Pool
import shutil
import logging
from typing import List, Tuple, Optional, Dict
import os
from datetime import datetime
from pathlib import Path
import sys
# Add the parent directory to the path to import Django models
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Import normalization functions
from normalization import clean_contour_label
import requests

class DicomOrganizer:
    def __init__(self, source_dir: str, destination_dir: str, upload_zip=None, models=None):
        self.source_dir = Path(source_dir)
        self.destination_dir = Path(destination_dir)
        self.upload_zip = upload_zip
        self.models = models  # Dictionary containing Django models
        self.destination_dir.mkdir(parents=True, exist_ok=True)
        self._setup_logging()

    def _setup_logging(self):
        """Setup logging configuration"""
        log_dir = Path('logs')
        log_dir.mkdir(exist_ok=True)
        
        log_file = log_dir / f'dicom_organizer_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )

    def _clean_text(self, value: object, max_len: int) -> str:
        """Sanitize text values to be safe for UTF-8 DB storage.

        - Convert to str
        - Replace invalid UTF-8 bytes
        - Remove NUL characters
        - Trim to max length
        """
        try:
            s = str(value) if value is not None else ''
        except Exception:
            s = ''
        # Ensure utf-8 compatible text and remove NULs
        s = s.encode('utf-8', 'replace').decode('utf-8', 'replace').replace('\x00', '')
        if max_len is not None and max_len > 0:
            s = s[:max_len]
        return s

    def is_dicom(self, file_path: Path) -> bool:
        """Check if file is DICOM without reading entire file"""
        try:
            with open(file_path, 'rb') as f:
                f.seek(128)
                magic = f.read(4)
                return magic == b'DICM'
        except Exception:
            return False

    def _scan_directory(self, directory: Path) -> List[Path]:
        """Scan a directory for DICOM files"""
        files = []
        for file_path in directory.iterdir():
            if file_path.is_file():
                if self.is_dicom(file_path):
                    files.append(file_path)
            elif file_path.is_dir():
                files.extend(self._scan_directory(file_path))
        return files

    def find_dicom_files(self) -> List[Path]:
        """Find all DICOM files recursively using multiple processes"""
        logging.info("Scanning for DICOM files...")
        
        # Get all subdirectories
        subdirs = [self.source_dir]
        subdirs.extend([d for d in self.source_dir.rglob('*') if d.is_dir()])
        
        # Use multiprocessing to scan directories in parallel
        num_processes = max(1, os.cpu_count() - 2)
        with Pool(processes=num_processes) as pool:
            results = pool.map(self._scan_directory, subdirs)
        
        # Flatten results
        dicom_files = [file for sublist in results for file in sublist]
        
        logging.info(f"Scan complete. Found {len(dicom_files)} DICOM files")
        return dicom_files

    def get_file_metadata(self, file_path: Path) -> Optional[Dict]:
        """Extract necessary DICOM metadata"""
        try:
            dicom = pydicom.dcmread(file_path, stop_before_pixels=True)
            # Read raw values
            raw = {
                'PatientID': getattr(dicom, 'PatientID', 'Unknown'),
                'PatientName': getattr(dicom, 'PatientName', 'Unknown'),
                'PatientSex': getattr(dicom, 'PatientSex', 'Unknown'),
                'PatientBirthDate': getattr(dicom, 'PatientBirthDate', 'Unknown'),
                'InstitutionName': getattr(dicom, 'InstitutionName', 'Unknown'),
                'StudyID': getattr(dicom, 'StudyID', 'Unknown'),
                'StudyDate': getattr(dicom, 'StudyDate', 'Unknown'),
                'StudyDescription': getattr(dicom, 'StudyDescription', 'Unknown'),
                'StudyInstanceUID': getattr(dicom, 'StudyInstanceUID', 'Unknown'),
                'FrameOfReferenceUID': getattr(dicom, 'FrameOfReferenceUID', 'Unknown'),
                'SeriesInstanceUID': getattr(dicom, 'SeriesInstanceUID', 'Unknown'),
                'SeriesDescription': getattr(dicom, 'SeriesDescription', 'Unknown'),
                'SeriesNumber': getattr(dicom, 'SeriesNumber', 'Unknown'),
                'Modality': getattr(dicom, 'Modality', 'Unknown'),
                'SOPInstanceUID': getattr(dicom, 'SOPInstanceUID', 'Unknown'),
                'InstanceNumber': getattr(dicom, 'InstanceNumber', '0'),
                'AccessionNumber': getattr(dicom, 'AccessionNumber', 'Unknown'),
                'SOPClassUID': getattr(dicom, 'SOPClassUID', 'Unknown'),
            }

            # Sanitize to match model limits
            meta = {
                'PatientID': self._clean_text(raw['PatientID'], 100),
                'PatientName': self._clean_text(raw['PatientName'], 200),
                'PatientSex': self._clean_text(raw['PatientSex'], 10),
                'PatientBirthDate': self._clean_text(raw['PatientBirthDate'], 20),
                'InstitutionName': self._clean_text(raw['InstitutionName'], 200),
                'StudyID': self._clean_text(raw['StudyID'], 100),
                'StudyDate': self._clean_text(raw['StudyDate'], 20),
                'StudyDescription': self._clean_text(raw['StudyDescription'], 500),
                'StudyInstanceUID': self._clean_text(raw['StudyInstanceUID'], 100),
                'FrameOfReferenceUID': self._clean_text(raw['FrameOfReferenceUID'], 100),
                'SeriesInstanceUID': self._clean_text(raw['SeriesInstanceUID'], 100),
                'SeriesDescription': self._clean_text(raw['SeriesDescription'], 500),
                'SeriesNumber': self._clean_text(raw['SeriesNumber'], 4).zfill(4),
                'Modality': self._clean_text(raw['Modality'], 20),
                'SOPInstanceUID': self._clean_text(raw['SOPInstanceUID'], 100),
                'InstanceNumber': self._clean_text(raw['InstanceNumber'], 6).zfill(6),
                'AccessionNumber': self._clean_text(raw['AccessionNumber'], 100),
                'SOPClassUID': self._clean_text(raw['SOPClassUID'], 100),
            }
            # Add RTSTRUCT specific metadata if this is an RTSTRUCT file
            if meta['Modality'] == 'RTSTRUCT':
                meta.update({
                    'StructureSetDate': self._clean_text(getattr(dicom, 'StructureSetDate', 'Unknown'), 20),
                    'StructureSetTime': self._clean_text(getattr(dicom, 'StructureSetTime', 'Unknown'), 20),
                    'StructureSetLabel': self._clean_text(getattr(dicom, 'StructureSetLabel', 'Unknown'), 200),
                    'StructureSetName': self._clean_text(getattr(dicom, 'StructureSetName', 'Unknown'), 200),
                })
            return meta
        except Exception as e:
            logging.error(f"Error reading metadata from {file_path}: {str(e)}")
            return None

    def clean_name(self, name: str) -> str:
        """Clean string for use in file path"""
        invalid_chars = '<>:"/\\|?*'
        cleaned_name = ''.join(c if c not in invalid_chars else '_' for c in name)
        cleaned_name = '_'.join(cleaned_name.split())
        return cleaned_name[:50]

    def generate_filename(self, metadata: Dict) -> str:
        """Generate a structured filename"""
        filename_parts = [
            metadata['Modality'],
            f"S{metadata['SeriesNumber']}",
            f"I{metadata['InstanceNumber']}",
            metadata['SOPInstanceUID'][-8:]
        ]
        return '_'.join(filename_parts) + '.dcm'

    def save_patient_data(self, metadata: Dict, patient_dir: str):
        """Save or update patient data in database"""
        if not self.upload_zip or not self.models:
            return None
            
        Patient = self.models['Patient']
        # Avoid fetching full rows with potentially invalid encodings by checking existence via values_list
        existing_id = (
            Patient.objects.filter(
                patient_id=metadata['PatientID'],
                uploaded_zip_file=self.upload_zip,
            ).values_list('id', flat=True).first()
        )

        if existing_id is None:
            # Create a new patient with sanitized text
            patient = Patient.objects.create(
                uploaded_zip_file=self.upload_zip,
                patient_dir=patient_dir,
                patient_id=metadata['PatientID'],
                patient_name=metadata['PatientName'],
                patient_gender=metadata['PatientSex'],
                patient_dob=metadata['PatientBirthDate'],
                institution_name=metadata['InstitutionName'],
            )
            return patient

        # Update existing without decoding other text columns
        Patient.objects.filter(id=existing_id).update(
            patient_dir=patient_dir,
            patient_name=metadata['PatientName'],
            patient_gender=metadata['PatientSex'],
            patient_dob=metadata['PatientBirthDate'],
            institution_name=metadata['InstitutionName'],
        )
        # Return a lightweight instance with only id loaded
        return Patient.objects.only('id').get(id=existing_id)

    def save_study_data(self, patient, metadata: Dict, study_dir: str):
        """Save or update study data in database"""
        if not self.models:
            return None
            
        Study = self.models['Study']
        study, created = Study.objects.get_or_create(
            study_instance_uid=metadata['StudyInstanceUID'],
            patient=patient,
            defaults={
                'study_dir': study_dir,
                'study_id': metadata['StudyID'],
                'study_date': metadata['StudyDate'],
                'study_description': metadata['StudyDescription'],
                'frame_of_reference_uid': metadata['FrameOfReferenceUID']
            }
        )
        
        if not created:
            # Update existing study data
            study.study_dir = study_dir
            study.study_id = metadata['StudyID']
            study.study_date = metadata['StudyDate']
            study.study_description = metadata['StudyDescription']
            study.frame_of_reference_uid = metadata['FrameOfReferenceUID']
            study.save()
            
        return study

    def save_series_data(self, study, metadata: Dict, series_dir: str):
        """Save or update series data in database"""
        if not self.models:
            return None
            
        Series = self.models['Series']
        try:
            series_number = int(metadata['SeriesNumber'])
        except (ValueError, TypeError):
            series_number = 0
            
        series, created = Series.objects.get_or_create(
            series_instance_uid=metadata['SeriesInstanceUID'],
            study=study,
            defaults={
                'series_dir': series_dir,
                'series_description': metadata['SeriesDescription'],
                'series_number': series_number,
                'modality': metadata['Modality']
            }
        )
        
        if not created:
            # Update existing series data
            series.series_dir = series_dir
            series.series_description = metadata['SeriesDescription']
            series.series_number = series_number
            series.modality = metadata['Modality']
            series.save()
            
        return series

    def save_instance_data(self, series, metadata: Dict, instance_dir: str):
        """Save or update instance data in database"""
        if not self.models:
            return None
            
        Instance = self.models['Instance']
        try:
            instance_number = int(metadata['InstanceNumber'])
        except (ValueError, TypeError):
            instance_number = 0
            
        instance, created = Instance.objects.get_or_create(
            sop_instance_uid=metadata['SOPInstanceUID'],
            series=series,
            defaults={
                'instance_dir': instance_dir,
                'modality': metadata['Modality'],
                'instance_number': instance_number
            }
        )
        
        if not created:
            # Update existing instance data
            instance.instance_dir = instance_dir
            instance.modality = metadata['Modality']
            instance.instance_number = instance_number
            instance.save()
            
        return instance

    def extract_roi_data(self, file_path: Path) -> List[Dict]:
        """Extract ROI data from RTSTRUCT files"""
        try:
            logging.info(f"Attempting to read RTSTRUCT file: {file_path}")
            dicom = pydicom.dcmread(file_path)
            roi_data = []
            
            # Check if this is an RTSTRUCT file
            if not hasattr(dicom, 'StructureSetROISequence'):
                logging.warning(f"File {file_path} is not a valid RTSTRUCT (missing StructureSetROISequence)")
                return roi_data
                
            # Extract ROI information
            for roi_seq in dicom.StructureSetROISequence:
                roi_info = {
                    'roi_number': int(getattr(roi_seq, 'ROINumber', 0)),
                    'roi_name': str(getattr(roi_seq, 'ROIName', 'Unknown')),
                    'roi_description': str(getattr(roi_seq, 'ROIDescription', '')),
                    'roi_generation_algorithm': str(getattr(roi_seq, 'ROIGenerationAlgorithm', 'Unknown')),
                    'referenced_frame_of_reference_uid': str(getattr(roi_seq, 'ReferencedFrameOfReferenceUID', 'Unknown'))
                }
                
                # Try to get additional ROI observation data if available
                if hasattr(dicom, 'RTROIObservationsSequence'):
                    for obs_seq in dicom.RTROIObservationsSequence:
                        if int(getattr(obs_seq, 'ReferencedROINumber', 0)) == roi_info['roi_number']:
                            roi_info.update({
                                'roi_observation_label': str(getattr(obs_seq, 'ROIObservationLabel', '')),
                                'rt_roi_interpreted_type': str(getattr(obs_seq, 'RTROIInterpretedType', '')),
                                'roi_interpreter': str(getattr(obs_seq, 'ROIInterpreter', ''))
                            })
                            break
                
                roi_data.append(roi_info)
                
            logging.info(f"Extracted {len(roi_data)} ROIs from RTSTRUCT file: {file_path}")
            return roi_data
            
        except Exception as e:
            logging.error(f"Error extracting ROI data from {file_path}: {str(e)}")
            return []

    def save_rtstruct_data(self, instance, metadata: Dict, rtstruct_dir: str):
        """Save or update RTSTRUCT data in database"""
        if not self.models:
            logging.warning("No models available for RTSTRUCT processing")
            return None
            
        if metadata['Modality'] != 'RTSTRUCT':
            return None
            
        logging.info(f"Processing RTSTRUCT with SOP Instance UID: {metadata['SOPInstanceUID']}")
            
        Rtstruct = self.models['Rtstruct']
        rtstruct, created = Rtstruct.objects.get_or_create(
            rtstruct_sop_instance_uid=metadata['SOPInstanceUID'],
            series_instance=instance,
            defaults={
                'rtstruct_dir': rtstruct_dir,
                'rtstruct_date': metadata.get('StructureSetDate', 'Unknown'),
                'rtstruct_time': metadata.get('StructureSetTime', 'Unknown'),
                'rtstruct_series_instance_uid': metadata['SeriesInstanceUID'],
                'rtstruct_study_instance_uid': metadata['StudyInstanceUID'],
                'rtstruct_frame_of_reference_uid': metadata['FrameOfReferenceUID'],
                'rtstruct_series_description': metadata['SeriesDescription']
            }
        )
        
        if not created:
            # Update existing RTSTRUCT data
            rtstruct.rtstruct_dir = rtstruct_dir
            rtstruct.rtstruct_date = metadata.get('StructureSetDate', 'Unknown')
            rtstruct.rtstruct_time = metadata.get('StructureSetTime', 'Unknown')
            rtstruct.rtstruct_series_instance_uid = metadata['SeriesInstanceUID']
            rtstruct.rtstruct_study_instance_uid = metadata['StudyInstanceUID']
            rtstruct.rtstruct_frame_of_reference_uid = metadata['FrameOfReferenceUID']
            rtstruct.rtstruct_series_description = metadata['SeriesDescription']
            rtstruct.save()
            
        return rtstruct

    def fetch_tg263_data(self):
        """Fetch TG263 data from the API"""
        try:
            logging.info("Attempting to fetch TG263 data from API...")
            response = requests.get('http://localhost:8002/api/tg263/', timeout=10)
            if response.status_code == 200:
                data = response.json()
                logging.info(f"Successfully fetched {len(data)} TG263 entries")
                return data
            else:
                logging.error(f"Error fetching TG263 data: HTTP {response.status_code}")
                logging.error(f"Response content: {response.text}")
                return []
        except requests.exceptions.RequestException as e:
            logging.error(f"Error fetching TG263 data: {str(e)}")
            if isinstance(e, requests.exceptions.ConnectionError):
                logging.error("Connection failed - Is the TG263 API server running?")
            return []

    def match_roi_with_tg263(self, roi_name, clean_roi_name, tg263_data):
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

    def save_roi_data(self, rtstruct, roi_data_list: List[Dict]):
        """Save ROI data to database with normalization and TG263 matching"""
        if not self.models:
            logging.warning("No models available for ROI processing")
            return []
            
        if not roi_data_list:
            logging.warning("No ROI data provided for processing")
            return []
            
        logging.info(f"Processing {len(roi_data_list)} ROIs for RTSTRUCT")
            
        Roi = self.models['Roi']
        saved_rois = []
        
        # Fetch TG263 data once for all ROIs
        tg263_data = self.fetch_tg263_data()
        if not tg263_data:
            logging.warning("Could not fetch TG263 data from API. ROI matching will be skipped.")
        
        for roi_data in roi_data_list:
            try:
                # Clean and normalize the ROI name using the normalization function
                original_roi_name = roi_data['roi_name'] if roi_data['roi_name'] else 'Unknown'
                normalized_name = clean_contour_label(original_roi_name)
                
                # Ensure the normalized name fits within the 16 character limit for tg263_primary_name
                # Try to match with TG263 data
                tg263_match = None
                match_result = False
                match_type = None
                roi_of_clean_roi_name_match_tg263 = False
                target_type = roi_data.get('rt_roi_interpreted_type', '')
                major_category = ''
                minor_category = ''
                anatomic_group = ''
                fma_id = ''
                tg263_primary = ''
                tg263_reverse = ''
                
                if tg263_data:
                    tg263_match, match_result, match_type = self.match_roi_with_tg263(original_roi_name, normalized_name, tg263_data)
                    if tg263_match:
                        roi_of_clean_roi_name_match_tg263 = True
                        target_type = tg263_match.get('Target_Type', '')
                        major_category = tg263_match.get('Major_Category', '')
                        minor_category = tg263_match.get('Minor_Category', '')
                        anatomic_group = tg263_match.get('Anatomic_Group', '')
                        fma_id = tg263_match.get('FMAID', '')
                        tg263_primary = tg263_match.get('TG263_Primary_Name', '')
                        tg263_reverse = tg263_match.get('TG263_Reverse_Order_Name', tg263_primary)
                        match_info = "original name" if match_type == "roi_name" else "cleaned name"
                        logging.info(f"ROI '{original_roi_name}' matched with TG263 via {match_info}: {tg263_match.get('Description', 'N/A')}")
                    else:
                        logging.info(f"ROI '{original_roi_name}' could not be matched with TG263 data")
                
                roi, created = Roi.objects.get_or_create(
                    rtstruct=rtstruct,
                    roi_number=roi_data['roi_number'],
                    defaults={
                        'roi_name': original_roi_name,
                        'clean_roi_name': normalized_name,
                        'roi_of_clean_roi_name_match_tg263': roi_of_clean_roi_name_match_tg263,
                        'tg263_primary_name': tg263_primary,
                        'tg263_reverse_order_name': tg263_reverse,
                        'target_type': target_type,
                        'major_category': major_category,
                        'minor_category': minor_category,
                        'anatomic_group': anatomic_group,
                        'fma_id': str(fma_id),
                        'user_modified_name': roi_data.get('roi_observation_label', original_roi_name)
                    }
                )
                
                if not created:
                    # Update existing ROI data with normalized names and TG263 data
                    roi.roi_name = original_roi_name
                    roi.clean_roi_name = normalized_name
                    roi.roi_of_clean_roi_name_match_tg263 = roi_of_clean_roi_name_match_tg263
                    roi.tg263_primary_name = tg263_primary
                    roi.tg263_reverse_order_name = tg263_reverse
                    roi.target_type = target_type
                    roi.major_category = major_category
                    roi.minor_category = minor_category
                    roi.anatomic_group = anatomic_group
                    roi.fma_id = str(fma_id)
                    roi.user_modified_name = roi_data.get('roi_observation_label', original_roi_name)
                    roi.save()
                    
                saved_rois.append(roi)
                match_status = "MATCHED" if roi_of_clean_roi_name_match_tg263 else "NOT MATCHED"
                logging.info(f"Saved ROI: {original_roi_name} -> Normalized: {normalized_name} -> TG263 Primary: {tg263_primary} -> {match_status} (Number: {roi.roi_number})")
                
            except Exception as e:
                logging.error(f"Error saving ROI data for {original_roi_name}: {str(e)}")
                logging.error(f"ROI data: {roi_data}")
                continue
                
        return saved_rois

    def process_dicom_file(self, file_path: Path) -> Tuple[Optional[Path], Optional[str], Optional[str], Optional[Dict]]:
        """Process a single DICOM file"""
        try:
            metadata = self.get_file_metadata(file_path)
            if not metadata:
                return None, None, None, None

            # Create new filename
            new_filename = self.generate_filename(metadata)

            # Create directory structure inside patient folder
            safe_patient_id = self.clean_name(metadata['PatientID'] if metadata['PatientID'] else 'Unknown')
            if not safe_patient_id:
                safe_patient_id = 'Unknown'
            patient_path = self.destination_dir / safe_patient_id
            
            # Create study folder with date and sanitized components
            safe_study_desc = self.clean_name(metadata['StudyDescription'])[:60]
            safe_accession = self.clean_name(metadata['AccessionNumber'])[:40]
            study_folder = (f"{self._clean_text(metadata['StudyDate'], 20)}_"
                          f"{safe_study_desc}_"
                          f"{safe_accession}")

            # Create series folder with modality and series info
            safe_series_desc = self.clean_name(metadata['SeriesDescription'])[:60]
            series_folder = (f"{self._clean_text(metadata['Modality'], 20)}_"
                           f"Series{metadata['SeriesNumber']}_"
                           f"{safe_series_desc}")

            # Combine paths to create full directory structure
            full_path = patient_path / study_folder / series_folder
            try:
                full_path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                logging.error(f"Failed to create directory {full_path}: {str(e)}")
                return None, None, None, None
            
            return file_path, str(full_path), new_filename, metadata

        except Exception as e:
            logging.error(f"Error processing {file_path}: {str(e)}")
            return None, None, None, None

    def organize_files(self, num_processes: int = None):
        """Organize DICOM files in parallel"""
        if num_processes is None:
            num_processes = max(1, os.cpu_count() - 2)
        
        logging.info(f"Starting organization with {num_processes} processes...")
        logging.info(f"Source directory: {self.source_dir}")
        logging.info(f"Destination directory: {self.destination_dir}")
        logging.info(f"Upload ZIP: {self.upload_zip}")
        logging.info(f"Models available: {bool(self.models)}")
        
        # Check if source directory exists and has content
        if not self.source_dir.exists():
            logging.error(f"Source directory does not exist: {self.source_dir}")
            return
            
        # List contents of source directory
        source_contents = list(self.source_dir.iterdir())
        logging.info(f"Source directory contains {len(source_contents)} items")
        for item in source_contents[:10]:  # Show first 10 items
            logging.info(f"  - {item.name} ({'dir' if item.is_dir() else 'file'})")
        
        # Find DICOM files (now parallelized)
        dicom_files = self.find_dicom_files()
        
        if not dicom_files:
            logging.warning("No DICOM files found!")
            logging.warning("This might be because:")
            logging.warning("1. Source directory is empty")
            logging.warning("2. No DICOM files in source directory")
            logging.warning("3. Source directory path is incorrect")
            return
        
        logging.info(f"Found {len(dicom_files)} DICOM files")
        
        # For database operations, process files sequentially to avoid Django connection issues
        if self.upload_zip and self.models:
            logging.info("Database operations enabled - processing files sequentially")
            self._organize_files_sequential(dicom_files)
        else:
            logging.info("No database operations - processing files in parallel")
            self._organize_files_parallel(dicom_files, num_processes)
    
    def _organize_files_sequential(self, dicom_files):
        """Organize files sequentially with database operations"""
        files_moved = 0
        files_skipped = 0
        total_files = len(dicom_files)
        
        for file_path in dicom_files:
            old_path, new_dir, new_filename, metadata = self.process_dicom_file(file_path)
            
            if all([old_path, new_dir, new_filename, metadata]):
                try:
                    new_full_path = Path(new_dir) / new_filename
                    
                    if new_full_path.exists():
                        files_skipped += 1
                        if files_skipped % 100 == 0:
                            logging.info(f"Skipped {files_skipped} duplicate files")
                        continue
                    
                    # Copy the file
                    shutil.copy2(old_path, new_full_path)
                    files_moved += 1
                    
                    # Save to database
                    try:
                        logging.info(f"Saving database data for patient: {metadata['PatientID']}")
                        
                        # Extract directory components from the new_dir path
                        new_dir_path = Path(new_dir)
                        patient_dir = str(new_dir_path.parent.parent)  # Go up to patient level
                        study_dir = str(new_dir_path.parent)  # Go up to study level
                        series_dir = str(new_dir_path)  # This is the series level
                        
                        # Save patient data
                        patient = self.save_patient_data(metadata, patient_dir)
                        logging.info(f"Patient saved: {patient}")
                        
                        # Save study data
                        study = self.save_study_data(patient, metadata, study_dir)
                        logging.info(f"Study saved: {study}")
                        
                        # Save series data
                        series = self.save_series_data(study, metadata, series_dir)
                        logging.info(f"Series saved: {series}")
                        
                        # Save instance data
                        instance_dir = str(new_full_path)
                        instance = self.save_instance_data(series, metadata, instance_dir)
                        logging.info(f"Instance saved: {instance}")
                        
                        # If this is an RTSTRUCT file, process ROI data
                        if metadata['Modality'] == 'RTSTRUCT':
                            try:
                                logging.info(f"Processing RTSTRUCT file: {old_path}")
                                
                                # Save RTSTRUCT data
                                rtstruct = self.save_rtstruct_data(instance, metadata, instance_dir)
                                if rtstruct:
                                    logging.info(f"RTSTRUCT saved: {rtstruct}")
                                    
                                    # Extract and save ROI data
                                    roi_data_list = self.extract_roi_data(old_path)
                                    if roi_data_list:
                                        saved_rois = self.save_roi_data(rtstruct, roi_data_list)
                                        logging.info(f"Saved {len(saved_rois)} ROIs for RTSTRUCT")
                                    else:
                                        logging.warning(f"No ROI data found in RTSTRUCT file: {old_path}")
                                        
                            except Exception as roi_error:
                                logging.error(f"Error processing RTSTRUCT/ROI data for {old_path}: {str(roi_error)}")
                        
                    except Exception as db_error:
                        logging.error(f"Database error for {old_path}: {str(db_error)}")
                        import traceback
                        logging.error(f"Full traceback: {traceback.format_exc()}")
                    
                    if files_moved % 10 == 0:  # More frequent updates for sequential processing
                        percentage = (files_moved / total_files) * 100
                        logging.info(f"Progress: {percentage:.1f}% ({files_moved}/{total_files} files)")
                        
                except Exception as e:
                    logging.error(f"Error copying {old_path}: {str(e)}")
        
        logging.info(f"Sequential organization complete!")
        logging.info(f"Successfully processed {files_moved} files")
        logging.info(f"Skipped {files_skipped} duplicate files")
        logging.info(f"Files are organized in: {self.destination_dir}")
    
    def _organize_files_parallel(self, dicom_files, num_processes):
        """Organize files in parallel without database operations"""
        chunk_size = 1000
        files_moved = 0
        files_skipped = 0
        total_files = len(dicom_files)
        
        with Pool(processes=num_processes) as pool:
            for i in range(0, len(dicom_files), chunk_size):
                chunk = dicom_files[i:i + chunk_size]
                results = pool.map(self.process_dicom_file, chunk)
                
                # Process results for this chunk
                for old_path, new_dir, new_filename, metadata in results:
                    if all([old_path, new_dir, new_filename, metadata]):
                        try:
                            new_full_path = Path(new_dir) / new_filename
                            
                            if new_full_path.exists():
                                files_skipped += 1
                                if files_skipped % 100 == 0:
                                    logging.info(f"Skipped {files_skipped} duplicate files")
                                continue
                            
                            # Copy the file
                            shutil.copy2(old_path, new_full_path)
                            files_moved += 1
                            
                            if files_moved % 100 == 0:
                                percentage = (files_moved / total_files) * 100
                                logging.info(f"Progress: {percentage:.1f}% ({files_moved}/{total_files} files)")
                                
                        except Exception as e:
                            logging.error(f"Error copying {old_path}: {str(e)}")
        
        logging.info(f"Parallel organization complete!")
        logging.info(f"Successfully processed {files_moved} files")
        logging.info(f"Skipped {files_skipped} duplicate files")
        logging.info(f"Files are organized in: {self.destination_dir}")


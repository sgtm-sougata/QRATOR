#!/usr/bin/env python3
"""
Export all radiomics features to a CSV file.
Run with: python export_radiomics.py
"""
import os
import sys
import csv
from pathlib import Path

# Add the project directory to the Python path
project_root = str(Path(__file__).resolve().parent)
sys.path.append(project_root)

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'qrator.settings')

try:
    import django
except ImportError:
    print("Error: Django is not installed. Please install it with: pip install django")
    sys.exit(1)

try:
    django.setup()
    print("Successfully set up Django environment")
except Exception as e:
    print(f"Error setting up Django: {str(e)}")
    print("Please make sure you're running this from the project root directory.")
    sys.exit(1)

from app.models import RadiomicFeatures

def export_radiomics():
    # Create output directory
    output_dir = os.path.join(project_root, 'exports')
    os.makedirs(output_dir, exist_ok=True)
    
    # Get all radiomics features
    features = RadiomicFeatures.objects.all()
    count = features.count()
    
    if count == 0:
        print("No radiomics features found in the database.")
        return
    
    # Create a timestamped filename
    from datetime import datetime
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'radiomics_features_export_{timestamp}.csv'
    filepath = os.path.join(output_dir, filename)
    
    # Get field names from the model, excluding many-to-many and one-to-many relations
    field_names = []
    for field in RadiomicFeatures._meta.get_fields():
        if field.is_relation:
            if field.many_to_one or field.one_to_one:
                field_names.append(f'{field.name}_id')
        else:
            field_names.append(field.name)
    
    # Write to CSV
    with open(filepath, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=field_names)
        writer.writeheader()
        
        for feature in features:
            row = {}
            for field in RadiomicFeatures._meta.get_fields():
                if field.is_relation:
                    if field.many_to_one or field.one_to_one:
                        related_obj = getattr(feature, field.name)
                        row[f'{field.name}_id'] = str(related_obj.id) if related_obj else ''
                else:
                    value = getattr(feature, field.name)
                    row[field.name] = str(value) if value is not None else ''
            writer.writerow(row)
    
    print(f"Successfully exported {count} radiomics features to: {filepath}")

if __name__ == '__main__':
    export_radiomics()

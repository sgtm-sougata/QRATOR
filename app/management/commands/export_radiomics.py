from django.core.management.base import BaseCommand
import csv
import os
from datetime import datetime
from django.db.models.fields import Field
from app.models import RadiomicFeatures

class Command(BaseCommand):
    help = 'Export all radiomics features to a CSV file'

    def handle(self, *args, **options):
        # Create output directory
        output_dir = os.path.join(os.getcwd(), 'exports')
        os.makedirs(output_dir, exist_ok=True)
        
        # Get all radiomics features
        features = RadiomicFeatures.objects.all()
        count = features.count()
        
        if count == 0:
            self.stdout.write(self.style.WARNING('No radiomics features found in the database.'))
            return
        
        # Create a timestamped filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'radiomics_features_export_{timestamp}.csv'
        filepath = os.path.join(output_dir, filename)
        
        # Get field names from the model
        field_names = [f.name for f in RadiomicFeatures._meta.get_fields() 
                      if not f.is_relation or f.many_to_one]
        
        # Write to CSV
        with open(filepath, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=field_names)
            writer.writeheader()
            
            for feature in features:
                row = {}
                for field in field_names:
                    value = getattr(feature, field)
                    if hasattr(value, 'id'):  # Handle related objects
                        row[field] = value.id
                    else:
                        row[field] = str(value) if value is not None else ''
                writer.writerow(row)
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully exported {count} radiomics features to: {filepath}')
        )

from django.core.management.base import BaseCommand
import pandas as pd
from app.models import RadiomicFeatureMapping
import os

class Command(BaseCommand):
    help = 'Import radiomics feature mapping from CSV file'

    def handle(self, *args, **options):
        try:
            # Get the absolute path to the CSV file
            csv_path = "feature/Radiomics Feature name with descriptions.csv"
            
            # Read the CSV file
            df = pd.read_csv(csv_path)
            
            # First, delete existing mappings to avoid duplicates
            RadiomicFeatureMapping.objects.all().delete()
            
            # Create new mappings from CSV data
            mappings = []
            for _, row in df.iterrows():
                mapping = RadiomicFeatureMapping(
                    feature_name=row['feature_name'],
                    feature_class=row['Class'],
                    feature=row['Feature'],
                    description=row['Description']
                )
                mappings.append(mapping)
            
            # Bulk create all mappings
            RadiomicFeatureMapping.objects.bulk_create(mappings)
            
            self.stdout.write(
                self.style.SUCCESS(f'Successfully imported {len(mappings)} feature mappings')
            )
            
        except FileNotFoundError:
            self.stdout.write(
                self.style.ERROR(f'Could not find CSV file at {csv_path}')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error importing data: {str(e)}')
            )
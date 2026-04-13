
# from __future__ import annotations

import os  # needed navigate the system to get the input data

import radiomics
from radiomics import *
# Get the testCase
# Instantiate the extractor
from radiomics import featureextractor

# Initialize the feature extractor
extractor = featureextractor.RadiomicsFeatureExtractor()

print('Extraction parameters:\n\t', extractor.settings)
print('Enabled filters:\n\t', extractor.enabledImagetypes)
print('Enabled features:\n\t', extractor.enabledFeatures)

result = extractor.execute("output/ct.nrrd", "output/rois/Femur_Head_R.nrrd")

print('Result type:', type(result))  # result is returned in a Python ordered dictionary)
print('')
print('Calculated features')
for key, value in result.items():
    print('\t', key, ':', value)
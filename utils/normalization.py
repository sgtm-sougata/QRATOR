
import re

def capitalize_after_underscore(input_string):
    words = input_string.split("_")
    capitalized_words = [word.capitalize() for word in words]
    return "_".join(capitalized_words)

def edit_string_left(input_string):
    # Define a regular expression pattern to match the specified patterns
    pattern = r'^(left|lt|l) (.*?)$'
    
    # Use re.search to find a match
    match = re.search(pattern, input_string)
    
    if match:
        # Rearrange the matched parts of the string
        edited_string = f"{match.group(2)} L"
        return edited_string
    else:
        # If no match is found, return the original string
        return input_string

def edit_string_right(input_string):
    # Define a regular expression pattern to match the specified patterns
    pattern = r'^(right|rt|r) (.*?)$'
    
    # Use re.search to find a match
    match = re.search(pattern, input_string)
    
    if match:
        # Rearrange the matched parts of the string
        edited_string = f"{match.group(2)} R"
        return edited_string
    else:
        # If no match is found, return the original string
        return input_string    

def edit_string_left_end(input_string):
    # Define a regular expression pattern to match the specified patterns
    pattern = r'^(.*?) (left|lt|l)$'
    
    # Use re.search to find a match
    match = re.search(pattern, input_string)
    
    if match:
        # Rearrange the matched parts of the string
        edited_string = f"{match.group(1)} L"
        return edited_string
    else:
        # If no match is found, return the original string
        return input_string

def edit_string_right_end(input_string):
    # Define a regular expression pattern to match the specified patterns
    pattern = r'^(.*?) (right|rt|r)$'
    
    # Use re.search to find a match
    match = re.search(pattern, input_string)
    
    if match:
        # Rearrange the matched parts of the string
        edited_string = f"{match.group(1)} R"
        return edited_string
    else:
        # If no match is found, return the original string
        return input_string    


def clean_contour_label(label):
    """
    Cleans a contour label:
    1. Converts all characters to lowercase.
    2. Removes leading and trailing spaces.
    3. Replaces special characters with spaces.
    4. Condenses consecutive spaces into a single space.
    5. Check if there is a trailing space and remove it if it exists
    6. Converts all strings with start with left / lt / l to designate it as a left sided structure to the string l at the end separated by a space. Thus left parotid is convered to parotid l
    7. Converts all strings with start with right / rt / r to designate it as a right sided structure to the string r at the end seperated by a space. Thus right parotid is convered to parotid r
    9. Converts all spaces to underscores, except the trailing space if it exists.
    10. Capitalizes the first character after each space.
    
    Args:
    label (str): The input contour label.
    
    Returns:
    str: The cleaned contour label.
    """
    import logging
    logging.info(f"Starting ROI name normalization for: {label}")
    
    # Convert all characters to lowercase
    label = label.lower()
    
    # Remove leading and trailing spaces
    label = label.strip()

   
    # Replace special characters with spaces
    label = re.sub(r'[^\w\s]', ' ', label)
    
    # Condense consecutive spaces into a single space
    label = re.sub(r'[\s]+', ' ', label)

    # Check if there is a trailing space, and if so, remove it
    if label.endswith(' '):
        label = label[:-1]

    label = label.replace('_', ' ')
    
    # Convert all Left / Lt / L at the begining with a space after that to L at the end
    label = edit_string_left(label)
    label = edit_string_left_end(label)

    # Convert all Right / Rt / R at the begining with a space after that to R at the end
    label = edit_string_right(label)
    label = edit_string_right_end(label)
    
    # Split the label into words and capitalize the first character of each word
    words = label.split(' ')
    words = [word.capitalize() for word in words]
    
    # Concatenate the words with underscores
    label_ = '_'.join(words)
    label = capitalize_after_underscore(label_)
    
    logging.info(f"Normalized ROI name result: {label}")
    return label

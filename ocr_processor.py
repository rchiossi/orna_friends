import cv2
import pytesseract
import re
import numpy as np
from PIL import Image
import os
import pandas as pd # Import pandas for easier data handling

# --- Configuration ---
# You might need to configure the path to the tesseract executable
# Example for macOS using Homebrew: 
pytesseract.pytesseract.tesseract_cmd = r'/opt/homebrew/bin/tesseract' # <--- VERIFY THIS PATH
# Example for Windows:
# pytesseract.pytesseract.tesseract_cmd = r'C:\\Program Files\\Tesseract-OCR\\tesseract.exe'

# --- Coordinate-Based Parsing Function ---
def parse_ocr_data(ocr_dict):
    """Parses the structured OCR data (dictionary) to find username, level, and class."""
    results = []
    n_boxes = len(ocr_dict['level']) # Number of detected elements (words, lines, etc.)

    # Convert the dictionary to a pandas DataFrame for easier manipulation
    df = pd.DataFrame(ocr_dict)

    # --- Initial Filtering & Preparation ---
    # 1. Convert coordinate columns to numeric, coercing errors
    for col in ['left', 'top', 'width', 'height', 'conf']:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    # 2. Filter out low confidence words (adjust threshold as needed)
    # Increase confidence slightly? Maybe >= 50
    # df = df[df['conf'] >= 50] # Keep words with confidence >= 50
    df = df[df['conf'] >= 30] # Lower confidence threshold for PSM 11

    # 3. Filter out empty or whitespace-only text, and very short text
    df['text_stripped'] = df['text'].str.strip()
    df = df[df['text_stripped'].astype(bool) & (df['text_stripped'].str.len() > 1)]

    # 4. Filter out things that are clearly just noise symbols (like single chars remaining after strip)
    df = df[~df['text_stripped'].isin(['=', '+', '-', ';', ':', 'A', '%', '&', 'i'])]

    # 5. Calculate approximate vertical center for grouping lines
    df['v_center'] = df['top'] + df['height'] / 2

    # --- Group words into lines based on vertical proximity ---
    lines = []
    current_line = []
    last_v_center = -1
    vertical_threshold = 20 # Max vertical distance to be considered same line (Increased slightly)

    df = df.sort_values(by=['top', 'left']).reset_index()

    for index, row in df.iterrows():
        # Check horizontal distance too? Maybe not needed if crop is good.
        if not current_line or abs(row['v_center'] - last_v_center) < vertical_threshold:
            current_line.append(row)
        else:
            # Start of a new line detected
            if current_line:
                # Sort words in the completed line by horizontal position
                current_line.sort(key=lambda x: x['left'])
                lines.append({'words': current_line, # Store individual words too
                                'text': ' '.join([word['text_stripped'] for word in current_line]), 
                                'top': min(word['top'] for word in current_line),
                                'bottom': max(word['top'] + word['height'] for word in current_line)}) 
            current_line = [row]
        # Use the first word's v_center as the line's reference v_center
        if current_line:
             last_v_center = current_line[0]['v_center'] 
        
    # Add the last line
    if current_line:
        current_line.sort(key=lambda x: x['left'])
        lines.append({'words': current_line,
                        'text': ' '.join([word['text_stripped'] for word in current_line]), 
                        'top': min(word['top'] for word in current_line),
                        'bottom': max(word['top'] + word['height'] for word in current_line)}) 

    # Pre-filter lines that are just dates before pairing logic
    # Use search instead of match to find date anywhere in the line
    date_pattern = re.compile(r"\d{1,2}/\d{1,2}/\d{4}") 
    filtered_lines = [line for line in lines if not date_pattern.search(line['text'])]

    # print("\n--- Filtered Lines (Coordinate-based, No Dates) ---")
    # for line in filtered_lines: print(f"{line['text']} (Top: {line['top']})")
    # print("--- End Filtered Lines ---")

    # --- Identify Player Entries by Finding Level line and looking back ---
    processed_username_indices = set()
    for i, line in enumerate(filtered_lines):
        # Check if the current line looks like a Level/Class line
        level_class_match = re.search(r"(?:Level|Lavel|LeveL|lavel|Seeelevcle)\s*(\d{1,3})\s+(.+)", line['text'], re.IGNORECASE)
        
        if level_class_match:
            level = int(level_class_match.group(1))
            class_name_raw = level_class_match.group(2).strip()
            
            # Attempt to clean class name (remove trailing noise)
            class_match = re.match(r"([a-zA-Z][a-zA-Z\s]+)", class_name_raw)
            class_name = class_match.group(1).strip() if class_match else class_name_raw
            if class_name.lower() == "snelleward": class_name = "Spellsword" # Correction
            
            # Check level sanity
            if 1 <= level <= 300:
                # Now look backwards for the closest plausible username line above it
                username_candidate = None
                username_line_index = -1
                min_vertical_gap = float('inf')

                # print(f"\nFound Level line {i}: {line['text']}") # DEBUG
                for j in range(i - 1, -1, -1):
                    potential_username_line = filtered_lines[j]
                    # print(f"  Checking previous line {j}: {potential_username_line['text']}") # DEBUG
                    # Check if already used
                    if j in processed_username_indices:
                        # print(f"    Skipping line {j}: Already used as username") # DEBUG
                        continue 
                        
                    # Check vertical gap 
                    vertical_gap = line['top'] - potential_username_line['bottom']
                    line_gap_threshold = 75 # Allow slightly larger gap now (Increased again)
                    # print(f"    Vertical Gap: {vertical_gap:.1f} (Threshold: {line_gap_threshold})" ) # DEBUG
                    
                    # Basic plausibility checks (not a level line, not search, decent length)
                    is_plausible = ("level" not in potential_username_line['text'].lower() and \
                                    len(potential_username_line['text']) > 1 and \
                                    "Search..." not in potential_username_line['text'] and \
                                    "Allies" not in potential_username_line['text'])
                    # print(f"    Is Plausible Username? {is_plausible}") # DEBUG

                    if is_plausible and 0 < vertical_gap < line_gap_threshold:
                         # print(f"    Found Plausible Candidate at index {j}") # DEBUG
                         # Found a plausible candidate, store it and its index
                         # More refined username cleaning: remove leading noise like '+ '
                         raw_username = potential_username_line['text']
                         cleaned_username = re.sub(r"^[+=%&;:\s]*", "", raw_username).strip()
                         if len(cleaned_username) > 1: # Ensure something remains after cleaning
                             username_candidate = cleaned_username
                             username_line_index = j
                             # print(f"    Stored Username: '{username_candidate}'") # DEBUG
                             break # Found the closest one, stop searching backwards
                         # else:
                             # print(f"    Username '{raw_username}' became empty after cleaning.") #DEBUG
                    # elif is_plausible and vertical_gap >= line_gap_threshold:
                         # print(f"    Skipping line {j}: Gap too large.") # DEBUG
                         # Optimization: If gap is already too large, lines further up will also be too large
                         # break # (Optional optimization)
                    # elif not is_plausible:
                        # print(f"    Skipping line {j}: Not plausible username.") # DEBUG


                # If we found a valid username
                if username_candidate and username_line_index != -1:
                    # Final check for duplicates
                    is_duplicate = False
                    for entry in results:
                        if entry['username'] == username_candidate and entry['level'] == level:
                            is_duplicate = True
                            break
                            
                    if not is_duplicate:
                        results.append({
                            'username': username_candidate,
                            'level': level,
                            'class': class_name
                        })
                        processed_username_indices.add(username_line_index) # Mark as used
            
    return results

# --- Main Extraction Function ---
def extract_data(image_path):
    """Extracts player data from the provided image path using coordinate-based OCR data."""
    try:
        # 1. Use PIL to open and crop the image 
        img_pil = Image.open(image_path)
        width, height = img_pil.size
        # Using the original crop estimate, adjust if needed
        crop_area = (0, int(height * 0.1), int(width * 0.7), int(height * 0.8)) 
        cropped_img_pil = img_pil.crop(crop_area)

        # 2. Preprocessing using OpenCV on the cropped image
        # Convert PIL Image to OpenCV format (NumPy array)
        cropped_img_cv = cv2.cvtColor(np.array(cropped_img_pil), cv2.COLOR_RGB2BGR)
        
        # Convert to grayscale
        gray_cv = cv2.cvtColor(cropped_img_cv, cv2.COLOR_BGR2GRAY)
        
        # Upscale the image (e.g., 1.5x)
        scale_factor = 1.5
        width = int(gray_cv.shape[1] * scale_factor)
        height = int(gray_cv.shape[0] * scale_factor)
        dim = (width, height)
        resized_cv = cv2.resize(gray_cv, dim, interpolation = cv2.INTER_LANCZOS4) # Use Lanczos for quality

        # Apply Otsu's thresholding
        _ , processed_cv = cv2.threshold(resized_cv, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # Save preprocessed image for debugging (optional)
        # cv2.imwrite("preprocessed_debug.png", processed_cv)
        
        # Convert processed OpenCV image back to PIL format for pytesseract if needed
        # Although pytesseract can often handle numpy arrays directly
        # processed_img_pil = Image.fromarray(processed_cv)

        # 3. Perform OCR on the preprocessed image, getting detailed data
        # Updated config: OEM 1 (LSTM), PSM 11 (Sparse), Disable Dictionaries
        custom_config = r'--oem 1 --psm 11 -c load_system_dawg=0 -c load_freq_dawg=0' 
        
        # Pass the processed OpenCV image (numpy array) directly
        ocr_data = pytesseract.image_to_data(processed_cv, config=custom_config, output_type=pytesseract.Output.DICT)
        
        # 4. Parse the structured OCR data
        extracted_info = parse_ocr_data(ocr_data)
        
        return extracted_info

    except FileNotFoundError:
        print(f"Error: Image file not found at {image_path}")
        return []
    except pytesseract.TesseractNotFoundError:
        print("Error: Tesseract is not installed or not in your PATH.")
        print("Please install Tesseract and configure the path in ocr_processor.py if needed.")
        raise 
    except ImportError:
        print("Error: pandas library not found. Please install it: pip install pandas")
        raise
    except Exception as e:
        print(f"An error occurred during coordinate-based OCR processing: {e}")
        # import traceback
        # traceback.print_exc()
        return []

# Example usage (for testing):
if __name__ == '__main__':
    # Use the actual image path provided
    test_image_path = 'images/Screenshot_2025-03-31-09-44-48-24_fba058fbcaeda824c55dd11029f3cefb.jpg' 
    if os.path.exists(test_image_path):
        print(f"Processing image: {test_image_path}")
        data = extract_data(test_image_path)
        print("\n--- Extracted Data (Coordinate-based) ---")
        if data:
            for item in data:
                print(item)
        else:
            print("No data extracted.")
    else:
        print(f"Test image not found: {test_image_path}")
        print("Skipping direct execution example.") 
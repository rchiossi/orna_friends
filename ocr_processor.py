import cv2
import pytesseract
import re
import numpy as np
from PIL import Image
import os
import pandas as pd # Import pandas for easier data handling
import easyocr # Import easyocr

# --- Configuration ---
# You might need to configure the path to the tesseract executable
# Example for macOS using Homebrew: 
pytesseract.pytesseract.tesseract_cmd = r'/opt/homebrew/bin/tesseract' # <--- VERIFY THIS PATH
# Example for Windows:
# pytesseract.pytesseract.tesseract_cmd = r'C:\\Program Files\\Tesseract-OCR\\tesseract.exe'

# --- DELETED Tesseract-based functions (extract_data, parse_ocr_data) --- 


# --- Implementation using easyocr --- 

# Initialize EasyOCR Reader (do this once, ideally outside the function if called repeatedly)
# This will download models on first run
# reader = easyocr.Reader(['en']) # Add other languages if needed e.g., ['en', 'fr']

def extract_data_easyocr(image_path):
    """Extracts player data using EasyOCR."""
    try:
        # Initialize reader here for simplicity in testing
        # Consider moving initialization outside for efficiency in real app
        # print("Initializing EasyOCR Reader...") # DEBUG
        # Specify gpu=False if you don't have a compatible GPU or CUDA installed
        reader = easyocr.Reader(['en'], gpu=False) 
        # print("EasyOCR Reader Initialized.") # DEBUG
        
        # 1. Use PIL to open and crop the image (same as Tesseract version)
        img_pil = Image.open(image_path)
        width, height = img_pil.size
        crop_area = (0, int(height * 0.1), int(width * 0.7), int(height * 0.8))
        cropped_img_pil = img_pil.crop(crop_area)
        
        # Convert PIL image to format easyocr needs (numpy array or filepath)
        # Using numpy array from PIL image:
        cropped_img_np = np.array(cropped_img_pil)

        # 2. Perform OCR using EasyOCR
        # print(f"Running EasyOCR on {image_path}...") # DEBUG
        ocr_results = reader.readtext(cropped_img_np, detail=1, paragraph=False) # paragraph=False gives word boxes
        # print(f"EasyOCR finished. Found {len(ocr_results)} text blocks.") # DEBUG
        
        # --- Parse EasyOCR results --- 
        
        # 1. Process raw results into a DataFrame
        results_list = []
        for (bbox, text, prob) in ocr_results:
            tl, tr, br, bl = bbox
            left = int(min(tl[0], bl[0]))
            top = int(min(tl[1], tr[1]))
            right = int(max(tr[0], br[0]))
            bottom = int(max(bl[1], br[1]))
            v_center = top + (bottom - top) / 2
            h_center = left + (right - left) / 2
            results_list.append({
                'left': left, 'top': top, 'right': right, 'bottom': bottom,
                'v_center': v_center, 'h_center': h_center,
                'text': text.strip(), 
                'conf': prob
            })
        
        if not results_list:
            return [] 
            
        df = pd.DataFrame(results_list)

        # 2. Filter noise 
        min_confidence = 0.30 
        df = df[df['conf'] >= min_confidence]
        df = df[df['text'].str.len() > 0] 

        # Sort by vertical then horizontal position
        df_sorted = df.sort_values(by=['top', 'left']).reset_index(drop=True)

        # --- Removed full DataFrame print --- 

        # print(f"EasyOCR: Filtered down to {len(df_sorted)} high-confidence text blocks.") # DEBUG

        # --- Steps 3-6: Find Level, Username, Combine, Store --- 
        parsed_data = []
        processed_indices = set() 
        level_keywords = ["level", "lavel", "leveel", "ievei"]

        for index, row in df_sorted.iterrows():
            if index in processed_indices:
                continue

            # 3. Find Level Keyword (Check if text block STARTS with Level)
            if row['text'].lower().startswith('level'): 
                level_word = row
                # print(f"  [EasyOCR DEBUG] Found Potential Level Block: '{level_word['text']}' at index {index}") # DEBUG 
                
                level_val = None
                class_name = None
                number_word = None 
                class_words = [] 

                match = re.search(r"Level\s*(\d{1,3})\s*(.*)", level_word['text'], re.IGNORECASE)
                if match:
                    level_val = int(match.group(1))
                    class_name_raw = match.group(2).strip()
                    if class_name_raw: 
                        class_name = class_name_raw
                        number_word = level_word 
                        class_words = [level_word] 
                        # print(f"    [EasyOCR DEBUG] Parsed L={level_val}, C='{class_name}' from same block.") # DEBUG
                
                if level_val is not None and class_name is None:
                    num_match_inline = re.search(r"Level\s*(\d{1,3})", level_word['text'], re.IGNORECASE)
                    if num_match_inline and level_val == int(num_match_inline.group(1)):
                        number_word = level_word 
                        # print(f"    [EasyOCR DEBUG] Found Number {level_val} in Level block.") # DEBUG
                    
                    if number_word is not None:
                        class_words_separate = [] 
                        last_class_word = number_word 
                        # print(f"      [EasyOCR DEBUG] Coords for {number_word['text']} (Index {number_word.name}): T={number_word['top']}, B={number_word['bottom']}, L={number_word['left']}, R={number_word['right']}") # DEBUG
                        nw_idx = number_word.name 
                        nw_bottom = number_word['bottom']
                        nw_right = number_word['right']
                        potential_classes_candidates = df_sorted.loc[
                            # (df_sorted.index > nw_idx) & # REMOVED
                            (df_sorted['top'] < nw_bottom + 25) & 
                            (df_sorted['left'] > nw_right - 20) & 
                            (df_sorted['left'] < nw_right + 210) 
                        ]
                        # print(f"      [EasyOCR DEBUG] Found {len(potential_classes_candidates)} candidates before head(5). First few: \n{potential_classes_candidates.head()}") # DEBUG
                        potential_classes = potential_classes_candidates.head(5) 

                        # print(f"      [EasyOCR DEBUG] Potential class DF size (after head): {len(potential_classes)}") # DEBUG
                        for cls_idx, cls_row in potential_classes.iterrows():
                            h_gap = cls_row['left'] - last_class_word['right']
                            # print(f"        [EasyOCR DEBUG] Checking word '{cls_row['text']}' (Index: {cls_idx}). H gap: {h_gap:.1f}") # DEBUG
                            if h_gap < 40: 
                                class_words_separate.append(cls_row)
                                last_class_word = cls_row
                                # print(f"          [EasyOCR DEBUG] Added '{cls_row['text']}' to separate class words.") # DEBUG
                            else:
                                # print(f"          [EasyOCR DEBUG] H gap too large. Stopping class search.") # DEBUG
                                break
                        
                        if class_words_separate: 
                            class_name = " ".join([cw['text'] for cw in class_words_separate])
                            class_words = class_words_separate 
                            # print(f"    [EasyOCR DEBUG] Found Class '{class_name}' in separate block(s). L={level_val}") # DEBUG

                if level_val is not None and class_name is not None and number_word is not None and class_words: 
                     # print(f"  [EasyOCR DEBUG] Confirmed Block: L={level_val} C='{class_name}'") # DEBUG
                     processed_indices.add(level_word.name) 
                     processed_indices.add(number_word.name) 
                     for cw in class_words:
                         processed_indices.add(cw.name)

                     search_bottom = min(level_word['top'], number_word['top']) - 5 
                     search_top = search_bottom - 170 
                     search_left = 0
                     search_right = max(level_word['right'], number_word['right'], class_words[-1]['right']) + 50
                     
                     username_candidates_df = df_sorted[
                         (df_sorted['bottom'] <= search_bottom) &
                         (df_sorted['top'] >= search_top) &
                         (df_sorted['right'] >= search_left) &
                         (df_sorted['left'] <= search_right) &
                         (~df_sorted.index.isin(processed_indices))
                     ].copy() 

                     username = None
                     username_indices = []
                     if not username_candidates_df.empty:
                         username_candidates_df['line_group'] = (username_candidates_df['v_center'].diff().abs() > 15).cumsum()
                         grouped = username_candidates_df.groupby('line_group')
                         
                         potential_usernames = []
                         for name, group in grouped:
                             sorted_group = group.sort_values('left')
                             potential_usernames.append({
                                 'text': ' '.join(sorted_group['text']), 
                                 'indices': sorted_group.index.tolist(),
                                 'bottom': sorted_group['bottom'].max(),
                                 'top': sorted_group['top'].min()
                             })

                         best_u_line = None
                         min_u_gap = float('inf')
                         if potential_usernames: 
                             # print(f"    [EasyOCR DEBUG] Found {len(potential_usernames)} potential username lines above.") # DEBUG 
                             for u_line in potential_usernames:
                                 gap = level_word['top'] - u_line['bottom']
                                 if 0 < gap < min_u_gap:
                                     min_u_gap = gap
                                     best_u_line = u_line
                             
                         if best_u_line:
                             # print(f"      [EasyOCR DEBUG] Selected best username line: '{best_u_line['text']}'") # DEBUG 
                             raw_username = best_u_line['text']
                             username_indices = best_u_line['indices']
                             best_u_line_top = best_u_line['top']
                             best_u_line_bottom = best_u_line['bottom']
                             
                             combined_u_line = False
                             best_u_line_group_idx = username_candidates_df.loc[best_u_line['indices'][0]]['line_group'] 
                             line_above = None
                             for u_line in potential_usernames:
                                 if username_candidates_df.loc[u_line['indices'][0]]['line_group'] == best_u_line_group_idx - 1:
                                     line_above = u_line
                                     break
                             
                             if line_above and line_above['text'].endswith('-'):
                                 gap_between = best_u_line_top - line_above['bottom']
                                 combine_threshold_revised = 90 
                                 if 0 < gap_between < combine_threshold_revised:
                                     # print(f"      [EasyOCR DEBUG] Combining line above '{line_above['text']}' with selected line '{best_u_line['text']}' due to hyphen.") # DEBUG
                                     raw_username = line_above['text'].rstrip() + best_u_line['text'] 
                                     username_indices = line_above['indices'] + best_u_line['indices']
                                     processed_indices.update(line_above['indices']) 
                                     combined_u_line = True

                             cleaned_username = re.sub(r"^[^a-zA-Z0-9\[\]]*", "", raw_username).strip()
                             cleaned_username = re.sub(r"[^a-zA-Z0-9-]*$", "", cleaned_username).strip() 
                             if '"' in cleaned_username and ' ' in cleaned_username:
                                 parts = cleaned_username.split(' ')
                                 if len(parts) > 1 and parts[-1]: cleaned_username = parts[-1]

                             if len(cleaned_username) > 1:
                                 username = cleaned_username
                                 # print(f"        [EasyOCR DEBUG] Final Cleaned Username: '{username}'") # DEBUG 

                     if username:
                         is_duplicate = False
                         for entry in parsed_data:
                             if entry['username'] == username and entry['level'] == level_val:
                                 is_duplicate = True
                                 break
                         if not is_duplicate:
                             # print(f"          [EasyOCR DEBUG] Appending result: {username}, {level_val}, {class_name}") # DEBUG 
                             parsed_data.append({
                                 'username': username,
                                 'level': level_val,
                                 'class': class_name
                             })
                             for idx in username_indices:
                                 processed_indices.add(idx)

        return parsed_data

    except ImportError:
        print("Error: easyocr library not found or dependencies missing.")
        print("Please install it: pip install easyocr")
        print("(This might also download PyTorch/TensorFlow based on your system)")
        return [] 
    except Exception as e:
        print(f"An error occurred during EasyOCR processing: {e}")
        import traceback
        traceback.print_exc()
        return []

# Example usage (for testing):
if __name__ == '__main__':
    # Use the actual image path provided
    # test_image_path = 'images/Screenshot_2025-03-31-09-44-48-24_fba058fbcaeda824c55dd11029f3cefb.jpg' # First image
    test_image_path = 'images/Screenshot_2025-03-31-10-43-07-78_fba058fbcaeda824c55dd11029f3cefb.jpg' # Second image
    if os.path.exists(test_image_path):
        # print(f"\n--- Processing with Tesseract ({test_image_path}) ---") # Removed Tesseract Call
        # data_tesseract = extract_data(test_image_path)
        # print("\n--- Extracted Data (Tesseract - Line-based - Final) ---")
        # if data_tesseract:
        #     for item in data_tesseract:
        #         print(item)
        # else:
        #     print("No data extracted.")
            
        print(f"\n--- Processing with EasyOCR ({test_image_path}) ---")
        data_easyocr = extract_data_easyocr(test_image_path)
        print("\n--- Extracted Data (EasyOCR - Final) ---") # Updated title
        if data_easyocr:
            for item in data_easyocr:
                print(item)
        else:
            print("No data extracted.") # Updated message
            
    else:
        print(f"Test image not found: {test_image_path}")
        print("Skipping direct execution example.")

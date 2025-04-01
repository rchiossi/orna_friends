import cv2
import pytesseract
import re
import numpy as np
from PIL import Image
import os
import pandas as pd # Import pandas for easier data handling
import easyocr # Import easyocr

CLASSES = [
    # Image 1
    "Mage", "Thief", "Warrior", "Archmage", "Witch", "Footsoldier", "Frost Mage",
    "Knight", "Knightess", "Legionnaire", "Paladin", "Valkyrie", "Royal Guard", 
    "Rune Knight", "Rune Knightess", "Scorcher", "Scorchess", "Storm Knight", 
    "Storm Valkyrie", "Strider", "Wanderer", "Wanderess", "Warlock", "Battle Master", 
    "Centurion", "Conjuror", "Conjuress", "Court Mage", "Handler", "Phalanx", 
    "Shadowmaker", "Sorcerer", "Sorceress",
    
    # Image 2
    "Squire", "Warlord", "Augur", "Gladiator", "Lancer", "Mystic", "Runeblade", 
    "Spellsword", "Wolf Tamer", "Cavalry", "Dragoon", "Dragoness", "Druid", 
    "Majestic", "Spirit Tamer",
    
    # Image 3
    "Battlemage", "Blademaster", "Dragoon", "Valkyrie", "Grand Mystic", "Shadowmancer", 
    "Spellweaver", "Templar", "Archdruid", "Attuner", "Grand Dragoon", "Grand Valkyrie", 
    "Majistrate", "Paladin", "Arcanic", "Atlas Vanguard", "Athena Vanguard", "Freyr", 
    "Freyja", "Gaia", "Grand Attuner", "Ifrit",
    
    # Image 4
    "Leviathan", "Nekromancer", "Nekromagus", "Taranis", "Bahamut", "Grand Ifrit", 
    "Great Leviathan", "High Taranis", "Noble Gaia", "Nyx", "Omnimancer", "Omnimagus", 
    "Summoner", "Titanguard", "Beowulf", "Bestla", "Deity", "Gilgamesh", "Gallia", 
    "Grand Summoner", "Heretic", "Hera", "Realmshifter",

    # Celestial T10
    "Grand Summoner Auriga", "Grand Summoner Hydron",
    "Beowulf Hydrus", "Bestla Hydrus", "Beowulf Auriga", "Bestla Auriga",
    "Deity Ara", " Deity Ursa",
    "Gilgamesh Hercules", "Gallia Hercules", "Gilgamesh Ursa", "Gallia Ursa",
    "Heretic Ara", "Hera Ara", "Heretic Corvus", "Hera Corvus",
    "Realmshifter Corvus", "Realmshifter Dorado",

    # Celestial T9
    "Bahamut Auriga", "Bahamut Hydrus",
    "Nyx Corvus", " Nyx Hercules",
    "Omnimancer Ara", "Omnimagus Ara", " Omnimancer Antlia, Omnimagus Antlia",
    "Summoner Hydrus", "Summoner Auriga",
    "Titanguard Ursa", "Titanguard Hercules",

    # Premium
    "Frost Mage", "Legionnaire", "Royal Guard", "Rune Knight", "Scorcher",
    "Storm Knight", "Wanderer", "Warlock", "Conjuror", "Phalanx", "Warlord",
    "Augur", "Gladiator", "Runeblade"
]

# --- Implementation using easyocr --- 

# Initialize EasyOCR Reader (do this once, ideally outside the function if called repeatedly)
# This will download models on first run
# reader = easyocr.Reader(['en']) # Add other languages if needed e.g., ['en', 'fr']

def get_ocr_results(image_path):
    """Extracts player data using EasyOCR."""
    # Initialize reader here for simplicity in testing
    # Consider moving initialization outside for efficiency in real app
    # Specify gpu=False if you don't have a compatible GPU or CUDA installed
    reader = easyocr.Reader(['en'], gpu=False) 
    
    # 1. Use PIL to open and crop the image (same as Tesseract version)
    img_pil = Image.open(image_path)
    width, height = img_pil.size
    # Adjust crop area based on user feedback
    # crop_area = (0, int(height * 0.1), int(width * 0.7), int(height * 0.8)) # Old values
    crop_area = (int(width * 0.14), int(height * 0.18), int(width * 0.51), int(height * 0.75)) # New values
    cropped_img_pil = img_pil.crop(crop_area)
    
    # --- Add code to save the processed image ---
    processed_dir = "processed_images"
    if not os.path.exists(processed_dir):
        os.makedirs(processed_dir)
    base_filename = os.path.basename(image_path)
    name, ext = os.path.splitext(base_filename)
    processed_filename = f"{name}_processed{ext}"
    processed_save_path = os.path.join(processed_dir, processed_filename)
    try:
        cropped_img_pil.save(processed_save_path)
        # print(f"Saved processed image to: {processed_save_path}") # Optional: uncomment for confirmation
    except Exception as save_err:
        print(f"Warning: Could not save processed image to {processed_save_path}: {save_err}")
    # --- End save code ---

    # Convert PIL image to format easyocr needs (numpy array or filepath)
    # Using numpy array from PIL image:
    cropped_img_np = np.array(cropped_img_pil)

    # 2. Perform OCR using EasyOCR
    ocr_results = reader.readtext(cropped_img_np, detail=1, paragraph=False) # paragraph=False gives word boxes

    return ocr_results

def extract_data_easyocr(image_path):
    """
    Extracts player data (username, level, class) from an image using EasyOCR,
    relying on the sequential order of text elements after sorting.
    """
    ocr_results = get_ocr_results(image_path)

    # 1. Process raw results into a DataFrame
    results_list = []
    for (bbox, text, prob) in ocr_results:
        tl, tr, br, bl = bbox
        left = int(min(tl[0], bl[0]))
        top = int(min(tl[1], tr[1]))
        # Get vertical center for sorting primarily by line
        v_center = top + (bottom - top) / 2 if 'bottom' in locals() else top # Handle potential undefined variable
        results_list.append({
            'left': left, 
            'top': top, 
            'v_center': v_center, # Use v_center for potentially better line grouping
            'text': text.strip(), 
            'conf': prob
        })
    
    if not results_list:
        print("EasyOCR returned no results.")
        return [] 
        
    df = pd.DataFrame(results_list)

    # 2. Filter noise 
    min_confidence = 0.30 
    df = df[df['conf'] >= min_confidence]
    df = df[df['text'].str.len() > 0] 
    
    if df.empty:
        print("No text passed confidence threshold.")
        return []

    # 3. Sort by vertical position (approximating lines), then horizontal
    # Using 'top' directly might be sufficient if v_center calculation was problematic
    df_sorted = df.sort_values(by=['top', 'left']).reset_index(drop=True)
    df_sorted = df

    # --- New Logic: Process Tokens Sequentially ---
    tokens_raw = df_sorted['text'].tolist()

    # Join and re-split to get individual words
    full_text = " ".join(tokens_raw)
    tokens = full_text.split(' ')
    # Filter out empty strings that can result from multiple spaces
    tokens = [token for token in tokens if token]

    # --- Pre-process Tokens: Merge Multi-word Class Names ---
    # Create sets for faster lookups (lowercase)
    classes_lower = {c.lower() for c in CLASSES}
    two_word_classes = {c.lower() for c in classes_lower if " " in c and len(c.split()) == 2}
    three_word_classes = {c.lower() for c in classes_lower if " " in c and len(c.split()) == 3} # e.g., Battle Master

    processed_tokens = []
    i = 0
    while i < len(tokens):
        # Check for 3-word classes first
        if i + 2 < len(tokens):
            potential_3_word = f"{tokens[i]} {tokens[i+1]} {tokens[i+2]}".lower()
            if potential_3_word in three_word_classes:
                # Find original casing from CLASSES list
                original_class = next((c for c in CLASSES if c.lower() == potential_3_word), f"{tokens[i]} {tokens[i+1]} {tokens[i+2]}")
                processed_tokens.append(original_class)
                i += 3
                continue # Skip to next iteration

        # Check for 2-word classes
        if i + 1 < len(tokens):
            potential_2_word = f"{tokens[i]} {tokens[i+1]}".lower()
            if potential_2_word in two_word_classes:
                 # Find original casing from CLASSES list
                original_class = next((c for c in CLASSES if c.lower() == potential_2_word), f"{tokens[i]} {tokens[i+1]}")
                processed_tokens.append(original_class)
                i += 2
                continue # Skip to next iteration
        
        # If not part of a multi-word class, add the single token
        processed_tokens.append(tokens[i])
        i += 1

    state = "username"
    data = {'username': '', 'level': 0, 'class': ''}
    extracted_data = []
    for index, token in enumerate(processed_tokens):
        if state == "username":
            if token.lower().startswith('level'):
                if index < len(processed_tokens) - 1 and processed_tokens[index + 1].isdigit():
                    state = "level"
                else:
                    state = "class"
            else:
                data['username'] += ' ' + token
        elif state == "level":
            if token.isdigit():
                data['level'] = int(token)
            state = "class"
        else:
            data['class'] += token

            if len(data['username']) != 0 and len(data['class']) != 0:
                 extracted_data.append(data)
            else:
                print(f"[Warning] Could not extract complete data: U='{data['username']}', L={data['level']}, C='{data['class']}'")    

            data = {'username': '', 'level': 0, 'class': ''}

            state = "username"

    return extracted_data # Return the list (potentially empty)


# Example usage (for testing):
if __name__ == '__main__':
    # Use the actual image path provided
    # test_image_path = 'images/Screenshot_2025-03-31-09-44-48-24_fba058fbcaeda824c55dd11029f3cefb.jpg' # First image
    test_image_path = 'images/Screenshot_2025-03-31-10-43-07-78_fba058fbcaeda824c55dd11029f3cefb.jpg' # Second image
    if os.path.exists(test_image_path):
        print(f"\n--- Processing with EasyOCR ({test_image_path}) ---")
        # Ensure we call the NEW function
        data_easyocr = extract_data_easyocr(test_image_path) 
        print("\n--- Extracted Data (EasyOCR - Sequential - Final) ---") # Updated title
        if data_easyocr:
            for item in data_easyocr:
                print(item)
        else:
            print("No data extracted.") # Updated message
            
    else:
        print(f"Test image not found: {test_image_path}")
        print("Skipping direct execution example.")

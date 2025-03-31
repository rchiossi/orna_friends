import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
import database
import ocr_processor
import os
import traceback # Import traceback for detailed error logging
import datetime
# import pytesseract # Removed - No longer used
import io # To handle image blob data
import tksheet # Import tksheet

class AppGUI:
    def __init__(self, master):
        self.master = master
        master.title("Orna Friends Extractor")
        # Increased initial size slightly to accommodate new layout
        master.geometry("900x650") 

        # Initialize database
        database.init_db()

        # --- Variables --- 
        self.current_image_path = None
        self.current_pil_image = None
        self.current_image_id = None # ID of image loaded in processing tab
        self.last_extracted_data = [] # Store raw OCR results before editing
        self.tree_data_map = {} # Store treeview item ID -> (image_id, file_path)
        self.manage_tab_image_id = None # ID of image context in manage tab
        self.manage_tab_file_path = None
        self.image_listbox_map = {} # Map listbox index to image_id/path
        self.bulk_folder_path = None # Path for bulk processing
        self.bulk_image_files = [] # List of image file paths in bulk folder
        self.bulk_results_map = {} # Map filepath -> extracted data list
        self.bulk_listbox_map = {} # Map listbox index -> filepath
        self.bulk_selected_filepath = None # Currently selected file in bulk list

        # Sorting state for the main data treeview
        self.tree_sort_column = 'Extraction Date' # Default sort column
        self.tree_sort_direction = 'desc' # Default sort direction

        # --- Create Tabs --- 
        self.notebook = ttk.Notebook(master)
        self.notebook.pack(pady=10, padx=10, expand=True, fill="both")

        # --- Tab 1: Image Processing ---
        self.processing_tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(self.processing_tab, text="Image Processing")
        # Configure columns for the processing tab grid (0: Left Panel, 1: Right Panel)
        self.processing_tab.columnconfigure(0, weight=1) 
        self.processing_tab.columnconfigure(1, weight=2) # Give more weight to the sheet panel
        self.processing_tab.rowconfigure(0, weight=1) # Allow panels to expand vertically

        # --- Left Panel (in Tab 1): Image Selection and Display ---
        self.left_panel = ttk.Frame(self.processing_tab, padding="10")
        self.left_panel.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)

        self.select_button = ttk.Button(self.left_panel, text="Select Image", command=self.select_image)
        self.select_button.grid(row=0, column=0, pady=5, sticky=tk.W)

        self.image_canvas = tk.Canvas(self.left_panel, bg='lightgrey', width=300, height=400)
        self.image_canvas.grid(row=1, column=0, pady=10, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.left_panel.rowconfigure(1, weight=1) # Allow canvas to expand

        self.process_button = ttk.Button(self.left_panel, text="Process Image", command=self.trigger_ocr_processing, state=tk.DISABLED)
        self.process_button.grid(row=2, column=0, pady=5, sticky=tk.W)

        self.status_label = ttk.Label(self.left_panel, text="Select an image file.", wraplength=300)
        self.status_label.grid(row=3, column=0, pady=5, sticky=tk.W)

        # --- Right Panel (in Tab 1): Editable Data Sheet & Save ---
        self.edit_panel = ttk.Frame(self.processing_tab, padding="10")
        self.edit_panel.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)
        
        ttk.Label(self.edit_panel, text="Extracted/Edit Data:").grid(row=0, column=0, columnspan=2, pady=5, sticky=tk.W)

        # Create Sheet Widget
        self.data_sheet = tksheet.Sheet(self.edit_panel,
                                        headers=["Username", "Level", "Class"],
                                        height=400, # Adjust height as needed
                                        width=450) # Adjust width as needed
        self.data_sheet.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.data_sheet.enable_bindings() # Enable default bindings (copy, paste, etc.)
        # Configure column widths (optional)
        self.data_sheet.column_width(column=0, width=200)
        self.data_sheet.column_width(column=1, width=70)
        self.data_sheet.column_width(column=2, width=150)

        self.save_button = ttk.Button(self.edit_panel, text="Save All Data from Sheet", command=self.save_proc_tab_data, state=tk.DISABLED)
        self.save_button.grid(row=2, column=0, columnspan=2, pady=10)

        self.edit_panel.columnconfigure(1, weight=1) # Allow entry fields to expand

        # --- Tab 2: Bulk Processing ---
        self.bulk_tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(self.bulk_tab, text="Bulk Processing")
        # Configure columns: 0 listbox, 1 image canvas, 2 sheet/buttons
        self.bulk_tab.columnconfigure(0, weight=1) 
        self.bulk_tab.columnconfigure(1, weight=1) 
        self.bulk_tab.columnconfigure(2, weight=2) 
        self.bulk_tab.rowconfigure(1, weight=1) # Allow image list/canvas/sheet row to expand

        # --- Top Bar (in Tab 4): Folder Select ---
        self.bulk_top_bar = ttk.Frame(self.bulk_tab)
        self.bulk_top_bar.grid(row=0, column=0, columnspan=3, sticky=(tk.W, tk.E), padx=5, pady=5)
        self.bulk_select_folder_button = ttk.Button(self.bulk_top_bar, text="Select Folder...", command=self.select_bulk_folder)
        self.bulk_select_folder_button.pack(side=tk.LEFT, padx=5)
        self.bulk_folder_label = ttk.Label(self.bulk_top_bar, text="No folder selected.")
        self.bulk_folder_label.pack(side=tk.LEFT, padx=5)
        
        # --- Listbox Panel (in Tab 4) ---
        self.bulk_listbox_panel = ttk.Frame(self.bulk_tab, padding="5")
        self.bulk_listbox_panel.grid(row=1, column=0, sticky=(tk.N, tk.S, tk.W, tk.E), padx=5, pady=5)
        self.bulk_listbox_panel.rowconfigure(0, weight=1)
        self.bulk_listbox_panel.columnconfigure(0, weight=1)
        self.bulk_image_listbox = tk.Listbox(self.bulk_listbox_panel, exportselection=False)
        self.bulk_image_listbox.grid(row=0, column=0, sticky=(tk.N, tk.S, tk.W, tk.E))
        bulk_listbox_scrollbar = ttk.Scrollbar(self.bulk_listbox_panel, orient=tk.VERTICAL, command=self.bulk_image_listbox.yview)
        bulk_listbox_scrollbar.grid(row=0, column=1, sticky='ns')
        self.bulk_image_listbox.configure(yscrollcommand=bulk_listbox_scrollbar.set)
        self.bulk_image_listbox.bind('<<ListboxSelect>>', self.on_bulk_listbox_select)

        # --- Image Panel (in Tab 4) ---
        self.bulk_image_panel = ttk.Frame(self.bulk_tab, padding="5")
        self.bulk_image_panel.grid(row=1, column=1, sticky=(tk.N, tk.S, tk.W, tk.E), padx=5, pady=5)
        self.bulk_image_canvas = tk.Canvas(self.bulk_image_panel, bg='lightgrey', width=300, height=400)
        self.bulk_image_canvas.pack(expand=True, fill='both') 

        # --- Sheet Panel (in Tab 4) ---
        self.bulk_sheet_panel = ttk.Frame(self.bulk_tab, padding="10")
        self.bulk_sheet_panel.grid(row=1, column=2, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)
        self.bulk_sheet_panel.rowconfigure(1, weight=1) # Make sheet expand
        self.bulk_sheet_panel.columnconfigure(0, weight=1) # Make sheet expand
        ttk.Label(self.bulk_sheet_panel, text="Extracted/Edit Data (Selected Image):").grid(row=0, column=0, columnspan=2, pady=5, sticky=tk.W)
        self.bulk_data_sheet = tksheet.Sheet(self.bulk_sheet_panel,
                                        headers=["Username", "Level", "Class"],
                                        height=400, width=450) 
        self.bulk_data_sheet.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.bulk_data_sheet.enable_bindings() 
        self.bulk_data_sheet.column_width(column=0, width=200)
        self.bulk_data_sheet.column_width(column=1, width=70)
        self.bulk_data_sheet.column_width(column=2, width=150)
        
        # Frame for buttons below sheet
        self.bulk_button_frame = ttk.Frame(self.bulk_sheet_panel)
        self.bulk_button_frame.grid(row=2, column=0, pady=10)
        
        self.bulk_process_selected_button = ttk.Button(self.bulk_button_frame, text="Process Selected", command=self.process_selected_bulk, state=tk.DISABLED)
        self.bulk_process_selected_button.pack(side=tk.LEFT, padx=5)
        self.bulk_process_all_button = ttk.Button(self.bulk_button_frame, text="Process All", command=self.process_all_bulk, state=tk.DISABLED)
        self.bulk_process_all_button.pack(side=tk.LEFT, padx=5)
        self.bulk_save_selected_button = ttk.Button(self.bulk_button_frame, text="Save Selected", command=self.save_selected_bulk, state=tk.DISABLED)
        self.bulk_save_selected_button.pack(side=tk.LEFT, padx=5)
        self.bulk_save_all_button = ttk.Button(self.bulk_button_frame, text="Save All Processed", command=self.save_all_bulk, state=tk.DISABLED)
        self.bulk_save_all_button.pack(side=tk.LEFT, padx=5)
        
        # --- Tab 3: Manage Data ---
        self.manage_tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(self.manage_tab, text="Manage Data")
        # Configure columns: 0 for listbox, 1 for image, 2 for sheet/buttons
        self.manage_tab.columnconfigure(0, weight=1)
        self.manage_tab.columnconfigure(1, weight=1)
        self.manage_tab.columnconfigure(2, weight=2) 
        self.manage_tab.rowconfigure(0, weight=1) # Allow rows to expand

        # --- Listbox Panel (in Tab 3) ---
        self.listbox_panel = ttk.Frame(self.manage_tab, padding="5")
        self.listbox_panel.grid(row=0, column=0, sticky=(tk.N, tk.S, tk.W, tk.E), padx=5, pady=5)
        self.listbox_panel.rowconfigure(1, weight=1)
        self.listbox_panel.columnconfigure(0, weight=1)
        ttk.Label(self.listbox_panel, text="Processed Images:").grid(row=0, column=0, sticky=tk.W)
        self.image_listbox = tk.Listbox(self.listbox_panel, exportselection=False)
        self.image_listbox.grid(row=1, column=0, sticky=(tk.N, tk.S, tk.W, tk.E))
        listbox_scrollbar = ttk.Scrollbar(self.listbox_panel, orient=tk.VERTICAL, command=self.image_listbox.yview)
        listbox_scrollbar.grid(row=1, column=1, sticky='ns')
        self.image_listbox.configure(yscrollcommand=listbox_scrollbar.set)
        self.image_listbox.bind('<<ListboxSelect>>', self.on_listbox_select)

        # --- Image Panel (in Tab 3) ---
        self.manage_image_panel = ttk.Frame(self.manage_tab, padding="5")
        self.manage_image_panel.grid(row=0, column=1, sticky=(tk.N, tk.S, tk.W, tk.E), padx=5, pady=5)
        self.manage_image_canvas = tk.Canvas(self.manage_image_panel, bg='lightgrey', width=300, height=400)
        self.manage_image_canvas.pack(expand=True, fill='both') # Use pack here for simplicity

        # --- Sheet Panel (in Tab 3) ---
        self.manage_sheet_panel = ttk.Frame(self.manage_tab, padding="10")
        self.manage_sheet_panel.grid(row=0, column=2, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)
        self.manage_sheet_panel.rowconfigure(1, weight=1) 
        self.manage_sheet_panel.columnconfigure(0, weight=1) 
        ttk.Label(self.manage_sheet_panel, text="Edit Saved Data:").grid(row=0, column=0, columnspan=2, pady=5, sticky=tk.W)
        self.manage_data_sheet = tksheet.Sheet(self.manage_sheet_panel,
                                        headers=["Username", "Level", "Class"],
                                        height=400, width=450) 
        self.manage_data_sheet.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.manage_data_sheet.enable_bindings() 
        self.manage_data_sheet.column_width(column=0, width=200)
        self.manage_data_sheet.column_width(column=1, width=70)
        self.manage_data_sheet.column_width(column=2, width=150)
        
        # Frame for buttons below sheet
        self.manage_button_frame = ttk.Frame(self.manage_sheet_panel)
        self.manage_button_frame.grid(row=2, column=0, pady=10)
        
        self.manage_save_button = ttk.Button(self.manage_button_frame, text="Save Changes", command=self.save_manage_tab_data, state=tk.DISABLED)
        self.manage_save_button.pack(side=tk.LEFT, padx=5)
        
        self.delete_button = ttk.Button(self.manage_button_frame, text="Delete Image & Data", command=self.delete_selected_image, state=tk.DISABLED)
        self.delete_button.pack(side=tk.LEFT, padx=5)
        
        # --- Tab 4: All Data ---
        self.data_tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(self.data_tab, text="All Data")
        self.data_tab.columnconfigure(0, weight=1) # Make treeview frame expand
        self.data_tab.rowconfigure(0, weight=1) 

        # --- Data Panel (in Tab 2): Data Visualization ---
        self.all_data_panel = ttk.Frame(self.data_tab, padding="10") # Renamed for clarity
        self.all_data_panel.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.all_data_panel.columnconfigure(0, weight=1)
        self.all_data_panel.rowconfigure(1, weight=1)

        # Frame for top controls (Label + Filter)
        self.all_data_top_frame = ttk.Frame(self.all_data_panel)
        self.all_data_top_frame.grid(row=0, column=0, columnspan=2, sticky=tk.W)

        ttk.Label(self.all_data_top_frame, text="All Extracted Data (Select Row to View Image)").pack(side=tk.LEFT, padx=(0, 10))

        # Filter Checkbox
        self.filter_duplicates_var = tk.BooleanVar(value=False) # Default: show duplicates
        self.filter_checkbox = ttk.Checkbutton(
            self.all_data_top_frame, 
            text="Show Only Most Recent per User", 
            variable=self.filter_duplicates_var, 
            command=self.load_data_into_treeview # Refresh tree when toggled
        )
        self.filter_checkbox.pack(side=tk.LEFT)

        # Treeview setup (as before)
        columns = ('username', 'level', 'class', 'extracted_at')
        self.data_tree = ttk.Treeview(self.all_data_panel, columns=columns, displaycolumns=columns, show='headings')
        # ... (headings and column setup as before) ...
        self.data_tree.heading('username', text='Username')
        self.data_tree.heading('level', text='Level')
        self.data_tree.heading('class', text='Class')
        self.data_tree.heading('extracted_at', text='Extraction Date')
        # Add sorting command to headers
        for col_id in columns:
            self.data_tree.heading(col_id, 
                                   command=lambda c=col_id: self.sort_treeview_column(c, False))

        # Configure column widths (adjust as needed)
        self.data_tree.column('username', width=150)
        self.data_tree.column('level', width=50, anchor=tk.CENTER)
        self.data_tree.column('class', width=100)
        self.data_tree.column('extracted_at', width=150)
        self.data_tree.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Scrollbar setup (as before)
        scrollbar = ttk.Scrollbar(self.all_data_panel, orient=tk.VERTICAL, command=self.data_tree.yview)
        self.data_tree.configure(yscroll=scrollbar.set)
        scrollbar.grid(row=1, column=1, sticky='ns')

        # Bind selection event (as before)
        self.data_tree.bind("<<TreeviewSelect>>", self.on_tree_select)

        # Load initial data (after ALL tabs are created)
        self.load_data_into_treeview() # For All Data Tab
        self.populate_image_listbox() # For Manage Data Tab

        # Store data currently displayed in the Treeview for sorting
        self.displayed_tree_data = []
        # Store sorting state
        self.tree_sort_column = None
        self.tree_sort_reverse = False

        # Bind Escape key to exit
        master.bind('<Escape>', self.quit_app)

    # --- Methods --- 

    def quit_app(self, event=None):
        """Closes the application window."""
        print("Escape pressed, exiting.")
        self.master.destroy()

    def select_image(self):
        """Opens dialog, loads image, enables Process button."""
        file_path = filedialog.askopenfilename(
            title="Select Screenshot",
            filetypes=(("PNG files", "*.png"), 
                       ("JPEG files", "*.jpg"), 
                       ("JPEG files", "*.jpeg"))
        )
        if not file_path:
            return

        self.current_image_path = file_path
        self.status_label.config(text=f"Loaded: {os.path.basename(file_path)}")
        self.clear_sheet() # Clear sheet data
        self.save_button.config(state=tk.DISABLED)

        try:
            self.current_pil_image = Image.open(file_path)
            # Add image to DB right away to get an ID
            with open(file_path, 'rb') as f:
                image_blob = f.read()
            self.current_image_id = database.add_image(file_path, image_blob)
            if self.current_image_id is None:
                raise ValueError("Failed to get image ID from database.")

            self.display_image(self.current_pil_image)
            self.process_button.config(state=tk.NORMAL) # Enable process button
            self.status_label.config(text=f"Image loaded. Ready to process.")

        except FileNotFoundError:
             messagebox.showerror("Error", f"Image file not found: {file_path}")
             self.reset_image_panel()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load image: {e}")
            traceback.print_exc()
            self.reset_image_panel()

    def trigger_ocr_processing(self):
        """Called by Process button. Runs OCR and populates the data sheet."""
        if not self.current_image_path or self.current_image_id is None:
            messagebox.showwarning("Warning", "Please select an image first.")
            return
        
        self.status_label.config(text="Processing OCR...")
        self.master.update_idletasks()
        self.process_button.config(state=tk.DISABLED) # Disable while processing

        self.last_extracted_data = [] # Clear previous results
        try:
            print(f"Processing image ID: {self.current_image_id}, Path: {self.current_image_path}")
            # Run OCR - UPDATED FUNCTION NAME
            self.last_extracted_data = ocr_processor.extract_data_easyocr(self.current_image_path)
            print(f"Extracted {len(self.last_extracted_data)} potential entries.")
            
            self.display_data_on_sheet(self.last_extracted_data)
            
            if self.last_extracted_data: # Enable save only if data was found
                 self.save_button.config(state=tk.NORMAL)
                 self.status_label.config(text="OCR complete. Edit sheet if needed and save.")
            else:
                 self.save_button.config(state=tk.DISABLED)
                 self.status_label.config(text="OCR complete. No data found.")
                 messagebox.showinfo("OCR Result", "No data automatically extracted.")

        except pytesseract.TesseractNotFoundError:
            messagebox.showerror("Error", "Tesseract OCR engine not found...") # Full message omitted for brevity
            self.status_label.config(text="OCR Error: Tesseract not found")
        except ImportError as e:
             messagebox.showerror("Error", f"Missing library: {e}...")
             self.status_label.config(text=f"Import Error: {e}")
        except Exception as e:
            messagebox.showerror("Processing Error", f"Failed to process image: {e}")
            traceback.print_exc()
            self.status_label.config(text=f"Processing Error occurred.")
        finally:
             self.process_button.config(state=tk.NORMAL) # Re-enable after processing

    def display_data_on_sheet(self, data_list, sheet_widget=None):
        """Populates the specified data sheet with the extracted data."""
        target_sheet = sheet_widget if sheet_widget else self.data_sheet
        self.clear_sheet(sheet_widget=target_sheet) # Clear the target sheet
        if data_list:
            # Prepare data in list-of-lists format for tksheet
            sheet_data = []
            for entry in data_list:
                sheet_data.append([
                    entry.get('username', ''),
                    str(entry.get('level', '')), # Level as string for sheet
                    entry.get('class', '')
                ])
            # Use the target_sheet variable to set data
            target_sheet.set_sheet_data(sheet_data, reset_col_positions=True, reset_row_positions=True)
        
    def save_proc_tab_data(self):
        """Saves ALL data currently in the sheet on the PROCESSING TAB."""
        if self.current_image_id is None:
            messagebox.showwarning("Warning", "No image context in processing tab.")
            return
        sheet_data = self.data_sheet.get_sheet_data()
        valid_rows_to_save, errors = self.validate_sheet_data(sheet_data)
        if errors:
            messagebox.showwarning("Validation Error", "Errors found:\n" + "\n".join(errors) + "\n\nPlease correct and save again.")
            return
        if not valid_rows_to_save:
             messagebox.showinfo("Save", "No valid data rows found in the sheet to save.")
             return
        # Proceed with saving
        try:
            database.clear_extracted_data_for_image(self.current_image_id)
            saved_count = 0
            for username, level, class_name in valid_rows_to_save:
                 database.add_extracted_data(self.current_image_id, username, level, class_name)
                 saved_count += 1
            messagebox.showinfo("Success", f"{saved_count} data entries saved.")
            self.load_data_into_treeview() # Refresh all data tab
            self.populate_image_listbox() # Refresh manage tab listbox
            # Keep save button enabled
        except Exception as e:
             messagebox.showerror("Database Error", f"Failed to save data: {e}")
             traceback.print_exc()

    def save_manage_tab_data(self):
        """Saves ALL data currently in the sheet on the MANAGE TAB."""
        if self.manage_tab_image_id is None:
             messagebox.showwarning("Warning", "No image selected in the Manage Data tab.")
             return
        sheet_data = self.manage_data_sheet.get_sheet_data()
        valid_rows_to_save, errors = self.validate_sheet_data(sheet_data)
        if errors:
            messagebox.showwarning("Validation Error", "Errors found:\n" + "\n".join(errors) + "\n\nPlease correct and save again.")
            return
        if not valid_rows_to_save:
             messagebox.showinfo("Save", "No valid data rows found in the sheet to save.")
             return
        # Proceed with saving
        try:
            database.clear_extracted_data_for_image(self.manage_tab_image_id)
            saved_count = 0
            for username, level, class_name in valid_rows_to_save:
                 database.add_extracted_data(self.manage_tab_image_id, username, level, class_name)
                 saved_count += 1
            messagebox.showinfo("Success", f"{saved_count} data entries saved.")
            self.load_data_into_treeview() # Refresh all data tab
            # Optionally refresh listbox if needed, though content doesn't change on save
            # Keep save button enabled
        except Exception as e:
             messagebox.showerror("Database Error", f"Failed to save data: {e}")
             traceback.print_exc()

    def validate_sheet_data(self, sheet_data):
        """Helper function to validate data read from tksheet."""
        valid_rows = []
        errors = []
        for i, row in enumerate(sheet_data):
            if len(row) < 3:
                # Ignore potentially empty trailing rows from sheet
                if not any(str(c).strip() for c in row):
                    continue 
                errors.append(f"Row {i+1}: Incomplete data.")
                continue
            
            username = str(row[0]).strip()
            level_str = str(row[1]).strip()
            class_name = str(row[2]).strip()

            if not username:
                errors.append(f"Row {i+1}: Username cannot be empty.")
                continue
                
            level = None
            if level_str:
                try:
                    level = int(level_str)
                except ValueError:
                    errors.append(f"Row {i+1}: Level '{level_str}' must be a number.")
                    continue
            
            valid_rows.append((username, level, class_name))
        return valid_rows, errors

    def clear_sheet(self, sheet_widget=None):
        """Clears the specified data sheet (defaults to proc tab sheet)."""
        target_sheet = sheet_widget if sheet_widget else self.data_sheet
        if target_sheet.get_total_rows() > 0:
            # Simpler way to clear
            target_sheet.set_sheet_data([]) 

    def load_data_into_treeview(self):
        """Loads data from DB, applies filter, and populates the treeview."""
        for item in self.data_tree.get_children():
            self.data_tree.delete(item)
        self.tree_data_map.clear() 
        self.displayed_tree_data = [] # Clear displayed data cache
        
        try:
            all_db_data = database.get_all_extracted_data()
            
            # Apply filtering if checkbox is checked
            data_to_display = []
            if self.filter_duplicates_var.get():
                seen_usernames = set()
                # Data is already sorted by extracted_at DESC from DB query
                for row in all_db_data:
                    username = row[3] # Username is at index 3
                    if username not in seen_usernames:
                        data_to_display.append(row)
                        seen_usernames.add(username)
            else:
                data_to_display = all_db_data
            
            # Store for sorting
            self.displayed_tree_data = data_to_display
            
            # Populate Treeview
            for row in self.displayed_tree_data:
                db_id, image_id, file_path, username, level, class_name, timestamp_str = row
                try:
                    dt_obj = datetime.datetime.fromisoformat(timestamp_str)
                    formatted_date = dt_obj.strftime("%Y-%m-%d %H:%M:%S")
                except:
                    formatted_date = timestamp_str
                item_id = self.data_tree.insert('', tk.END, values=(username, level, class_name, formatted_date))
                self.tree_data_map[item_id] = (image_id, file_path)

            # Apply existing sort if any
            if self.tree_sort_column:
                self.sort_treeview_column(self.tree_sort_column, self.tree_sort_reverse, refresh_display=False)

        except Exception as e:
            print(f"Error loading data into treeview: {e}")
            traceback.print_exc()

    def sort_treeview_column(self, col_id, reverse, refresh_display=True):
        """Sorts the Treeview data by the specified column."""
        if not self.displayed_tree_data:
            return # Nothing to sort
            
        # Determine sort key and type based on column id
        if col_id == 'username':
            index = 3
            key_func = lambda row: str(row[index]).lower() # Case-insensitive string sort
        elif col_id == 'level':
            index = 4
            key_func = lambda row: int(row[index]) if row[index] is not None else -1 # Integer sort, handle None
        elif col_id == 'class':
            index = 5
            key_func = lambda row: str(row[index]).lower()
        elif col_id == 'extracted_at':
            index = 6
            # Convert to datetime for proper sorting, fallback to string if format fails
            def date_key(row):
                try: return datetime.datetime.fromisoformat(row[index])
                except: return datetime.datetime.min # Put unparseable dates first
            key_func = date_key
        else:
            return # Unknown column
            
        # Toggle sort direction if the same column is clicked again
        if col_id == self.tree_sort_column:
            reverse = not self.tree_sort_reverse
        else:
            reverse = False # Default to ascending for new column
            
        self.displayed_tree_data.sort(key=key_func, reverse=reverse)
        
        # Update sort state
        self.tree_sort_column = col_id
        self.tree_sort_reverse = reverse

        # Refresh display if requested (default)
        if refresh_display:
            # Clear existing items
            for item in self.data_tree.get_children():
                self.data_tree.delete(item)
            self.tree_data_map.clear()
            
            # Repopulate with sorted data
            for row in self.displayed_tree_data:
                db_id, image_id, file_path, username, level, class_name, timestamp_str = row
                try:
                    dt_obj = datetime.datetime.fromisoformat(timestamp_str)
                    formatted_date = dt_obj.strftime("%Y-%m-%d %H:%M:%S")
                except:
                    formatted_date = timestamp_str
                item_id = self.data_tree.insert('', tk.END, values=(username, level, class_name, formatted_date))
                self.tree_data_map[item_id] = (image_id, file_path)

    def on_tree_select(self, event):
        """Handles selection changes in the data Treeview."""
        # (Implementation as before)
        selected_items = self.data_tree.selection()
        if not selected_items: return
        selected_item_id = selected_items[0]
        if selected_item_id in self.tree_data_map:
            image_id, file_path = self.tree_data_map[selected_item_id]
            self.display_image_from_db(image_id, file_path)
            self.notebook.select(self.processing_tab)
        else:
             print(f"Warning: Selected tree item {selected_item_id} not found in data map.")

    def display_image_from_db(self, image_id, file_path):
         """Loads image blob, displays it (Proc Tab), and populates PROC TAB sheet."""
         try:
            image_blob = database.get_image_blob(image_id)
            if image_blob:
                pil_image = Image.open(io.BytesIO(image_blob))
                self.display_image(pil_image) # Displays on proc tab canvas
                self.current_image_id = image_id
                self.current_image_path = file_path
                self.current_pil_image = pil_image
                # Fetch SAVED data for this image to populate PROC TAB sheet
                saved_data = database.get_extracted_data_by_image_id(image_id)
                self.last_extracted_data = saved_data 
                self.display_data_on_sheet(saved_data, sheet_widget=self.data_sheet) # Use proc tab sheet
                self.process_button.config(state=tk.NORMAL)
                self.save_button.config(state=tk.NORMAL if saved_data else tk.DISABLED)
                self.status_label.config(text=f"Loaded image ID {image_id} from All Data tab. Process again or edit/save.")
            else:
                messagebox.showerror("Error", f"Could not load image data for ID {image_id}.")
                self.reset_image_panel()
         except Exception as e:
             messagebox.showerror("Error", f"Failed to display image ID {image_id}: {e}")
             traceback.print_exc()
             self.reset_image_panel()
             
    def display_image(self, pil_image):
        """Displays the given PIL image on the PROC TAB canvas."""
        display_img = pil_image.copy()
        display_img.thumbnail((300, 400)) 
        self.proc_tk_image = ImageTk.PhotoImage(display_img) # Use different var name
        self.image_canvas.delete("all") 
        self.image_canvas.config(width=self.proc_tk_image.width(), height=self.proc_tk_image.height())
        self.image_canvas.create_image(0, 0, anchor=tk.NW, image=self.proc_tk_image)
        
    def reset_image_panel(self):
         """Clears the image canvas, PROC TAB sheet and related variables."""
         self.image_canvas.delete("all")
         self.clear_sheet(sheet_widget=self.data_sheet) # Use proc tab sheet
         self.current_image_path = None
         self.current_pil_image = None
         self.current_image_id = None
         self.last_extracted_data = []
         self.process_button.config(state=tk.DISABLED)
         self.save_button.config(state=tk.DISABLED)
         self.status_label.config(text="Failed to load image or no image selected.")

    def populate_image_listbox(self):
        """Clears and repopulates the image listbox in the Manage tab."""
        self.image_listbox.delete(0, tk.END) # Clear listbox
        self.image_listbox_map.clear()
        try:
            all_images = database.get_all_images()
            for index, (img_id, file_path) in enumerate(all_images):
                display_name = os.path.basename(file_path) if file_path else f"Image ID: {img_id}"
                self.image_listbox.insert(tk.END, display_name)
                self.image_listbox_map[index] = (img_id, file_path)
        except Exception as e:
             print(f"Error populating image listbox: {e}")
             traceback.print_exc()
             
    def on_listbox_select(self, event):
        """Handles selection changes in the image listbox."""
        selected_indices = self.image_listbox.curselection()
        if not selected_indices: return
        
        selected_index = selected_indices[0]
        if selected_index in self.image_listbox_map:
            image_id, file_path = self.image_listbox_map[selected_index]
            self.manage_tab_image_id = image_id # Set context for manage tab
            self.manage_tab_file_path = file_path
            self.display_manage_tab_image(image_id)
            self.delete_button.config(state=tk.NORMAL)
            # self.manage_save_button.config(state=tk.DISABLED) # Disabled until data loaded
            # Always enable save button once an image is selected in this tab
            self.manage_save_button.config(state=tk.NORMAL) 
        else:
             print(f"Error: Selected listbox index {selected_index} not in map.")
             self.reset_manage_panel()
             
    def display_manage_tab_image(self, image_id):
         """Loads image blob and its SAVED data into the Manage Tab."""
         try:
            image_blob = database.get_image_blob(image_id)
            if image_blob:
                pil_image = Image.open(io.BytesIO(image_blob))
                # Display on manage tab canvas
                display_img = pil_image.copy()
                display_img.thumbnail((300, 400)) 
                self.manage_tk_image = ImageTk.PhotoImage(display_img) # Store separately
                self.manage_image_canvas.delete("all") 
                self.manage_image_canvas.config(width=self.manage_tk_image.width(), height=self.manage_tk_image.height())
                self.manage_image_canvas.create_image(0, 0, anchor=tk.NW, image=self.manage_tk_image)
                
                # Load saved data into manage tab sheet
                saved_data = database.get_extracted_data_by_image_id(image_id)
                self.display_data_on_sheet(saved_data, sheet_widget=self.manage_data_sheet)
                self.manage_save_button.config(state=tk.NORMAL if saved_data else tk.DISABLED)
            else:
                messagebox.showerror("Error", f"Could not load image data for ID {image_id}.")
                self.reset_manage_panel()
         except Exception as e:
             messagebox.showerror("Error", f"Failed to display image ID {image_id} in Manage Tab: {e}")
             traceback.print_exc()
             self.reset_manage_panel()
             
    def delete_selected_image(self):
        """Deletes the image and data selected in the Manage Tab listbox."""
        if self.manage_tab_image_id is None:
             messagebox.showwarning("Warning", "No image selected in the listbox to delete.")
             return
             
        image_id_to_delete = self.manage_tab_image_id
        file_path_to_delete = self.manage_tab_file_path
        display_name = os.path.basename(file_path_to_delete) if file_path_to_delete else f"Image ID {image_id_to_delete}"
        
        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to permanently delete\n'{display_name}'\nand all its associated data?"):
            success = database.delete_image_and_data(image_id_to_delete)
            if success:
                messagebox.showinfo("Deleted", f"'{display_name}' deleted successfully.")
                self.reset_manage_panel() # Clear the panel
                self.populate_image_listbox() # Refresh listbox
                self.load_data_into_treeview() # Refresh treeview
            else:
                 messagebox.showerror("Error", f"Failed to delete image ID {image_id_to_delete}.")

    def reset_manage_panel(self):
        """Clears the controls on the manage tab."""
        self.manage_image_canvas.delete("all")
        self.clear_sheet(sheet_widget=self.manage_data_sheet)
        self.manage_tab_image_id = None
        self.manage_tab_file_path = None
        self.manage_save_button.config(state=tk.DISABLED)
        self.delete_button.config(state=tk.DISABLED)
        # Clear listbox selection visually
        # self.image_listbox.selection_clear(0, tk.END)

    # --- Bulk Tab Methods ---
    def select_bulk_folder(self):
        """Opens dialog to select a folder and populates the bulk image list."""
        selected_path = filedialog.askdirectory(title="Select Folder Containing Images")
        if not selected_path:
            return
            
        self.bulk_folder_path = selected_path
        self.bulk_folder_label.config(text=f"Folder: ...{os.path.basename(selected_path)}")
        self.bulk_image_listbox.delete(0, tk.END)
        self.bulk_listbox_map.clear()
        self.bulk_image_files.clear()
        self.bulk_results_map.clear()
        self.clear_sheet(sheet_widget=self.bulk_data_sheet)
        self.bulk_image_canvas.delete("all")
        self.bulk_process_selected_button.config(state=tk.DISABLED)
        self.bulk_process_all_button.config(state=tk.DISABLED)
        self.bulk_save_selected_button.config(state=tk.DISABLED)
        self.bulk_save_all_button.config(state=tk.DISABLED)
        
        valid_extensions = (".png", ".jpg", ".jpeg")
        try:
            index = 0
            for filename in sorted(os.listdir(self.bulk_folder_path)):
                if filename.lower().endswith(valid_extensions):
                    full_path = os.path.join(self.bulk_folder_path, filename)
                    if os.path.isfile(full_path):
                        self.bulk_image_files.append(full_path)
                        self.bulk_image_listbox.insert(tk.END, filename)
                        self.bulk_listbox_map[index] = full_path
                        index += 1
            
            if self.bulk_image_files:
                 self.bulk_process_all_button.config(state=tk.NORMAL)
            else:
                 self.bulk_process_all_button.config(state=tk.DISABLED)
                 messagebox.showinfo("Info", "No images found in the selected folder.")
                 
        except Exception as e:
             messagebox.showerror("Error", f"Failed to read folder contents: {e}")
             traceback.print_exc()
             self.bulk_process_all_button.config(state=tk.DISABLED)

    def on_bulk_listbox_select(self, event):
        """Handles selection changes in the bulk image listbox."""
        selected_indices = self.bulk_image_listbox.curselection()
        if not selected_indices: return
        
        selected_index = selected_indices[0]
        if selected_index in self.bulk_listbox_map:
            filepath = self.bulk_listbox_map[selected_index]
            self.bulk_selected_filepath = filepath
            self.display_bulk_tab_image(filepath) # Display image
            # Display existing results if already processed
            if filepath in self.bulk_results_map:
                self.display_data_on_sheet(self.bulk_results_map[filepath], sheet_widget=self.bulk_data_sheet)
                self.bulk_save_selected_button.config(state=tk.NORMAL)
            else:
                self.clear_sheet(sheet_widget=self.bulk_data_sheet)
                self.bulk_save_selected_button.config(state=tk.DISABLED)
            self.bulk_process_selected_button.config(state=tk.NORMAL)
        else:
             print(f"Error: Selected bulk listbox index {selected_index} not in map.")
             self.bulk_selected_filepath = None
             # Clear display?
             
    def display_bulk_tab_image(self, filepath):
        """Displays the image from the filepath in the bulk tab canvas."""
        try:
            pil_image = Image.open(filepath)
            display_img = pil_image.copy()
            display_img.thumbnail((300, 400)) 
            self.bulk_tk_image = ImageTk.PhotoImage(display_img) 
            self.bulk_image_canvas.delete("all") 
            self.bulk_image_canvas.config(width=self.bulk_tk_image.width(), height=self.bulk_tk_image.height())
            self.bulk_image_canvas.create_image(0, 0, anchor=tk.NW, image=self.bulk_tk_image)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to display image: {os.path.basename(filepath)}\n{e}")
            self.bulk_image_canvas.delete("all")
            traceback.print_exc()
            
    def process_selected_bulk(self):
        """Processes the single image currently selected in the bulk list."""
        if not self.bulk_selected_filepath:
             messagebox.showwarning("Warning", "No image selected in the list.")
             return
        
        filepath = self.bulk_selected_filepath
        print(f"Processing selected bulk image: {filepath}")
        self.status_label.config(text=f"Processing {os.path.basename(filepath)}...")
        self.master.update_idletasks()
        # Disable buttons during processing
        self.bulk_process_selected_button.config(state=tk.DISABLED)
        self.bulk_process_all_button.config(state=tk.DISABLED)
        
        try:
            extracted_data = ocr_processor.extract_data_easyocr(filepath)
            self.bulk_results_map[filepath] = extracted_data # Store/update results
            self.display_data_on_sheet(extracted_data, sheet_widget=self.bulk_data_sheet)
            self.status_label.config(text=f"Processed {os.path.basename(filepath)}. Edit sheet and save if needed.")
            # Enable relevant save buttons
            self.bulk_save_selected_button.config(state=tk.NORMAL)
            self.bulk_save_all_button.config(state=tk.NORMAL if self.bulk_results_map else tk.DISABLED)
            print(f" -> Found {len(extracted_data)} entries.")
        except Exception as e:
            messagebox.showerror("OCR Error", f"Failed processing {os.path.basename(filepath)}:\n{e}")
            traceback.print_exc()
            self.status_label.config(text=f"Error processing {os.path.basename(filepath)}.")
        finally:
            # Re-enable buttons
            self.bulk_process_selected_button.config(state=tk.NORMAL)
            self.bulk_process_all_button.config(state=tk.NORMAL)

    def process_all_bulk(self):
        """Processes all images listed in the bulk tab listbox."""
        if not self.bulk_image_files:
            messagebox.showwarning("Warning", "No images loaded in the list.")
            return
            
        print(f"Processing all {len(self.bulk_image_files)} bulk images...")
        self.status_label.config(text=f"Processing 0/{len(self.bulk_image_files)} images...")
        self.master.update_idletasks()
        # Disable buttons
        self.bulk_process_selected_button.config(state=tk.DISABLED)
        self.bulk_process_all_button.config(state=tk.DISABLED)
        self.bulk_save_selected_button.config(state=tk.DISABLED)
        self.bulk_save_all_button.config(state=tk.DISABLED)
        
        processed_count = 0
        errors_occurred = False
        self.bulk_results_map.clear() # Clear previous bulk results
        
        for i, filepath in enumerate(self.bulk_image_files):
            filename = os.path.basename(filepath)
            self.status_label.config(text=f"Processing {i+1}/{len(self.bulk_image_files)}: {filename}...")
            self.master.update_idletasks()
            try:
                extracted_data = ocr_processor.extract_data_easyocr(filepath)
                self.bulk_results_map[filepath] = extracted_data
                processed_count += 1
                print(f" -> Processed {filename}: Found {len(extracted_data)} entries.")
                # Display results if this is the currently selected image
                if filepath == self.bulk_selected_filepath:
                    self.display_data_on_sheet(extracted_data, sheet_widget=self.bulk_data_sheet)
                    self.bulk_save_selected_button.config(state=tk.NORMAL) # Enable save for current selection
            except Exception as e:
                errors_occurred = True
                print(f" -> ERROR processing {filename}: {e}")
                # Optionally show error popup per file, or just log/status update
                # messagebox.showerror("OCR Error", f"Failed processing {filename}:\n{e}", parent=self.bulk_tab)
        
        # Update status after processing all
        final_status = f"Bulk processing complete. {processed_count}/{len(self.bulk_image_files)} images processed."
        if errors_occurred:
            final_status += " Some errors occurred (see console)."
        self.status_label.config(text=final_status)
        
        if self.bulk_results_map: # Enable Save All if any results were stored
            self.bulk_save_all_button.config(state=tk.NORMAL)
        
        # Re-enable process buttons, keep save selected disabled unless current item was processed
        self.bulk_process_selected_button.config(state=tk.NORMAL)
        self.bulk_process_all_button.config(state=tk.NORMAL)
        if self.bulk_selected_filepath not in self.bulk_results_map:
            self.bulk_save_selected_button.config(state=tk.DISABLED)
            
    def save_selected_bulk(self):
        """Saves the data for the currently selected image from the bulk sheet."""
        if not self.bulk_selected_filepath:
            messagebox.showwarning("Warning", "No image selected in the list.")
            return
            
        filepath = self.bulk_selected_filepath
        sheet_data = self.bulk_data_sheet.get_sheet_data()
        if not sheet_data:
             messagebox.showinfo("Save", "Sheet is empty, nothing to save for selected image.")
             return
             
        valid_rows_to_save, errors = self.validate_sheet_data(sheet_data)
        if errors:
            messagebox.showwarning("Validation Error", "Errors found:\n" + "\n".join(errors)) 
            return
        if not valid_rows_to_save:
             messagebox.showinfo("Save", "No valid data rows found in the sheet to save.")
             return
             
        # Get image ID (add image to DB if not already there)
        try:
            with open(filepath, 'rb') as f: image_blob = f.read()
            image_id = database.add_image(filepath, image_blob)
            if image_id is None:
                 raise ValueError("Failed to get or add image ID to database.")
                 
            # Proceed with saving
            database.clear_extracted_data_for_image(image_id)
            saved_count = 0
            for username, level, class_name in valid_rows_to_save:
                 database.add_extracted_data(image_id, username, level, class_name)
                 saved_count += 1
            messagebox.showinfo("Success", f"{saved_count} entries saved for {os.path.basename(filepath)}.")
            # Update internal map too, in case user processed again without saving
            self.bulk_results_map[filepath] = [{'username': r[0], 'level': r[1], 'class': r[2]} for r in valid_rows_to_save]
            # Refresh other views
            self.load_data_into_treeview()
            self.populate_image_listbox() # Refresh manage list
        except Exception as e:
             messagebox.showerror("Database Error", f"Failed to save data for {os.path.basename(filepath)}: {e}")
             traceback.print_exc()

    def save_all_bulk(self):
        """Saves all processed data stored in self.bulk_results_map to the DB."""
        if not self.bulk_results_map:
            messagebox.showinfo("Save All", "No processed data available to save.")
            return
            
        total_saved_count = 0
        errors_occurred = False
        num_images = len(self.bulk_results_map)
        current_image_num = 0
        
        if not messagebox.askyesno("Confirm Save All", f"This will save processed data for {num_images} images.\nExisting saved data for these images will be replaced.\nContinue?"):
            return
            
        self.status_label.config(text=f"Saving data for 0/{num_images} images...")
        self.master.update_idletasks()
        # Disable buttons
        self.bulk_process_selected_button.config(state=tk.DISABLED)
        self.bulk_process_all_button.config(state=tk.DISABLED)
        self.bulk_save_selected_button.config(state=tk.DISABLED)
        self.bulk_save_all_button.config(state=tk.DISABLED)

        for filepath, data_list in self.bulk_results_map.items():
            current_image_num += 1
            filename = os.path.basename(filepath)
            self.status_label.config(text=f"Saving data for {current_image_num}/{num_images}: {filename}...")
            self.master.update_idletasks()
            
            # Data is already extracted, format it for validation/saving
            # (Assuming data_list contains dicts like {'username': '...', ...})
            rows_to_validate = []
            for entry in data_list:
                 rows_to_validate.append([
                     entry.get('username', ''), 
                     entry.get('level', ''), # Level might be None or int
                     entry.get('class', '')
                 ])
                 
            valid_rows_to_save, errors = self.validate_sheet_data(rows_to_validate)
            
            if errors:
                print(f" -> Validation errors saving {filename}: {errors}")
                errors_occurred = True
                continue # Skip saving this file
            if not valid_rows_to_save:
                print(f" -> No valid rows to save for {filename}.")
                continue # Skip saving this file
                
            # Get image ID
            try:
                with open(filepath, 'rb') as f: image_blob = f.read()
                image_id = database.add_image(filepath, image_blob)
                if image_id is None: raise ValueError("Failed to get image ID")
                
                database.clear_extracted_data_for_image(image_id)
                file_saved_count = 0
                for username, level, class_name in valid_rows_to_save:
                     database.add_extracted_data(image_id, username, level, class_name)
                     file_saved_count += 1
                print(f" -> Saved {file_saved_count} entries for {filename}.")
                total_saved_count += file_saved_count
                
            except Exception as e:
                print(f" -> ERROR saving data for {filename}: {e}")
                errors_occurred = True
                # traceback.print_exc() # Optionally print full trace

        # Update status and re-enable buttons
        final_status = f"Bulk save complete. {total_saved_count} total entries saved."
        if errors_occurred:
             final_status += " Some errors occurred (see console)."
        self.status_label.config(text=final_status)
        messagebox.showinfo("Save All Complete", final_status)
        
        self.bulk_process_selected_button.config(state=tk.NORMAL)
        self.bulk_process_all_button.config(state=tk.NORMAL)
        # Re-enable save selected only if current selection exists and was potentially saved
        if self.bulk_selected_filepath in self.bulk_results_map:
             self.bulk_save_selected_button.config(state=tk.NORMAL)
        else:
             self.bulk_save_selected_button.config(state=tk.DISABLED)
        self.bulk_save_all_button.config(state=tk.NORMAL if self.bulk_results_map else tk.DISABLED)
        
        # Refresh other views
        self.load_data_into_treeview()
        self.populate_image_listbox()
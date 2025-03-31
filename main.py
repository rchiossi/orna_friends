import tkinter as tk
from gui import AppGUI

def main():
    """Main function to run the application."""
    root = tk.Tk()
    app = AppGUI(root)
    
    # Force window to the front on macOS
    root.withdraw() # Hide the window initially
    root.update_idletasks() # Process geometry tasks
    root.deiconify() # Show the window (should bring it to front)
    # Optionally add lift/focus if needed, but deiconify often suffices
    # root.lift()
    # root.focus_force()
    
    root.mainloop()

if __name__ == "__main__":
    main() 
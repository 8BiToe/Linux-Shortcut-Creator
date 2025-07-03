#!/usr/bin/env python3
"""
Desktop Shortcut Creator for Zorin OS
A simple GUI application to create desktop shortcuts (.desktop files)
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import stat
import subprocess
import glob
from pathlib import Path
import shlex # For robust parsing of Exec strings
import re # For regex to extract Flatpak ID

class ShortcutCreator:
    def __init__(self, root):
        self.root = root
        self.root.title("Desktop Shortcut Creator")
        self.root.geometry("650x550")
        self.root.resizable(True, True)
        
        # Get desktop path
        self.desktop_path = Path.home() / "Desktop"
        if not self.desktop_path.exists():
            # Check for common localized desktop paths if default 'Desktop' isn't found
            localized_desktop_dirs = [
                Path.home() / "Plocha",  # Czech
                Path.home() / "Рабочий стол", # Russian
                Path.home() / "Bureau", # French
                Path.home() / "Schreibtisch", # German
            ]
            found = False
            for p in localized_desktop_dirs:
                if p.exists():
                    self.desktop_path = p
                    found = True
                    break
            if not found:
                self.desktop_path = Path.home() # Fallback to home if no known desktop path
        
        # 1. Initialize applications list (empty for now)
        self.applications = [] 

        # 2. Create widgets. This sets up self.status_text and other GUI elements.
        self.create_widgets()
        
        # 3. Load applications. Now self.applications is a list, and self.status_text exists for logging.
        self.load_applications() 
        
        # Initial log messages after everything is set up
        self.log_message(f"Desktop directory: {self.desktop_path}\n")
        self.log_message(f"Found {len(self.applications)} installed applications.\n")

        # After applications are loaded, update the dropdown
        self.update_app_dropdown()
        
    def create_widgets(self):
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        # Title
        title_label = ttk.Label(main_frame, text="Create Desktop Shortcut", 
                               font=("Arial", 16, "bold"))
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 20))
        
        # Shortcut Name
        ttk.Label(main_frame, text="Shortcut Name:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.name_var = tk.StringVar()
        name_entry = ttk.Entry(main_frame, textvariable=self.name_var, width=40)
        name_entry.grid(row=1, column=1, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        # Application Selection
        ttk.Label(main_frame, text="Select Application:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.app_var = tk.StringVar()
        self.app_combo = ttk.Combobox(main_frame, textvariable=self.app_var, width=35, state="readonly")
        self.app_combo.grid(row=2, column=1, sticky=(tk.W, tk.E), pady=5)
        self.app_combo.bind('<<ComboboxSelected>>', self.on_app_selected)
        
        refresh_btn = ttk.Button(main_frame, text="Refresh", command=self.refresh_applications)
        refresh_btn.grid(row=2, column=2, padx=(5, 0), pady=5)
        
        # Application Path (now shows resolved path, editable)
        ttk.Label(main_frame, text="Application Path:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.path_var = tk.StringVar()
        path_entry = ttk.Entry(main_frame, textvariable=self.path_var, width=35)
        path_entry.grid(row=3, column=1, sticky=(tk.W, tk.E), pady=5)
        
        browse_btn = ttk.Button(main_frame, text="Browse", command=self.browse_application)
        browse_btn.grid(row=3, column=2, padx=(5, 0), pady=5)
        
        # Icon Path (optional)
        ttk.Label(main_frame, text="Icon Path (optional):").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.icon_var = tk.StringVar()
        icon_entry = ttk.Entry(main_frame, textvariable=self.icon_var, width=35)
        icon_entry.grid(row=4, column=1, sticky=(tk.W, tk.E), pady=5)
        
        icon_browse_btn = ttk.Button(main_frame, text="Browse", command=self.browse_icon)
        icon_browse_btn.grid(row=4, column=2, padx=(5, 0), pady=5)
        
        # Description (optional)
        ttk.Label(main_frame, text="Description (optional):").grid(row=5, column=0, sticky=tk.W, pady=5)
        self.desc_var = tk.StringVar()
        desc_entry = ttk.Entry(main_frame, textvariable=self.desc_var, width=40)
        desc_entry.grid(row=5, column=1, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        # Categories (optional)
        ttk.Label(main_frame, text="Categories (optional):").grid(row=6, column=0, sticky=tk.W, pady=5)
        self.categories_var = tk.StringVar(value="Application")
        categories_combo = ttk.Combobox(main_frame, textvariable=self.categories_var, width=37)
        categories_combo['values'] = ('Application', 'Game', 'Development', 'Office', 
                                     'Graphics', 'AudioVideo', 'Network', 'System', 'Utility', 'Education', 'Science', 'Finance', 'Other')
        categories_combo.grid(row=6, column=1, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        # Terminal checkbox
        self.terminal_var = tk.BooleanVar()
        terminal_check = ttk.Checkbutton(main_frame, text="Run in terminal", 
                                        variable=self.terminal_var)
        terminal_check.grid(row=7, column=1, sticky=tk.W, pady=5)
        
        # Destination
        ttk.Label(main_frame, text="Save to:").grid(row=8, column=0, sticky=tk.W, pady=5)
        self.dest_var = tk.StringVar(value=str(self.desktop_path))
        dest_entry = ttk.Entry(main_frame, textvariable=self.dest_var, width=35)
        dest_entry.grid(row=8, column=1, sticky=(tk.W, tk.E), pady=5)
        
        dest_browse_btn = ttk.Button(main_frame, text="Browse", command=self.browse_destination)
        dest_browse_btn.grid(row=8, column=2, padx=(5, 0), pady=5)
        
        # Buttons frame
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=9, column=0, columnspan=3, pady=20)
        
        create_btn = ttk.Button(button_frame, text="Create Shortcut", 
                               command=self.create_shortcut, style="Accent.TButton")
        create_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        clear_btn = ttk.Button(button_frame, text="Clear Fields", command=self.clear_fields)
        clear_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # Status text
        self.status_text = tk.Text(main_frame, height=8, width=60, wrap=tk.WORD)
        self.status_text.grid(row=10, column=0, columnspan=3, pady=10, sticky=(tk.W, tk.E, tk.N, tk.S))
        main_frame.rowconfigure(10, weight=1)
        
        # Scrollbar for status text
        scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=self.status_text.yview)
        scrollbar.grid(row=10, column=3, sticky=(tk.N, tk.S), pady=10)
        self.status_text.configure(yscrollcommand=scrollbar.set)
        
        self.log_message("Desktop Shortcut Creator initialized.\n") # Initial message

    def load_applications(self):
        """Load all installed applications from .desktop files"""
        self.applications = []
        # Standard XDG application directories
        desktop_dirs = [
            "/usr/share/applications/",
            "/usr/local/share/applications/",
            f"{Path.home()}/.local/share/applications/",
            # Snap applications (these typically have their own .desktop structure that points to a launcher)
            "/var/lib/snapd/desktop/applications/",
            # Flatpak applications export their .desktop files here, often containing X-Flatpak=true
            "/var/lib/flatpak/exports/share/applications/",
            f"{Path.home()}/.local/share/flatpak/exports/share/applications/"
        ]
        
        # Add XDG_DATA_DIRS if set, typically includes more system-wide paths
        xdg_data_dirs = os.environ.get("XDG_DATA_DIRS", "").split(":")
        for d in xdg_data_dirs:
            if d and d not in desktop_dirs: # Avoid duplicates
                desktop_dirs.append(os.path.join(d, "applications"))

        # Add XDG_DATA_HOME if set, typically ~/.local/share/
        xdg_data_home = os.environ.get("XDG_DATA_HOME", f"{Path.home()}/.local/share")
        if xdg_data_home and f"{Path.home()}/.local/share/applications/" not in desktop_dirs: # Avoid duplicates
             desktop_dirs.append(os.path.join(xdg_data_home, "applications"))
             
        # Dedup and ensure paths exist
        desktop_dirs = [d for d in list(set(desktop_dirs)) if os.path.exists(d)]
        
        for directory in desktop_dirs:
            for file_path in glob.glob(f"{directory}*.desktop"):
                app_info = self.parse_desktop_file(file_path)
                # Only add if we got a valid name and an executable command
                if app_info and app_info['name'] and app_info['exec']:
                    self.applications.append(app_info)
        
        # Sort applications by name
        self.applications.sort(key=lambda x: x['name'].lower())
    
    def parse_desktop_file(self, file_path):
        """Parse a .desktop file and extract relevant information"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            desktop_dict = {}
            current_section = None
            for line in content.split('\n'):
                line = line.strip()
                if line.startswith('[') and line.endswith(']'):
                    current_section = line[1:-1]
                elif current_section == "Desktop Entry" and '=' in line:
                    key, value = line.split('=', 1)
                    desktop_dict[key] = value

            # Extract preferred values
            lang_code = os.environ.get('LANG', 'en_US.UTF-8').split('.')[0]
            name = desktop_dict.get(f'Name[{lang_code}]', desktop_dict.get('Name', ''))
            if not name:
                name = desktop_dict.get('GenericName', '')

            exec_string_original = desktop_dict.get('Exec', '') # Store the original Exec value
            icon = desktop_dict.get(f'Icon[{lang_code}]', desktop_dict.get('Icon', ''))
            comment = desktop_dict.get(f'Comment[{lang_code}]', desktop_dict.get('Comment', ''))
            categories = desktop_dict.get('Categories', '')
            terminal = desktop_dict.get('Terminal', '').lower() == 'true'
            
            # --- IMPROVED FLATPAK/SNAP HANDLING IN PARSING ---
            resolved_exec_command = exec_string_original # Default to original

            is_flatpak = desktop_dict.get('X-Flatpak', '').lower() == 'true' or \
                         file_path.startswith('/var/lib/flatpak/exports/share/applications/') or \
                         file_path.startswith(f"{Path.home()}/.local/share/flatpak/exports/share/applications/")
            
            is_snap = 'snap/gui' in exec_string_original and not is_flatpak # Snap detection

            if is_flatpak:
                # Flatpak's Exec line often looks like:
                # Exec=/usr/bin/flatpak run --branch=stable --arch=x86_64 --command=zen-browser app.zen_browser.zen @@u %U @@
                # We need to extract the 'app.zen_browser.zen' ID and form 'flatpak run <ID>'
                # Or sometimes just: Exec=flatpak run org.gnome.Lollypop
                
                # Regex to find the app ID after 'flatpak run' and before flags/placeholders
                match = re.search(r"flatpak run\s+(--[a-zA-Z0-9=\-\.]+?\s+)*?([a-zA-Z0-9\.\-_]+)(?=\s|\Z)", exec_string_original)
                if match:
                    flatpak_id = match.group(2)
                    resolved_exec_command = f"flatpak run {flatpak_id}"
                    # Often the icon is also just the Flatpak ID
                    if not icon or icon == exec_string_original.split('/')[-1].split(' ')[0]: # If icon is generic or derived from exec
                        icon = flatpak_id
                    self.log_message(f"DEBUG: Identified Flatpak '{name}' (ID: {flatpak_id}), simplified Exec to: '{resolved_exec_command}'\n")
                else:
                    self.log_message(f"WARNING: Could not parse Flatpak ID from Exec '{exec_string_original}' for '{name}'. Using original.\n")
                    resolved_exec_command = exec_string_original # Fallback
            elif is_snap:
                # Snap apps also use a wrapper. Their Exec looks like /snap/bin/appname or /usr/bin/env snap run appname
                # We generally want to preserve the original Exec for snap, or simplify to 'snap run <snap_name>'
                # For this script, we'll try to use the raw Exec value if it's already a snap command.
                # If it's a direct path to a snap wrapper, e.g. /snap/vlc/current/desktop-launch, just use that.
                self.log_message(f"DEBUG: Identified Snap app '{name}', using original Exec: '{exec_string_original}'\n")
                resolved_exec_command = exec_string_original
            else:
                # For regular apps, try to resolve the executable path
                resolved_exec_command = self.find_executable_path(exec_string_original)
            # --- END IMPROVED FLATPAK/SNAP HANDLING ---
            
            return {
                'name': name,
                'exec': exec_string_original, # Keep original exec string as read from file
                'resolved_path': resolved_exec_command, # This is what will be shown/used in GUI and for shortcut's Exec
                'icon': icon,
                'comment': comment,
                'categories': categories,
                'terminal': terminal,
                'desktop_file': file_path
            }
        except Exception as e:
            self.log_message(f"WARNING: Error parsing desktop file {file_path}: {e}\n")
            return None
    
    def find_executable_path(self, exec_string):
        """Find the actual executable path from the Exec string for non-Flatpak/Snap apps."""
        try:
            exec_parts = shlex.split(exec_string)
        except ValueError:
            self.log_message(f"WARNING: Malformed Exec string '{exec_string}'. Attempting fallback split.\n")
            exec_parts = [part.strip('"\'') for part in exec_string.split() if part.strip()]

        if not exec_parts:
            return exec_string
        
        exec_candidate = exec_parts[0]
        exec_candidate = exec_candidate.split('%')[0].strip() # Remove placeholders

        if not exec_candidate:
            return exec_string

        # Case 1: Absolute path
        if os.path.isabs(exec_candidate):
            if os.path.exists(exec_candidate) and os.access(exec_candidate, os.X_OK):
                return exec_candidate
            else:
                self.log_message(f"DEBUG: Absolute path '{exec_candidate}' not found or not executable.\n")
        
        # Case 2: Command in PATH
        try:
            result = subprocess.run(['which', exec_candidate], 
                                    capture_output=True, text=True, check=False)
            if result.returncode == 0:
                resolved_path = result.stdout.strip()
                if os.access(resolved_path, os.X_OK):
                    return resolved_path
                else:
                    self.log_message(f"DEBUG: Found '{resolved_path}' via which, but it's not executable.\n")
            else:
                self.log_message(f"DEBUG: 'which {exec_candidate}' failed: {result.stderr.strip()}\n")
        except FileNotFoundError:
            self.log_message("WARNING: 'which' command not found. Cannot resolve executables in PATH.\n")
        except Exception as e:
            self.log_message(f"WARNING: Error running 'which' for '{exec_candidate}': {e}\n")
        
        return exec_string  # Return original Exec string as fallback if we can't resolve or not executable
    
    def refresh_applications(self):
        """Refresh the applications list"""
        self.log_message("Refreshing applications list...\n")
        self.load_applications()
        self.update_app_dropdown()
        self.log_message(f"Found {len(self.applications)} applications.\n")
    
    def update_app_dropdown(self):
        """Update the application dropdown with current applications"""
        app_names = [f"{app['name']}" for app in self.applications if app['name']] # Ensure name exists
        self.app_combo['values'] = app_names
        if app_names:
            self.app_combo.set("")  # Clear selection
    
    def on_app_selected(self, event=None):
        """Handle application selection from dropdown"""
        selected_name = self.app_var.get()
        if not selected_name:
            return
        
        # Find the selected application by name
        selected_app = next((app for app in self.applications if app['name'] == selected_name), None)
        
        if selected_app:
            # Auto-fill fields, but only if they are currently empty or if the user explicitly clears them later
            if not self.name_var.get() or self.name_var.get() == selected_name: # Avoid overwriting user's custom name
                self.name_var.set(selected_app['name'])
            
            # Use resolved_path for display, which now can be 'flatpak run <ID>' or actual binary path
            self.path_var.set(selected_app['resolved_path'])
            
            if selected_app['icon']:
                self.icon_var.set(selected_app['icon'])
            else:
                self.icon_var.set("") # Clear if no icon for this app

            if selected_app['comment']:
                self.desc_var.set(selected_app['comment'])
            else:
                self.desc_var.set("") # Clear if no comment for this app
            
            # Set category based on the app's categories (more comprehensive matching)
            if selected_app['categories']:
                categories_lower = selected_app['categories'].lower()
                if 'game' in categories_lower:
                    self.categories_var.set('Game')
                elif 'development' in categories_lower or 'programming' in categories_lower or 'ide' in categories_lower:
                    self.categories_var.set('Development')
                elif 'office' in categories_lower or 'wordprocessor' in categories_lower or 'spreadsheet' in categories_lower or 'presentation' in categories_lower:
                    self.categories_var.set('Office')
                elif 'graphics' in categories_lower or 'image' in categories_lower or 'photography' in categories_lower or 'design' in categories_lower:
                    self.categories_var.set('Graphics')
                elif 'audiovideo' in categories_lower or 'audio' in categories_lower or 'video' in categories_lower or 'sound' in categories_lower:
                    self.categories_var.set('AudioVideo')
                elif 'network' in categories_lower or 'internet' in categories_lower or 'webbrowser' in categories_lower:
                    self.categories_var.set('Network')
                elif 'system' in categories_lower or 'utility' in categories_lower or 'settings' in categories_lower:
                    self.categories_var.set('System')
                elif 'education' in categories_lower:
                    self.categories_var.set('Education')
                elif 'science' in categories_lower:
                    self.categories_var.set('Science')
                elif 'finance' in categories_lower:
                    self.categories_var.set('Finance')
                else:
                    self.categories_var.set('Application') # Default if no specific match
            else:
                self.categories_var.set('Application') # Default if no categories found
            
            self.terminal_var.set(selected_app['terminal'])
            
            self.log_message(f"Selected: {selected_app['name']}\n")
            self.log_message(f"Original Exec (from .desktop file): {selected_app['exec']}\n")
            self.log_message(f"Resolved Path (for display/shortcut): {selected_app['resolved_path']}\n")
            self.log_message(f"Icon: {selected_app['icon']}\n")

    def browse_application(self):
        """Browse for an application executable"""
        # Note: Browsing for flatpaks directly is tricky as they are in a sandbox.
        # This function is primarily for traditional executables or AppImages.
        file_path = filedialog.askopenfilename(
            title="Select Application Executable",
            filetypes=[
                ("Executable files", "*"), # Allow any file, as executables may not have an extension
                ("AppImage files", "*.AppImage"),
                ("Binary files", "*"),
                ("All files", "*.*")
            ]
        )
        if file_path:
            self.path_var.set(file_path)
            # Auto-fill name if empty
            if not self.name_var.get():
                name = Path(file_path).stem
                self.name_var.set(name)
                
    def browse_icon(self):
        """Browse for an icon file"""
        file_path = filedialog.askopenfilename(
            title="Select Icon",
            filetypes=[
                ("Image files", "*.png *.svg *.jpg *.jpeg *.ico *.xpm"),
                ("All files", "*.*")
            ]
        )
        if file_path:
            self.icon_var.set(file_path)
            
    def browse_destination(self):
        """Browse for destination directory"""
        dir_path = filedialog.askdirectory(title="Select Destination Directory")
        if dir_path:
            self.dest_var.set(dir_path)
            
    def clear_fields(self):
        """Clear all input fields"""
        self.name_var.set("")
        self.app_var.set("")
        self.path_var.set("")
        self.icon_var.set("")
        self.desc_var.set("")
        self.categories_var.set("Application")
        self.terminal_var.set(False)
        self.dest_var.set(str(self.desktop_path))
        self.log_message("Fields cleared.\n")
        
    def log_message(self, message):
        """Add a message to the status text area"""
        self.status_text.insert(tk.END, message)
        self.status_text.see(tk.END) # Scroll to end
        self.root.update_idletasks() # Force update
        
    def create_shortcut(self):
        """Create the desktop shortcut file"""
        # Validate inputs
        name = self.name_var.get().strip()
        
        # We use the text from the path_var directly for Exec=
        # This will already contain "flatpak run <ID>" for flatpaks or a normal path for others
        exec_command = self.path_var.get().strip() 
        
        if not name:
            messagebox.showerror("Error", "Please enter a shortcut name.")
            self.log_message("ERROR: Shortcut name is empty.\n")
            return
            
        if not exec_command:
            messagebox.showerror("Error", "Please select an application or enter its path/command.")
            self.log_message("ERROR: Application path/command is empty.\n")
            return
        
        # --- UPDATED PATH= LOGIC (more refined check) ---
        working_dir = ""
        # Check if it's explicitly a Flatpak or Snap command.
        # This ensures we don't try to derive a Path= for these sandboxed apps.
        if exec_command.startswith("flatpak run") or exec_command.startswith("snap run"):
            working_dir = "" # Path= field is typically not needed for Flatpaks/Snaps
            self.log_message("DEBUG: Detected Flatpak/Snap command, skipping Path= field.\n")
        else:
            # For regular applications, try to determine a working directory
            # If the entered exec_command is an absolute path to a file or directory
            if Path(exec_command).is_absolute() and Path(exec_command).exists():
                if Path(exec_command).is_dir(): # if it's a directory (e.g., a script wrapper)
                    working_dir = str(Path(exec_command))
                elif Path(exec_command).is_file(): # if it's a file
                    working_dir = str(Path(exec_command).parent)
            else:
                # If it's not an absolute path, assume it's a command in PATH and try to find its parent.
                resolved_bin_path = self.find_executable_path(exec_command)
                if Path(resolved_bin_path).is_absolute() and Path(resolved_bin_path).is_file():
                    working_dir = str(Path(resolved_bin_path).parent)
                else:
                    self.log_message(f"WARNING: Could not determine working directory for '{exec_command}'. Path= field will be empty.\n")
        # --- END UPDATED PATH= LOGIC ---
        
        # Prepare desktop file content
        desktop_content = "[Desktop Entry]\n"
        desktop_content += "Version=1.0\n"
        desktop_content += "Type=Application\n"
        desktop_content += f"Name={name}\n"
        desktop_content += f"Exec={exec_command}\n" # Use the validated exec_command directly
        if working_dir: # Only add Path if a valid working directory is determined
            desktop_content += f"Path={working_dir}\n" 
        
        # Optional fields
        if self.desc_var.get().strip():
            desktop_content += f"Comment={self.desc_var.get().strip()}\n"
            
        if self.icon_var.get().strip():
            desktop_content += f"Icon={self.icon_var.get().strip()}\n"
            
        if self.categories_var.get().strip():
            desktop_content += f"Categories={self.categories_var.get().strip()};\n"
            
        desktop_content += f"Terminal={str(self.terminal_var.get()).lower()}\n"
        desktop_content += "StartupNotify=true\n"
        
        # Create the desktop file
        try:
            dest_dir = Path(self.dest_var.get())
            if not dest_dir.exists():
                self.log_message(f"Creating destination directory: {dest_dir}\n")
                dest_dir.mkdir(parents=True, exist_ok=True)
                
            # Clean filename: replace invalid chars for filename with underscore, then remove leading/trailing spaces/dots
            safe_name = "".join(c if c.isalnum() or c in (' ', '-', '_', '.') else '_' for c in name).strip().replace('__', '_')
            if not safe_name: # Fallback if name becomes empty after cleaning
                safe_name = "untitled_shortcut"
            
            desktop_file_path = dest_dir / f"{safe_name}.desktop"
            
            # Handle potential file overwrite
            if desktop_file_path.exists():
                response = messagebox.askyesno("File Exists", 
                                               f"Shortcut file '{desktop_file_path.name}' already exists in '{dest_dir}'. Do you want to overwrite it?",
                                               icon='warning')
                if not response:
                    self.log_message(f"User cancelled overwrite of {desktop_file_path}\n")
                    return
            
            # Write the file
            with open(desktop_file_path, 'w', encoding='utf-8') as f:
                f.write(desktop_content)
                
            # Make it executable (user, group, others can execute)
            os.chmod(desktop_file_path, 0o755)
            
            self.log_message(f"✓ Successfully created shortcut: {desktop_file_path}\n")
            self.log_message(f"  Name: {name}\n")
            self.log_message(f"  Exec: {exec_command}\n")
            if working_dir:
                self.log_message(f"  Path: {working_dir}\n")
            if self.icon_var.get().strip():
                self.log_message(f"  Icon: {self.icon_var.get().strip()}\n")
            self.log_message("\n")
            
            messagebox.showinfo("Success", f"Shortcut created successfully!\n\nLocation: {desktop_file_path}")
            
        except Exception as e:
            error_msg = f"Error creating shortcut: {str(e)}"
            self.log_message(f"✗ {error_msg}\n\n")
            messagebox.showerror("Error", error_msg)

def main():
    root = tk.Tk()
    try:
        pass
    except tk.TclError:
        pass
    
    app = ShortcutCreator(root)
    root.mainloop()

if __name__ == "__main__":
    main()

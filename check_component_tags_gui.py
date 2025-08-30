#!/usr/bin/env python3
"""
GUI for the Component Tag Checker.

This script provides a graphical user interface for the component tag checker.
"""

import os
import sys
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
import threading

# Import the component tag checker module
try:
    from check_component_tags import parse_cmake_file, check_component_tag, resolve_path
except ImportError:
    messagebox.showerror("Error", "Could not import check_component_tags.py. Make sure it's in the same directory.")
    sys.exit(1)

# Global variables
MISALIGNED_COMPONENTS = []

class ComponentTagCheckerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Component Tag Checker")
        self.root.geometry("1000x700")
        self.root.minsize(1000, 700)
        
        # Set icon if available
        try:
            self.root.iconbitmap("icon.ico")
        except:
            pass
        
        # Create the main frame
        main_frame = ttk.Frame(root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create the input frame
        input_frame = ttk.LabelFrame(main_frame, text="Input", padding="10")
        input_frame.pack(fill=tk.X, pady=5)
        
        # CMake file selection
        ttk.Label(input_frame, text="CMake File:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.cmake_file_var = tk.StringVar(value="S32K/EDx/build.cmake")
        cmake_file_entry = ttk.Entry(input_frame, textvariable=self.cmake_file_var, width=50)
        cmake_file_entry.grid(row=0, column=1, sticky=tk.W+tk.E, pady=5, padx=5)
        ttk.Button(input_frame, text="Browse...", command=self.browse_cmake_file).grid(row=0, column=2, pady=5)
        
        # Target selection frame
        target_frame = ttk.LabelFrame(input_frame, text="Target Selection", padding="5")
        target_frame.grid(row=1, column=0, columnspan=3, sticky=tk.W+tk.E, pady=5)
        
        # Target checkboxes
        self.target_vars = {}
        self.target_checkbuttons = {}
        self.targets_frame = ttk.Frame(target_frame)
        self.targets_frame.pack(fill=tk.X, expand=True)
        
        # Add "Select All" checkbox
        self.select_all_var = tk.BooleanVar(value=True)
        self.select_all_checkbutton = ttk.Checkbutton(
            target_frame, 
            text="Select All Targets", 
            variable=self.select_all_var,
            command=self.toggle_all_targets
        )
        self.select_all_checkbutton.pack(anchor=tk.W, pady=(0, 5))
        
        # Refresh targets button
        ttk.Button(target_frame, text="Refresh Targets", command=self.refresh_targets).pack(anchor=tk.E)
        
        # Output file selection
        ttk.Label(input_frame, text="Output File:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.output_file_var = tk.StringVar()
        output_file_entry = ttk.Entry(input_frame, textvariable=self.output_file_var, width=50)
        output_file_entry.grid(row=2, column=1, sticky=tk.W+tk.E, pady=5, padx=5)
        ttk.Button(input_frame, text="Browse...", command=self.browse_output_file).grid(row=2, column=2, pady=5)
        
        # Verbose option
        self.verbose_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(input_frame, text="Verbose Output", variable=self.verbose_var).grid(row=3, column=0, columnspan=3, sticky=tk.W, pady=5)
        
        # Configure grid columns
        input_frame.columnconfigure(1, weight=1)
        
        # Create the action frame
        action_frame = ttk.Frame(main_frame)
        action_frame.pack(fill=tk.X, pady=5)
        
        # Run button
        self.run_button = ttk.Button(action_frame, text="Run Check", command=self.run_check)
        self.run_button.pack(side=tk.RIGHT, padx=5)
        
        # Progress bar
        self.progress_var = tk.DoubleVar()
        self.progress = ttk.Progressbar(action_frame, variable=self.progress_var, maximum=100)
        self.progress.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Create a notebook with tabs
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Create the output frame (first tab)
        output_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(output_frame, text="Output")
        
        # Output text
        self.output_text = scrolledtext.ScrolledText(output_frame, wrap=tk.WORD, width=80, height=20)
        self.output_text.pack(fill=tk.BOTH, expand=True)
        self.output_text.config(state=tk.DISABLED)
        
        # Create the misaligned components frame (second tab)
        self.misaligned_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(self.misaligned_frame, text="Misaligned Components")
        
        # Create a frame for the misaligned components list
        list_frame = ttk.Frame(self.misaligned_frame)
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create a treeview for the misaligned components
        self.tree = ttk.Treeview(list_frame, columns=("Module", "Target", "Path", "Expected Tag", "Actual Tag", "Status"), show="headings")
        self.tree.heading("Module", text="Module")
        self.tree.heading("Target", text="Target")
        self.tree.heading("Path", text="Path")
        self.tree.heading("Expected Tag", text="Expected Tag")
        self.tree.heading("Actual Tag", text="Actual Tag")
        self.tree.heading("Status", text="Status")
        
        self.tree.column("Module", width=150)
        self.tree.column("Target", width=80)
        self.tree.column("Path", width=250)
        self.tree.column("Expected Tag", width=100)
        self.tree.column("Actual Tag", width=100)
        self.tree.column("Status", width=250)
        
        # Add a scrollbar to the treeview
        tree_scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll.set)
        
        # Pack the treeview and scrollbar
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Create a frame for the buttons
        button_frame = ttk.Frame(self.misaligned_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        # Add buttons for selecting/deselecting all and updating selected components
        ttk.Button(button_frame, text="Select All", command=self.select_all).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Deselect All", command=self.deselect_all).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Update Selected Components", command=self.update_selected_components).pack(side=tk.RIGHT, padx=5)
        
        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Store misaligned components
        self.misaligned_components = []
        
        # Try to refresh targets on startup
        self.refresh_targets()
    
    def browse_cmake_file(self):
        """Open a file dialog to select a CMake file."""
        file_path = filedialog.askopenfilename(
            title="Select CMake File",
            filetypes=[("CMake Files", "*.cmake"), ("All Files", "*.*")]
        )
        if file_path:
            self.cmake_file_var.set(file_path)
            self.refresh_targets()
    
    def browse_output_file(self):
        """Open a file dialog to select an output file."""
        file_path = filedialog.asksaveasfilename(
            title="Select Output File",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")],
            defaultextension=".txt"
        )
        if file_path:
            self.output_file_var.set(file_path)
    
    def refresh_targets(self):
        """Refresh the list of targets from the CMake file."""
        cmake_file = self.cmake_file_var.get()
        if not os.path.exists(cmake_file):
            messagebox.showerror("Error", f"CMake file does not exist: {cmake_file}")
            return
        
        try:
            self.status_var.set(f"Parsing {cmake_file}...")
            self.root.update_idletasks()
            
            # Clear existing checkboxes
            for widget in self.targets_frame.winfo_children():
                widget.destroy()
            self.target_vars.clear()
            self.target_checkbuttons.clear()
            
            modules_sections = parse_cmake_file(cmake_file)
            targets = list(modules_sections.keys())
            
            if targets:
                # Create a horizontal flow of checkboxes
                for target in targets:
                    self.target_vars[target] = tk.BooleanVar(value=True)
                    cb = ttk.Checkbutton(
                        self.targets_frame, 
                        text=target, 
                        variable=self.target_vars[target],
                        command=self.update_select_all_state
                    )
                    cb.pack(side=tk.LEFT, padx=10, pady=5)
                    self.target_checkbuttons[target] = cb
                
                self.status_var.set(f"Found {len(targets)} targets")
            else:
                ttk.Label(self.targets_frame, text="No targets found").pack()
                self.status_var.set("No targets found in the CMake file")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to parse CMake file: {e}")
            self.status_var.set("Ready")
    
    def toggle_all_targets(self):
        """Toggle all target checkboxes based on the select all checkbox."""
        select_all = self.select_all_var.get()
        for target, var in self.target_vars.items():
            var.set(select_all)
    
    def update_select_all_state(self):
        """Update the select all checkbox state based on individual checkboxes."""
        all_selected = all(var.get() for var in self.target_vars.values())
        self.select_all_var.set(all_selected)
    
    def run_check(self):
        """Run the component tag check."""
        cmake_file = self.cmake_file_var.get()
        selected_targets = [target for target, var in self.target_vars.items() if var.get()]
        output_file = self.output_file_var.get()
        verbose = self.verbose_var.get()
        
        if not os.path.exists(cmake_file):
            messagebox.showerror("Error", f"CMake file does not exist: {cmake_file}")
            return
        
        if not selected_targets and self.target_vars:
            messagebox.showinfo("Info", "Please select at least one target")
            return
        
        # Disable the run button and clear the output
        self.run_button.config(state=tk.DISABLED)
        self.output_text.config(state=tk.NORMAL)
        self.output_text.delete(1.0, tk.END)
        self.output_text.config(state=tk.DISABLED)
        self.progress_var.set(0)
        
        # Run the check in a separate thread
        thread = threading.Thread(target=self.run_check_thread, args=(cmake_file, selected_targets, output_file, verbose))
        thread.daemon = True
        thread.start()
    
    def run_check_thread(self, cmake_file, selected_targets, output_file, verbose):
        """Run the component tag check in a separate thread."""
        try:
            # Parse the CMake file
            self.update_status("Parsing CMake file...")
            modules_sections = parse_cmake_file(cmake_file)
            
            # Filter targets based on selection
            targets_to_check = {}
            
            # If no targets are explicitly selected but we have target checkboxes,
            # this means none were selected (not "All Targets")
            if not selected_targets and self.target_vars:
                self.update_output("No targets selected. Please select at least one target.")
                self.update_status("Ready")
                self.run_button.config(state=tk.NORMAL)
                return
            
            # If targets are selected, only check those
            if selected_targets:
                for target in selected_targets:
                    if target in modules_sections:
                        targets_to_check[target] = modules_sections[target]
                    else:
                        self.update_output(f"Warning: Target '{target}' not found in the CMake file.")
                
                if not targets_to_check:
                    self.update_output("Error: None of the selected targets were found in the CMake file.")
                    self.update_output(f"Available targets: {', '.join(modules_sections.keys())}")
                    self.update_status("Ready")
                    self.run_button.config(state=tk.NORMAL)
                    return
            else:
                # This case is only reached if no target checkboxes exist yet
                # (first run before parsing targets)
                targets_to_check = modules_sections
            
            # Get the directory of the CMake file
            cmake_file_dir = os.path.dirname(os.path.abspath(cmake_file))
            
            # Clear the treeview
            for item in self.tree.get_children():
                self.tree.delete(item)
            
            # Check each component
            self.misaligned_components = []
            total_components = 0
            
            for target_name, components in targets_to_check.items():
                self.update_output(f"\nChecking components for target: {target_name}")
                self.update_output(f"Found {len(components)} components")
                total_components += len(components)
                
                for i, component in enumerate(components):
                    module_name = component['module_name']
                    path = component['path']
                    expected_tag = component['tag']
                    
                    # Update progress
                    progress = (i + 1) / len(components) * 100
                    self.progress_var.set(progress)
                    self.update_status(f"Checking component {i + 1} of {len(components)}: {module_name}")
                    
                    if verbose:
                        self.update_output(f"\nChecking component: {module_name}")
                        self.update_output(f"  Path: {path}")
                        self.update_output(f"  Expected tag: {expected_tag}")
                    else:
                        self.update_output(f"\nChecking component: {module_name}...", end="")
                    
                    is_aligned, actual_tag, expected_tag, error_message = check_component_tag(component, cmake_file_dir)
                    
                    if is_aligned:
                        if verbose:
                            self.update_output(f"  Status: ALIGNED (tag: {actual_tag})")
                        else:
                            self.update_output(" ALIGNED")
                    else:
                        if verbose:
                            self.update_output(f"  Status: NOT ALIGNED")
                            if actual_tag:
                                self.update_output(f"  Actual tag: {actual_tag}")
                            if error_message:
                                self.update_output(f"  Error: {error_message}")
                        else:
                            self.update_output(" NOT ALIGNED")
                            self.update_output(f"  Error: {error_message}")
                        
                        component_info = {
                            'target': target_name,
                            'module_name': module_name,
                            'path': path,
                            'expected_tag': expected_tag,
                            'actual_tag': actual_tag if actual_tag else "",
                            'error_message': error_message,
                            'resolved_path': resolve_path(path, cmake_file_dir)
                        }
                        self.misaligned_components.append(component_info)
                        
                        # Add to treeview
                        self.tree.insert("", "end", values=(
                            module_name,
                            target_name,
                            path,
                            expected_tag,
                            actual_tag if actual_tag else "",
                            error_message
                        ))
                        
                        # If the error message indicates commits after tag, highlight it differently
                        if "commits after the tag" in error_message or "uncommitted changes" in error_message:
                            last_item = self.tree.get_children()[-1]
                            self.tree.item(last_item, tags=("modified",))
                            
                # Configure tag colors
                self.tree.tag_configure("modified", background="#FFF9C4")  # Light yellow for modified repos
            
            # Print summary
            self.update_output("\n=== Summary ===")
            if self.misaligned_components:
                self.update_output(f"Found {len(self.misaligned_components)} misaligned components out of {total_components} total components:")
                for component in self.misaligned_components:
                    self.update_output(f"- {component['module_name']} (target: {component['target']})")
                    self.update_output(f"  Expected tag: {component['expected_tag']}")
                    if component['actual_tag']:
                        self.update_output(f"  Actual tag: {component['actual_tag']}")
                    self.update_output(f"  Error: {component['error_message']}")
                
                # Calculate percentage of misaligned components
                percentage = (len(self.misaligned_components) / total_components) * 100
                self.update_output(f"\nPercentage of misaligned components: {percentage:.2f}%")
                
                # Switch to the misaligned components tab
                self.notebook.select(1)
            else:
                self.update_output(f"All {total_components} components are aligned with their expected tags.")
            
            # Write report to file if specified
            if output_file:
                try:
                    with open(output_file, 'w') as f:
                        f.write("=== Component Tag Alignment Report ===\n\n")
                        f.write(f"CMake file: {cmake_file}\n")
                        f.write(f"Total components checked: {total_components}\n")
                        
                        if self.misaligned_components:
                            f.write(f"Misaligned components: {len(self.misaligned_components)} ({percentage:.2f}%)\n\n")
                            f.write("Details of misaligned components:\n")
                            for component in self.misaligned_components:
                                f.write(f"- {component['module_name']} (target: {component['target']})\n")
                                f.write(f"  Path: {component['path']}\n")
                                f.write(f"  Expected tag: {component['expected_tag']}\n")
                                if component['actual_tag']:
                                    f.write(f"  Actual tag: {component['actual_tag']}\n")
                                f.write(f"  Error: {component['error_message']}\n\n")
                        else:
                            f.write("All components are aligned with their expected tags.\n")
                    
                    self.update_output(f"\nReport written to {output_file}")
                except Exception as e:
                    self.update_output(f"Error writing report to {output_file}: {e}")
            
            self.update_status("Ready")
        except Exception as e:
            self.update_output(f"Error: {e}")
            self.update_status("Error")
        finally:
            self.run_button.config(state=tk.NORMAL)
    
    def update_output(self, text, end="\n"):
        """Update the output text widget."""
        self.output_text.config(state=tk.NORMAL)
        self.output_text.insert(tk.END, text + end)
        self.output_text.see(tk.END)
        self.output_text.config(state=tk.DISABLED)
        self.root.update_idletasks()
    
    def update_status(self, text):
        """Update the status bar."""
        self.status_var.set(text)
        self.root.update_idletasks()
    
    def select_all(self):
        """Select all items in the treeview."""
        for item in self.tree.get_children():
            self.tree.selection_add(item)
    
    def deselect_all(self):
        """Deselect all items in the treeview."""
        for item in self.tree.get_children():
            self.tree.selection_remove(item)
    
    def update_selected_components(self):
        """Update selected components to their expected tags."""
        selected_items = self.tree.selection()
        if not selected_items:
            messagebox.showinfo("Info", "No components selected")
            return
        
        # Confirm update
        if not messagebox.askyesno("Confirm Update", "Are you sure you want to update the selected components to their expected tags?"):
            return
        
        # Get selected components
        selected_indices = [self.tree.index(item) for item in selected_items]
        selected_components = [self.misaligned_components[i] for i in selected_indices]
        
        # Update components
        updated_count = 0
        failed_count = 0
        
        for component in selected_components:
            try:
                self.update_status(f"Updating {component['module_name']}...")
                
                # Change to the component directory
                original_dir = os.getcwd()
                os.chdir(component['resolved_path'])
                
                # Create a VERSION file with the expected tag
                with open('VERSION', 'w') as f:
                    f.write(component['expected_tag'])
                
                # Try to set git tag if it's a git repository
                try:
                    # Check if it's a git repository
                    result = subprocess.run(['git', 'rev-parse', '--is-inside-work-tree'], 
                                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    
                    if result.returncode == 0:
                        # Delete existing tag if it exists
                        subprocess.run(['git', 'tag', '-d', component['expected_tag']], 
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        
                        # Create new tag
                        subprocess.run(['git', 'tag', component['expected_tag']], 
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                except Exception as e:
                    # Ignore git errors, we've already created the VERSION file
                    pass
                
                # Change back to the original directory
                os.chdir(original_dir)
                
                updated_count += 1
            except Exception as e:
                failed_count += 1
                self.update_output(f"Error updating {component['module_name']}: {e}")
        
        # Show results
        if failed_count == 0:
            messagebox.showinfo("Update Complete", f"Successfully updated {updated_count} components")
        else:
            messagebox.showwarning("Update Complete", f"Updated {updated_count} components, {failed_count} failed")
        
        # Re-run the check to refresh the display
        self.run_check()

def main():
    """Main function."""
    root = tk.Tk()
    app = ComponentTagCheckerGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()

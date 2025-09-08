#!/usr/bin/env python3
"""
GUI for the Repo Maintenance Tool.

This script provides a graphical user interface for repository maintenance tasks,
including component tag checking and other features to be added in the future.
"""

import os
import sys
import re
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
import threading

# Import the component tag checker module
try:
    from check_component_tags import parse_cmake_file, check_component_tag, resolve_path, clone_component
except ImportError:
    messagebox.showerror("Error", "Could not import check_component_tags.py. Make sure it's in the same directory.")
    sys.exit(1)

# Global variables
MISALIGNED_COMPONENTS = []

class ComponentTagCheckerGUI:
    # Add version number
    VERSION = "1.1.0"
    
    def __init__(self, root):
        self.root = root
        self.root.title(f"Repo Maintenance Tool v{self.VERSION}")
        self.root.geometry("1000x700")
        self.root.minsize(1000, 700)
        
        # Set icon using absolute path to ensure it's found
        icon_path = "C:\\Users\\NTadepalli\\Desktop\\CustomTool\\RepoMaintenance\\icon.ico"
        try:
            self.root.iconbitmap(icon_path)
        except Exception as e:
            print(f"Failed to set icon: {e}")
        
        # Create the main frame
        main_frame = ttk.Frame(root, padding="5")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create the top control panel
        control_panel = ttk.Frame(main_frame)
        control_panel.pack(fill=tk.X, pady=2)
        
        # CMake file selection
        file_frame = ttk.Frame(control_panel)
        file_frame.pack(fill=tk.X, pady=2)
        
        ttk.Label(file_frame, text="CMake File:").pack(side=tk.LEFT, padx=2)
        self.cmake_file_var = tk.StringVar(value="S32K/EDx/build.cmake")
        cmake_file_entry = ttk.Entry(file_frame, textvariable=self.cmake_file_var, width=50)
        cmake_file_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        ttk.Button(file_frame, text="Browse", command=self.browse_cmake_file, width=8).pack(side=tk.LEFT, padx=2)
        
        # Target selection and controls
        target_control_frame = ttk.Frame(control_panel)
        target_control_frame.pack(fill=tk.X, pady=2)
        
        # Left side - Refresh button only
        target_left_frame = ttk.Frame(target_control_frame)
        target_left_frame.pack(side=tk.LEFT, fill=tk.Y)
        
        # Keep the select_all_var for internal use but don't show the checkbox
        self.select_all_var = tk.BooleanVar(value=True)
        
        ttk.Button(target_left_frame, text="Refresh", command=self.refresh_targets, width=8).pack(side=tk.LEFT, padx=2)
        
        # Keep verbose var but set to True by default and don't show the checkbox
        self.verbose_var = tk.BooleanVar(value=True)
        
        # Right side - Run and Clear buttons
        target_right_frame = ttk.Frame(target_control_frame)
        target_right_frame.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.clear_button = ttk.Button(target_right_frame, text="Clear", command=self.clear_results, width=8)
        self.clear_button.pack(side=tk.RIGHT, padx=2)
        
        self.run_button = ttk.Button(target_right_frame, text="Run Check", command=self.run_check, width=10)
        self.run_button.pack(side=tk.RIGHT, padx=2)
        
        # Target checkboxes frame
        targets_container = ttk.LabelFrame(control_panel, text="Targets")
        targets_container.pack(fill=tk.X, pady=2)
        
        # Target checkboxes
        self.target_vars = {}
        self.target_checkbuttons = {}
        self.targets_frame = ttk.Frame(targets_container)
        self.targets_frame.pack(fill=tk.X, expand=True, padx=2, pady=2)
        
        # Add base URL field
        url_frame = ttk.Frame(control_panel)
        url_frame.pack(fill=tk.X, pady=2)
        
        ttk.Label(url_frame, text="Repository Base URL:").pack(side=tk.LEFT, padx=2)
        self.base_url_var = tk.StringVar(value="https://bitbucket.harman.com/scm/casco/")
        base_url_entry = ttk.Entry(url_frame, textvariable=self.base_url_var, width=50)
        base_url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        
        # No longer need output file variable
        
        # Progress bar
        self.progress_var = tk.DoubleVar()
        self.progress = ttk.Progressbar(control_panel, variable=self.progress_var, maximum=100)
        self.progress.pack(fill=tk.X, expand=True, padx=2, pady=2)
        
        # Create a notebook with tabs
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=2)
        
        # Create the output frame (first tab)
        output_frame = ttk.Frame(self.notebook, padding="5")
        self.notebook.add(output_frame, text="Output")
        
        # Output text
        self.output_text = scrolledtext.ScrolledText(output_frame, wrap=tk.WORD)
        self.output_text.pack(fill=tk.BOTH, expand=True)
        self.output_text.config(state=tk.DISABLED)
        
        # Create the misaligned components frame (second tab)
        self.misaligned_frame = ttk.Frame(self.notebook, padding="5")
        self.notebook.add(self.misaligned_frame, text="Misaligned Components")
        
        # Create the local changes frame (third tab)
        self.local_changes_frame = ttk.Frame(self.notebook, padding="5")
        self.notebook.add(self.local_changes_frame, text="Local Changes")
        
        # Create a frame for the local changes list
        local_changes_list_frame = ttk.Frame(self.local_changes_frame)
        local_changes_list_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create a treeview for the components with local changes
        self.local_changes_tree = ttk.Treeview(local_changes_list_frame, 
                                                 columns=("Module", "Target", "Path", "Change Location", "Status"), 
                                                 show="headings")
        
        self.local_changes_tree.heading("Module", text="Module")
        self.local_changes_tree.heading("Target", text="Target")
        self.local_changes_tree.heading("Path", text="Path")
        self.local_changes_tree.heading("Change Location", text="Change Location")
        self.local_changes_tree.heading("Status", text="Status")
        
        self.local_changes_tree.column("Module", width=150)
        self.local_changes_tree.column("Target", width=100)
        self.local_changes_tree.column("Path", width=250)
        self.local_changes_tree.column("Change Location", width=250)
        self.local_changes_tree.column("Status", width=150)
        
        # Add a scrollbar to the local changes treeview
        local_changes_tree_scroll = ttk.Scrollbar(local_changes_list_frame, orient="vertical", command=self.local_changes_tree.yview)
        self.local_changes_tree.configure(yscrollcommand=local_changes_tree_scroll.set)
        
        # Pack the local changes treeview and scrollbar
        self.local_changes_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        local_changes_tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Create a compact button bar for local changes tab
        local_changes_button_frame = ttk.Frame(self.local_changes_frame)
        local_changes_button_frame.pack(fill=tk.X, pady=2)
        
        # Add buttons for selecting/deselecting all and reverting selected changes
        ttk.Button(local_changes_button_frame, text="Select All", command=self.select_all_local_changes, width=10).pack(side=tk.LEFT, padx=2)
        ttk.Button(local_changes_button_frame, text="Deselect All", command=self.deselect_all_local_changes, width=10).pack(side=tk.LEFT, padx=2)
        ttk.Button(local_changes_button_frame, text="Revert Changes", command=self.revert_selected_changes, width=15).pack(side=tk.RIGHT, padx=2)
        
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
        
        # Local Changes tab has been removed
        
        # Add a scrollbar to the treeview
        tree_scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll.set)
        
        # Pack the treeview and scrollbar
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Create a compact button bar for misaligned components tab
        button_frame = ttk.Frame(self.misaligned_frame)
        button_frame.pack(fill=tk.X, pady=2)
        
        # Add buttons for selecting/deselecting all and updating selected components
        ttk.Button(button_frame, text="Select All", command=self.select_all, width=10).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="Deselect All", command=self.deselect_all, width=10).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="Update Selected", command=self.update_selected_components, width=15).pack(side=tk.RIGHT, padx=2)
        
        # Local Changes tab has been removed
        
        # Status bar with version number
        self.status_var = tk.StringVar(value="Ready")
        status_frame = ttk.Frame(root)
        status_frame.pack(side=tk.BOTTOM, fill=tk.X)
        
        status_bar = ttk.Label(status_frame, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Add version label to status bar
        version_label = ttk.Label(status_frame, text=f"v{self.VERSION}", relief=tk.SUNKEN, anchor=tk.E)
        version_label.pack(side=tk.RIGHT, padx=5)
        
        # Store misaligned components and components with local changes
        self.misaligned_components = []
        self.components_with_local_changes = []
        
        # Show a message to select a CMake file
        self.update_output("Welcome to the Repo Maintenance Tool!")
        self.update_output(f"Version: {self.VERSION}")
        self.update_output("Please select a CMake file using the Browse button.")
        self.update_status("Ready")
    
    def browse_cmake_file(self):
        """Open a file dialog to select a CMake file."""
        file_path = filedialog.askopenfilename(
            title="Select CMake File",
            filetypes=[("CMake Files", "*.cmake"), ("All Files", "*.*")]
        )
        if file_path:
            self.cmake_file_var.set(file_path)
            self.refresh_targets()
    
    # Removed browse_output_file method as we no longer save to file
    
    def refresh_targets(self):
        """Refresh the list of targets from the CMake file."""
        cmake_file = self.cmake_file_var.get()
        if not cmake_file:
            self.update_output("Please select a CMake file first.")
            return
        
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
                    # Set canfbl target to False by default, all others to True
                    default_value = False if target.lower() == 'canfbl' else True
                    self.target_vars[target] = tk.BooleanVar(value=default_value)
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
    
    def clear_results(self):
        """Clear all results from previous checks."""
        # Clear the output text
        self.output_text.config(state=tk.NORMAL)
        self.output_text.delete(1.0, tk.END)
        self.output_text.config(state=tk.DISABLED)
        
        # Clear the misaligned components treeview
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Clear the local changes treeview
        for item in self.local_changes_tree.get_children():
            self.local_changes_tree.delete(item)
        
        # Clear the component lists
        self.misaligned_components = []
        self.components_with_local_changes = []
        
        # Reset the progress bar
        self.progress_var.set(0)
        
        # Update status
        self.update_status("Ready")
    
    def run_check(self):
        """Run the component tag check."""
        cmake_file = self.cmake_file_var.get()
        selected_targets = [target for target, var in self.target_vars.items() if var.get()]
        verbose = self.verbose_var.get()
        
        if not os.path.exists(cmake_file):
            messagebox.showerror("Error", f"CMake file does not exist: {cmake_file}")
            return
        
        if not selected_targets and self.target_vars:
            messagebox.showinfo("Info", "Please select at least one target")
            return
        
        # Disable the run button and clear all previous results
        self.run_button.config(state=tk.DISABLED)
        self.clear_results()
        
        # Run the check in a separate thread
        thread = threading.Thread(target=self.run_check_thread, args=(cmake_file, selected_targets, verbose))
        thread.daemon = True
        thread.start()
    
    def run_check_thread(self, cmake_file, selected_targets, verbose):
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
                    is_aligned, actual_tag, expected_tag, error_message, path_exists = check_component_tag(component, cmake_file_dir)
                    
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
                            'resolved_path': resolve_path(path, cmake_file_dir),
                            'path_exists': path_exists
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
                        
                    # Check if this component has uncommitted changes in its own directory
                    if error_message and "Tag is correct but there are uncommitted changes" in error_message:
                        # Add to the components with local changes list
                        self.components_with_local_changes.append({
                            'target': target_name,
                            'module_name': module_name,
                            'path': path,
                            'change_location': resolve_path(path, cmake_file_dir),
                            'status': "Has uncommitted changes in component directory",
                            'change_type': 'self'  # Add change_type field
                        })
                        
                        # Add to the local changes treeview
                        self.local_changes_tree.insert("", "end", values=(
                            module_name,
                            target_name,
                            path,
                            resolve_path(path, cmake_file_dir),
                            "Has uncommitted changes in component directory"
                        ))
                        
            # After checking all components, check if we found any with local changes
            if self.components_with_local_changes:
                self_changes = sum(1 for c in self.components_with_local_changes if c.get('change_type') == 'self')
                if self_changes > 0:
                    self.update_output(f"\nFound {self_changes} components with uncommitted changes in their own directories.")
                    self.notebook.select(2)  # Switch to the Local Changes tab
                else:
                    self.update_output("\nNo components with local changes found.")
            else:
                self.update_output(f"All {total_components} components are aligned with their expected tags.")
            
            # Display report summary in the output tab
            self.update_output("\n=== Component Tag Alignment Report ===")
            self.update_output(f"CMake file: {cmake_file}")
            self.update_output(f"Total components checked: {total_components}")
            
            if self.misaligned_components:
                # Calculate percentage of misaligned components
                percentage = (len(self.misaligned_components) / total_components) * 100
                self.update_output(f"Misaligned components: {len(self.misaligned_components)} ({percentage:.2f}%)")
                
                self.update_output("\nDetails of misaligned components:")
                for component in self.misaligned_components:
                    self.update_output(f"- {component['module_name']} (target: {component['target']})")
                    self.update_output(f"  Path: {component['path']}")
                    self.update_output(f"  Expected tag: {component['expected_tag']}")
                    if component['actual_tag']:
                        self.update_output(f"  Actual tag: {component['actual_tag']}")
                    self.update_output(f"  Error: {component['error_message']}")
                    self.update_output("")  # Add an empty line between components
            else:
                self.update_output("All components are aligned with their expected tags.")
            
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
        """Select all items in the misaligned components treeview."""
        for item in self.tree.get_children():
            self.tree.selection_add(item)
    
    def deselect_all(self):
        """Deselect all items in the misaligned components treeview."""
        for item in self.tree.get_children():
            self.tree.selection_remove(item)
    
    def select_all_local_changes(self):
        """Select all items in the local changes treeview."""
        for item in self.local_changes_tree.get_children():
            self.local_changes_tree.selection_add(item)
    
    def deselect_all_local_changes(self):
        """Deselect all items in the local changes treeview."""
        for item in self.local_changes_tree.get_children():
            self.local_changes_tree.selection_remove(item)
    
    def revert_selected_changes(self):
        """Revert changes for selected components in the local changes tab."""
        selected_items = self.local_changes_tree.selection()
        if not selected_items:
            messagebox.showinfo("Info", "No components selected")
            return
        
        # Confirm revert
        if not messagebox.askyesno("Confirm Revert", "Are you sure you want to revert changes for the selected components? This will discard all uncommitted changes."):
            return
        
        # Get selected components
        selected_indices = [self.local_changes_tree.index(item) for item in selected_items]
        selected_components = [self.components_with_local_changes[i] for i in selected_indices]
        
        # Revert changes
        reverted_count = 0
        failed_count = 0
        
        for component in selected_components:
            try:
                change_location = component.get('change_location', '')
                
                if not change_location:
                    self.update_output(f"Error: No change location found for {component['module_name']}")
                    failed_count += 1
                    continue
                
                self.update_status(f"Reverting changes for {component['module_name']}...")
                
                # Save current directory
                original_dir = os.getcwd()
                
                # Change to the directory with changes
                os.chdir(change_location)
                
                # Check if it's a git repository
                is_git_repo = subprocess.run(['git', 'rev-parse', '--is-inside-work-tree'], 
                                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True).returncode == 0
                
                if is_git_repo:
                    # More thorough cleaning of the repository
                    
                    # 1. Reset any staged changes
                    subprocess.run(['git', 'reset', 'HEAD'], 
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    
                    # 2. Discard changes in tracked files
                    result = subprocess.run(['git', 'checkout', '--force', '.'], 
                                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    
                    if result.returncode != 0:
                        raise Exception(f"Git checkout failed: {result.stderr}")
                    
                    # 3. Handle untracked files
                    untracked_files = subprocess.run(['git', 'ls-files', '--others', '--exclude-standard'], 
                                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True).stdout.strip()
                    
                    if untracked_files:
                        # Ask if user wants to remove untracked files
                        if messagebox.askyesno("Untracked Files", 
                                             f"There are untracked files in {change_location}. Do you want to remove them?"):
                            # Clean untracked files and directories
                            clean_result = subprocess.run(['git', 'clean', '-fd'], 
                                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                            if clean_result.returncode == 0:
                                self.update_output(f"Removed untracked files in {change_location}")
                            else:
                                self.update_output(f"Warning: Failed to remove untracked files in {change_location}")
                        else:
                            self.update_output(f"Warning: Untracked files remain in {change_location}")
                else:
                    raise Exception("Not a git repository")
                
                # Change back to the original directory
                os.chdir(original_dir)
                
                self.update_output(f"Successfully reverted changes for {component['module_name']} in {change_location}")
                reverted_count += 1
                
            except Exception as e:
                failed_count += 1
                self.update_output(f"Error reverting changes for {component['module_name']}: {e}")
                
                # Try to change back to the original directory if we're not there
                try:
                    if os.getcwd() != original_dir:
                        os.chdir(original_dir)
                except:
                    pass
        
        # Show results
        if failed_count == 0:
            messagebox.showinfo("Revert Complete", f"Successfully reverted changes for {reverted_count} components")
        else:
            messagebox.showwarning("Revert Complete", f"Reverted changes for {reverted_count} components, {failed_count} failed")
        
        # Inform user that they need to run the check again to see updated results
        self.update_output("\nUpdate complete. Run check again to see updated results.")
        self.update_status("Ready")
    
    def update_selected_components(self):
        """Update selected components to their expected tags or clone if missing."""
        selected_items = self.tree.selection()
        if not selected_items:
            messagebox.showinfo("Info", "No components selected")
            return
        
        # Confirm update
        if not messagebox.askyesno("Confirm Update", "Are you sure you want to update the selected components? This will clone missing components and update existing ones to their expected tags."):
            return
        
        # Get selected components
        selected_indices = [self.tree.index(item) for item in selected_items]
        selected_components = [self.misaligned_components[i] for i in selected_indices]
        
        # Get base URL
        base_url = self.base_url_var.get()
        
        # Update components
        updated_count = 0
        cloned_count = 0
        failed_count = 0
        
        for component in selected_components:
            try:
                self.update_status(f"Processing {component['module_name']}...")
                
                # Check if the path exists
                path_exists = component.get('path_exists', os.path.exists(component['resolved_path']))
                
                if not path_exists:
                    # Clone the component
                    self.update_output(f"Cloning {component['module_name']} to {component['resolved_path']}...")
                    
                    try:
                        # Format the component name for the URL (lowercase and remove special characters)
                        repo_name = re.sub(r'[^a-zA-Z0-9._-]', '', component['module_name'].lower())
                        clone_url = f"{base_url}{repo_name}.git"
                        self.update_output(f"Using URL: {clone_url}")
                        
                        # Make sure the component has a tag (either in 'tag' or 'expected_tag' field)
                        tag = None
                        if 'tag' in component and component['tag']:
                            tag = component['tag']
                        elif 'expected_tag' in component and component['expected_tag']:
                            tag = component['expected_tag']
                            # Update the component with the tag for cloning
                            component['tag'] = tag
                        
                        if not tag:
                            self.update_output(f"Error: Component {component['module_name']} is missing a tag field")
                            failed_count += 1
                            continue
                        
                        self.update_output(f"Using tag: {tag}")
                        
                        success, message = clone_component(component, os.path.dirname(os.path.abspath(self.cmake_file_var.get())), base_url)
                    except Exception as e:
                        self.update_output(f"Error preparing to clone {component['module_name']}: {str(e)}")
                        failed_count += 1
                        continue
                    
                    if success:
                        self.update_output(f"Successfully cloned {component['module_name']}")
                        cloned_count += 1
                        continue
                    else:
                        self.update_output(f"Failed to clone {component['module_name']}: {message}")
                        failed_count += 1
                        continue
                
                # Change to the component directory
                original_dir = os.getcwd()
                os.chdir(component['resolved_path'])
                
                # Create a VERSION file with the expected tag
                with open('VERSION', 'w') as f:
                    f.write(component['expected_tag'])
                
                # Try to set git tag if it's a git repository
                try:
                    # Check if it's a git repository
                    is_git_repo = subprocess.run(['git', 'rev-parse', '--is-inside-work-tree'], 
                                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True).returncode == 0
                    
                    if is_git_repo:
                        # Check if there are uncommitted changes
                        uncommitted_changes = subprocess.run(['git', 'status', '--porcelain'], 
                                                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True).stdout.strip() != ""
                        
                        # Commit all changes, not just the VERSION file
                        # This ensures we don't leave uncommitted changes that would cause the component to still be misaligned
                        subprocess.run(['git', 'add', '.'], 
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        
                        subprocess.run(['git', 'commit', '-m', f"Update component to {component['expected_tag']}"], 
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        
                        # Delete existing tag if it exists (locally)
                        subprocess.run(['git', 'tag', '-d', component['expected_tag']], 
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        
                        # Create new tag with force flag
                        subprocess.run(['git', 'tag', '-f', component['expected_tag']], 
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        
                        # Verify the tag was created
                        tag_check = subprocess.run(['git', 'tag', '-l', component['expected_tag']], 
                                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                        
                        if component['expected_tag'] not in tag_check.stdout:
                            raise Exception(f"Failed to create tag {component['expected_tag']}")
                except Exception as e:
                    self.update_output(f"Warning: Git operation failed for {component['module_name']}: {e}")
                    # Continue anyway, we've already created the VERSION file
                
                # Change back to the original directory
                os.chdir(original_dir)
                
                updated_count += 1
            except Exception as e:
                failed_count += 1
                self.update_output(f"Error updating {component['module_name']}: {e}")
                
                # Try to change back to the original directory if we're not there
                try:
                    if os.getcwd() != original_dir:
                        os.chdir(original_dir)
                except:
                    pass
        
        # Show results
        result_message = ""
        if cloned_count > 0:
            result_message += f"Cloned {cloned_count} components. "
        if updated_count > 0:
            result_message += f"Updated {updated_count} components. "
        if failed_count > 0:
            result_message += f"{failed_count} operations failed."
        
        if failed_count == 0:
            messagebox.showinfo("Operation Complete", result_message.strip())
        else:
            messagebox.showwarning("Operation Complete", result_message.strip())
        
        # Inform user that they need to run the check again to see updated results
        self.update_output("\nUpdate complete. Run check again to see updated results.")
        self.update_status("Ready")

def main():
    """Main function."""
    root = tk.Tk()
    app = ComponentTagCheckerGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()

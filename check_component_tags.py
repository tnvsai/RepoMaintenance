#!/usr/bin/env python3
"""
Build script to check if components in a CMake file have aligned tags.

This script takes a CMake file as input, extracts components with tags,
and checks if each component's path is aligned with the tag mentioned in the CMake file.
"""

import os
import re
import sys
import subprocess
import argparse
from pathlib import Path
import time

def parse_cmake_file(cmake_file_path):
    """
    Parse the CMake file and extract components with their paths and tags.
    
    Args:
        cmake_file_path (str): Path to the CMake file
        
    Returns:
        dict: Dictionary of components with their paths and tags
    """
    with open(cmake_file_path, 'r') as f:
        cmake_content = f.read()
    
    # Extract all MODULES_* sections
    modules_sections = {}
    
    # Find all set(MODULES_target ...) sections
    pattern = r'set\(MODULES_(\w+)\s+(.*?)\s*\)'
    matches = re.findall(pattern, cmake_content, re.DOTALL)
    
    for target, modules_content in matches:
        # Extract components from each section
        components = []
        
        # Skip if the content starts with a variable reference like "${MODULES_app}"
        if modules_content.strip().startswith('"${MODULES_'):
            continue
            
        # Split the content by lines and process each line
        lines = modules_content.strip().split('\n')
        current_component = []
        
        for line in lines:
            # Skip commented lines and empty lines
            if line.strip().startswith('#') or not line.strip():
                continue
            
            # Skip lines with variable references like "${MODULES_app}"
            if '"${MODULES_' in line:
                continue
                
            # Extract quoted strings from the line
            quoted_strings = re.findall(r'"([^"]*)"', line)
            
            # Add the quoted strings to the current component
            current_component.extend(quoted_strings)
            
            # If we have 4 elements, we have a complete component
            if len(current_component) >= 4:
                # Extract the component details
                module_name = current_component[0]
                project_key = current_component[1]
                path = current_component[2]
                tag = current_component[3]
                
                # Add the component to the list
                components.append({
                    'module_name': module_name,
                    'project_key': project_key,
                    'path': path,
                    'tag': tag
                })
                
                # Reset the current component
                current_component = []
        
        # Add the components to the modules_sections dictionary
        if components:  # Only add if there are actual components
            modules_sections[target] = components
    
    # Also check for additional components added later in the file
    # For example: set(MODULES_app "${MODULES_app}" "SHARED_C.SV.0034.00_SVRESOURCEM_S32K" "CASCO" "${CMAKE_CURRENT_LIST_DIR}/app/services/shared/SvResourceM" "V_02_00_10")
    pattern = r'set\(MODULES_(\w+)\s+"\$\{MODULES_\w+\}"\s+"([^"]*)"\s+"([^"]*)"\s+"([^"]*)"\s+"([^"]*)"\)'
    matches = re.findall(pattern, cmake_content)
    
    for target, module_name, project_key, path, tag in matches:
        if target in modules_sections:
            modules_sections[target].append({
                'module_name': module_name,
                'project_key': project_key,
                'path': path,
                'tag': tag
            })
        else:
            modules_sections[target] = [{
                'module_name': module_name,
                'project_key': project_key,
                'path': path,
                'tag': tag
            }]
    
    return modules_sections

def resolve_path(path, cmake_file_dir):
    """
    Resolve the path relative to the CMake file directory.
    
    Args:
        path (str): Path to resolve
        cmake_file_dir (str): Directory of the CMake file
        
    Returns:
        str: Resolved path
    """
    # Replace ${CMAKE_CURRENT_LIST_DIR} with the actual directory
    path = path.replace('${CMAKE_CURRENT_LIST_DIR}', cmake_file_dir)
    
    # Replace other variables if needed
    # For example, ${PROJ_ROOT}, ${PLATFORM}, ${PROJECT}, etc.
    # This would require parsing the CMake file for these variables
    
    return path

def check_tag_reuse(repo_path, tag_name):
    """
    Check if a tag has been reused using a single git command.
    This is much faster than running multiple git commands.
    
    Args:
        repo_path (str): Path to the git repository
        tag_name (str): Name of the tag to check
        
    Returns:
        tuple: (is_integrity_ok, error_message)
    """
    try:
        # This single command gets both the tag object type and the commit it points to
        result = subprocess.run(
            ['git', '-C', repo_path, 'cat-file', '-p', tag_name],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=1
        )
        
        if result.returncode != 0:
            return False, f"Failed to inspect tag: {result.stderr}"
            
        # For annotated tags, the output includes the tagger info with date
        # For lightweight tags, we just get the commit object
        output = result.stdout
        
        # Check if this is an annotated tag (which includes creation date)
        if 'tagger ' in output:
            # Extract the tagger date and the commit hash
            tagger_line = re.search(r'tagger .+? (\d+) [+-]\d+', output)
            object_line = re.search(r'object ([0-9a-f]+)', output)
            
            if tagger_line and object_line:
                tag_date = int(tagger_line.group(1))
                commit_hash = object_line.group(1)
                
                # Get the commit date with a single command
                commit_date_result = subprocess.run(
                    ['git', '-C', repo_path, 'show', '-s', '--format=%at', commit_hash],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=1
                )
                
                if commit_date_result.returncode == 0:
                    commit_date = int(commit_date_result.stdout.strip())
                    
                    # If tag date is earlier than commit date, the tag was likely moved
                    if tag_date < commit_date:
                        return False, f"Tag {tag_name} appears to have been reused (created before its commit)"
        
        # For lightweight tags or if we couldn't parse dates, fall back to a simpler check
        # Check if VERSION file content matches the tag name
        version_check = subprocess.run(
            ['git', '-C', repo_path, 'show', f'{tag_name}:VERSION'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=1
        )
        
        if version_check.returncode == 0 and version_check.stdout.strip() != tag_name:
            return False, f"VERSION file content doesn't match tag name"
            
        return True, None
    except subprocess.TimeoutExpired:
        return False, "Git command timed out"
    except Exception as e:
        return False, f"Error checking tag: {e}"

def check_component_tag(component, cmake_file_dir):
    """
    Check if the component's path is aligned with the tag mentioned in the CMake file.
    Also checks if there are commits after the tag in git repositories.
    
    Args:
        component (dict): Component details
        cmake_file_dir (str): Directory of the CMake file
        
    Returns:
        tuple: (is_aligned, actual_tag, expected_tag, error_message, path_exists)
    """
    module_name = component['module_name']
    path = component['path']
    expected_tag = component['tag']
    
    # Resolve the path
    resolved_path = resolve_path(path, cmake_file_dir)
    
    # Check if the path exists
    path_exists = os.path.exists(resolved_path)
    if not path_exists:
        return False, None, expected_tag, f"Path does not exist: {resolved_path}", False
    
    # Try to determine the actual tag
    # This could be done by checking a version file, git tag, etc.
    
    # Method 1: Check if it's a git repository and get the tag
    try:
        # Change to the component directory
        original_dir = os.getcwd()
        os.chdir(resolved_path)
        
        # Check if it's a git repository
        is_git_repo = subprocess.run(['git', 'rev-parse', '--is-inside-work-tree'], 
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True).returncode == 0
        
        if is_git_repo:
            # Get the current git tag
            tag_result = subprocess.run(['git', 'describe', '--tags', '--exact-match'], 
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            
            if tag_result.returncode == 0:
                actual_tag = tag_result.stdout.strip()
                
                # Check if there are commits after the tag
                # Get the commit hash that the tag points to
                tag_commit = subprocess.run(['git', 'rev-list', '-n', '1', actual_tag], 
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True).stdout.strip()
                
                # Get the commit hash of HEAD
                head_commit = subprocess.run(['git', 'rev-parse', 'HEAD'], 
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True).stdout.strip()
                
                # Check if there are uncommitted changes
                uncommitted_changes = subprocess.run(['git', 'status', '--porcelain'], 
                                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True).stdout.strip() != ""
                
                # Change back to the original directory
                os.chdir(original_dir)
                
                if actual_tag != expected_tag:
                    return False, actual_tag, expected_tag, f"Tag mismatch: expected {expected_tag}, got {actual_tag}", True
                
                # Check if the tag has been reused
                integrity_ok, integrity_error = check_tag_reuse(resolved_path, actual_tag)
                if not integrity_ok:
                    return False, actual_tag, expected_tag, integrity_error, True
                
                if tag_commit != head_commit:
                    # Count commits between tag and HEAD
                    commit_count_result = subprocess.run(['git', '-C', resolved_path, 'rev-list', '--count', f"{actual_tag}..HEAD"], 
                                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    commit_count = commit_count_result.stdout.strip() if commit_count_result.returncode == 0 else "unknown number of"
                    
                    return False, actual_tag, expected_tag, f"Tag is correct but there are {commit_count} commits after the tag", True
                
                if uncommitted_changes:
                    return False, actual_tag, expected_tag, f"Tag is correct but there are uncommitted changes", True
                
                return True, actual_tag, expected_tag, None, True
        
        # Change back to the original directory if we didn't return yet
        os.chdir(original_dir)
        
    except Exception as e:
        # Change back to the original directory in case of an error
        try:
            os.chdir(original_dir)
        except:
            pass
    
    # Method 2: Check if there's a VERSION file
    version_file = os.path.join(resolved_path, 'VERSION')
    if os.path.exists(version_file):
        with open(version_file, 'r') as f:
            actual_tag = f.read().strip()
            if actual_tag == expected_tag:
                # For VERSION file, we can't check if tag was reused
                # But we can check if the VERSION file was modified after creation
                # by comparing file modification time with current time
                try:
                    file_mtime = os.path.getmtime(version_file)
                    current_time = time.time()
                    # If file was modified in the last hour, it might be suspicious
                    if current_time - file_mtime < 3600:  # 1 hour in seconds
                        return False, actual_tag, expected_tag, "VERSION file was recently modified, possible tag reuse", True
                except Exception:
                    pass
                return True, actual_tag, expected_tag, None, True
            else:
                return False, actual_tag, expected_tag, f"Tag mismatch: expected {expected_tag}, got {actual_tag}", True
    
    # Method 3: Check if there's a manifest file or similar
    manifest_file = os.path.join(resolved_path, 'manifest.json')
    if os.path.exists(manifest_file):
        try:
            import json
            with open(manifest_file, 'r') as f:
                manifest = json.load(f)
                if 'version' in manifest:
                    actual_tag = manifest['version']
                    if actual_tag == expected_tag:
                        return True, actual_tag, expected_tag, None, True
                    else:
                        return False, actual_tag, expected_tag, f"Tag mismatch: expected {expected_tag}, got {actual_tag}", True
        except Exception as e:
            pass
    
    # If we couldn't determine the actual tag, return an error
    error_message = f"Could not determine the actual tag for {module_name} at {resolved_path}"
    
    
    return False, None, expected_tag, error_message, True

# Keep the existing function as is
def clone_component(component, cmake_file_dir, base_url="https://bitbucket.harman.com/scm/casco/"):
    """
    Clone a component repository if it doesn't exist.
    
    Args:
        component (dict): Component details
        cmake_file_dir (str): Directory of the CMake file
        base_url (str): Base URL for the git repository
        
    Returns:
        tuple: (success, message)
    """
    module_name = component['module_name']
    path = component['path']
    expected_tag = component['tag']
    
    # Resolve the path
    resolved_path = resolve_path(path, cmake_file_dir)
    
    # Create parent directory if it doesn't exist
    parent_dir = os.path.dirname(resolved_path)
    if not os.path.exists(parent_dir):
        try:
            os.makedirs(parent_dir)
        except Exception as e:
            return False, f"Failed to create directory {parent_dir}: {e}"
    
    # Format the component name for the URL (lowercase)
    # Remove any special characters and convert to lowercase
    repo_name = re.sub(r'[^a-zA-Z0-9._-]', '', module_name.lower())
    clone_url = f"{base_url}{repo_name}.git"
    
    print(f"Attempting to clone from URL: {clone_url}")
    print(f"To path: {resolved_path}")
    
    try:
        # Clone the repository
        result = subprocess.run(
            ['git', 'clone', clone_url, resolved_path],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        
        if result.returncode != 0:
            error_msg = result.stderr.strip() if result.stderr else "Unknown error"
            return False, f"Failed to clone repository: {error_msg}"
        
        # Change to the cloned directory
        original_dir = os.getcwd()
        os.chdir(resolved_path)
        
        # Checkout the specific tag
        tag_result = subprocess.run(
            ['git', 'checkout', expected_tag],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        
        # Change back to the original directory
        os.chdir(original_dir)
        
        if tag_result.returncode != 0:
            return False, f"Failed to checkout tag {expected_tag}: {tag_result.stderr}"
        
        return True, f"Successfully cloned {module_name} at tag {expected_tag}"
    except Exception as e:
        # Change back to the original directory in case of an error
        try:
            if 'original_dir' in locals():
                os.chdir(original_dir)
        except:
            pass
        return False, f"Error cloning component: {e}"

def check_parent_directories_for_changes(path):
    """
    Check parent directories for local changes in git repositories.
    
    Args:
        path (str): Path to start checking from
        
    Returns:
        str: Path of the parent directory with local changes, or None if no changes found
    """
    # Existing implementation here...
    # Get the absolute path
    abs_path = os.path.abspath(path)
    
    # Check each parent directory
    current_path = abs_path
    while True:
        parent_path = os.path.dirname(current_path)
        
        # Stop if we've reached the root directory
        if parent_path == current_path:
            break
        
        # Check if this directory is a git repository
        try:
            # Check if it's a git repository
            is_git_repo = subprocess.run(['git', '-C', parent_path, 'rev-parse', '--is-inside-work-tree'], 
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True).returncode == 0
            
            if is_git_repo:
                # Check if there are uncommitted changes
                uncommitted_changes = subprocess.run(['git', '-C', parent_path, 'status', '--porcelain'], 
                                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True).stdout.strip() != ""
                
                if uncommitted_changes:
                    return parent_path
        except Exception:
            # Ignore errors and continue checking parent directories
            pass
        
        # Move up to the parent directory
        current_path = parent_path
    
    # No parent directory with local changes found
    return None

def main():
    """
    Main function to check component tags.
    """
    parser = argparse.ArgumentParser(description='Check if components in a CMake file have aligned tags.')
    parser.add_argument('cmake_file', help='Path to the CMake file')
    parser.add_argument('--target', help='Specific target to check (e.g., app, fbl, canfbl, url)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose output')
    parser.add_argument('--output', '-o', help='Output file for the report')
    args = parser.parse_args()
    
    cmake_file_path = args.cmake_file
    
    # Check if the CMake file exists
    if not os.path.exists(cmake_file_path):
        print(f"Error: CMake file does not exist: {cmake_file_path}")
        sys.exit(1)
    
    # Get the directory of the CMake file
    cmake_file_dir = os.path.dirname(os.path.abspath(cmake_file_path))
    
    # Parse the CMake file
    print(f"Parsing CMake file: {cmake_file_path}")
    modules_sections = parse_cmake_file(cmake_file_path)
    
    # Check each component
    misaligned_components = []
    total_components = 0
    
    # Filter targets if specified
    if args.target:
        if args.target in modules_sections:
            targets_to_check = {args.target: modules_sections[args.target]}
        else:
            print(f"Error: Target '{args.target}' not found in the CMake file.")
            print(f"Available targets: {', '.join(modules_sections.keys())}")
            sys.exit(1)
    else:
        targets_to_check = modules_sections
    
    for target, components in targets_to_check.items():
        print(f"\nChecking components for target: {target}")
        print(f"Found {len(components)} components")
        total_components += len(components)
        
        for component in components:
            module_name = component['module_name']
            path = component['path']
            expected_tag = component['tag']
            
            if args.verbose:
                print(f"\nChecking component: {module_name}")
                print(f"  Path: {path}")
                print(f"  Expected tag: {expected_tag}")
            else:
                print(f"\nChecking component: {module_name}...", end="", flush=True)
            
            is_aligned, actual_tag, expected_tag, error_message, path_exists = check_component_tag(component, cmake_file_dir)
            
            if is_aligned:
                if args.verbose:
                    print(f"  Status: ALIGNED (tag: {actual_tag})")
                else:
                    print(" ALIGNED")
            else:
                if args.verbose:
                    print(f"  Status: NOT ALIGNED")
                    if actual_tag:
                        print(f"  Actual tag: {actual_tag}")
                    if error_message:
                        print(f"  Error: {error_message}")
                else:
                    print(" NOT ALIGNED")
                    print(f"  Error: {error_message}")
                
                misaligned_components.append({
                    'target': target,
                    'module_name': module_name,
                    'path': path,
                    'expected_tag': expected_tag,
                    'actual_tag': actual_tag,
                    'error_message': error_message,
                    'path_exists': path_exists
                })
    
    # Print summary
    print("\n=== Summary ===")
    if misaligned_components:
        print(f"Found {len(misaligned_components)} misaligned components out of {total_components} total components:")
        for component in misaligned_components:
            print(f"- {component['module_name']} (target: {component['target']})")
            print(f"  Expected tag: {component['expected_tag']}")
            if component['actual_tag']:
                print(f"  Actual tag: {component['actual_tag']}")
            print(f"  Error: {component['error_message']}")
            
        # Calculate percentage of misaligned components
        percentage = (len(misaligned_components) / total_components) * 100
        print(f"\nPercentage of misaligned components: {percentage:.2f}%")
    else:
        print(f"All {total_components} components are aligned with their expected tags.")
    
    # Write report to file if specified
    if args.output:
        try:
            with open(args.output, 'w') as f:
                f.write("=== Component Tag Alignment Report ===\n\n")
                f.write(f"CMake file: {cmake_file_path}\n")
                f.write(f"Total components checked: {total_components}\n")
                
                if misaligned_components:
                    f.write(f"Misaligned components: {len(misaligned_components)} ({percentage:.2f}%)\n\n")
                    
                    
                    f.write("Details of misaligned components:\n")
                    for component in misaligned_components:
                        f.write(f"- {component['module_name']} (target: {component['target']})\n")
                        f.write(f"  Path: {component['path']}\n")
                        f.write(f"  Expected tag: {component['expected_tag']}\n")
                        if component['actual_tag']:
                            f.write(f"  Actual tag: {component['actual_tag']}\n")
                        f.write(f"  Error: {component['error_message']}\n\n")
                else:
                    f.write("All components are aligned with their expected tags.\n")
                    
            print(f"\nReport written to {args.output}")
        except Exception as e:
            print(f"Error writing report to {args.output}: {e}")

if __name__ == "__main__":
    main()

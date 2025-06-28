import os
import zipfile
import tempfile
import logging
from pathlib import Path

class FileHandler:
    def __init__(self):
        self.code_extensions = {
            'android_java': ['.java', '.xml'],
            'android_kotlin': ['.kt', '.xml'],
            'ios_swift': ['.swift', '.storyboard', '.xib']
        }
        
        # Files and folders to skip during extraction
        self.skip_patterns = [
            # Version control and IDE
            '.git/', '.idea/', '.vscode/', '__pycache__/',
            # Build and cache folders
            '.gradle/', 'build/', 'bin/', 'obj/', 'target/',
            # System files
            '.DS_Store', 'Thumbs.db', '.gitignore', '.gitattributes',
            # Android specific
            'gradle/', 'gradlew', 'gradlew.bat', 'local.properties',
            # iOS specific
            'Pods/', 'DerivedData/', '.xcworkspace/', '.xcodeproj/',
            # Images and media
            '.png', '.jpg', '.jpeg', '.gif', '.ico', '.svg', '.webp',
            '.mp3', '.mp4', '.avi', '.mov', '.wav',
            # Configuration files (that don't need conversion)
            'proguard-rules.pro', '.pro', '.properties',
            # Documentation
            '.md', '.txt', '.pdf', '.docx',
            # Archive files
            '.zip', '.tar', '.gz', '.rar'
        ]
        
        # Files to copy without conversion (preserve in output)
        self.preserve_files = [
            '.png', '.jpg', '.jpeg', '.gif', '.ico', '.svg', '.webp',
            '.mp3', '.mp4', '.avi', '.mov', '.wav',
            'androidmanifest.xml', 'info.plist'
        ]
    
    def extract_code_files(self, zip_path, platform):
        """Extract code files from ZIP based on platform with robust error handling"""
        extracted_files = []
        valid_extensions = self.code_extensions.get(platform, [])
        skipped_files = []
        error_files = []
        
        if not valid_extensions:
            raise ValueError(f"Unsupported platform: {platform}")
        
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # Get list of all files in the ZIP
                file_list = zip_ref.namelist()
                logging.info(f"ZIP contains {len(file_list)} total entries")
                
                for file_path in file_list:
                    try:
                        # Skip directories
                        if file_path.endswith('/'):
                            continue
                        
                        # Skip files matching skip patterns
                        if self._should_skip_file(file_path):
                            skipped_files.append(file_path)
                            continue
                        
                        # Check if file has valid extension
                        file_ext = Path(file_path).suffix.lower()
                        if file_ext in valid_extensions:
                            # Extract to temporary location
                            temp_dir = tempfile.mkdtemp()
                            
                            try:
                                extracted_path = zip_ref.extract(file_path, temp_dir)
                                
                                # Verify the file was extracted and is readable
                                if os.path.exists(extracted_path) and os.path.getsize(extracted_path) > 0:
                                    # Try to read the file to ensure it's valid text
                                    with open(extracted_path, 'r', encoding='utf-8', errors='ignore') as test_file:
                                        content = test_file.read(100)  # Read first 100 chars as test
                                    
                                    # Store both the extracted path and relative path
                                    extracted_files.append((extracted_path, file_path))
                                    logging.info(f"Successfully extracted {file_path}")
                                else:
                                    error_files.append(f"{file_path} (empty or corrupted)")
                                    
                            except Exception as extract_error:
                                logging.warning(f"Failed to extract {file_path}: {extract_error}")
                                error_files.append(f"{file_path} (extraction failed)")
                                
                    except Exception as file_error:
                        logging.warning(f"Error processing {file_path}: {file_error}")
                        error_files.append(f"{file_path} (processing error)")
                        continue
        
        except zipfile.BadZipFile:
            raise ValueError("Invalid ZIP file")
        except Exception as e:
            logging.error(f"Error extracting ZIP file: {e}")
            raise Exception(f"Failed to extract ZIP file: {str(e)}")
        
        # Log summary
        logging.info(f"Extraction summary: {len(extracted_files)} files extracted, {len(skipped_files)} skipped, {len(error_files)} errors")
        
        if error_files:
            logging.warning(f"Files with errors: {error_files}")
        
        return extracted_files, skipped_files, error_files
    
    def extract_project_files(self, zip_path, platform):
        """Extract both code files and preserve files from a project ZIP"""
        code_files, skipped_files, error_files = self.extract_code_files(zip_path, platform)
        preserve_files = self._extract_preserve_files(zip_path)
        
        return code_files, preserve_files, skipped_files, error_files
    
    def _extract_preserve_files(self, zip_path):
        """Extract files that should be preserved (like images, manifests) without conversion"""
        preserve_files = []
        
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                file_list = zip_ref.namelist()
                
                for file_path in file_list:
                    if file_path.endswith('/'):
                        continue
                    
                    file_path_lower = file_path.lower()
                    file_name = os.path.basename(file_path_lower)
                    
                    # Check if this file should be preserved
                    should_preserve = False
                    for preserve_pattern in self.preserve_files:
                        if (file_path_lower.endswith(preserve_pattern) or 
                            preserve_pattern in file_name):
                            should_preserve = True
                            break
                    
                    if should_preserve and not self._should_skip_file(file_path):
                        try:
                            temp_dir = tempfile.mkdtemp()
                            extracted_path = zip_ref.extract(file_path, temp_dir)
                            preserve_files.append((extracted_path, file_path))
                            logging.info(f"Preserved asset: {file_path}")
                        except Exception as e:
                            logging.warning(f"Failed to preserve {file_path}: {e}")
                            
        except Exception as e:
            logging.error(f"Error extracting preserve files: {e}")
        
        return preserve_files
    
    def _should_skip_file(self, file_path):
        """Check if a file should be skipped during extraction"""
        file_path_lower = file_path.lower()
        file_name = os.path.basename(file_path_lower)
        
        # Check for exact filename matches
        if file_name in ['gradlew', 'gradlew.bat', 'local.properties', '.ds_store', 'thumbs.db']:
            return True
        
        # Check for folder patterns
        for pattern in self.skip_patterns:
            if pattern.endswith('/'):
                # Folder pattern - check if any part of path contains this folder
                if f'/{pattern[:-1]}/' in f'/{file_path_lower}/' or file_path_lower.startswith(pattern[:-1] + '/'):
                    return True
            else:
                # File extension or name pattern
                if file_path_lower.endswith(pattern) or pattern in file_path_lower:
                    return True
        
        # Skip files that are too deep in folder structure (likely build artifacts)
        path_depth = file_path.count('/')
        if path_depth > 6:  # Allow reasonable project structure depth
            return True
        
        # Skip files with suspicious patterns
        suspicious_patterns = ['generated', 'cache', 'temp', 'tmp', '.class', '.dex', '.o']
        if any(pattern in file_path_lower for pattern in suspicious_patterns):
            return True
        
        return False
    
    def create_zip(self, converted_files, output_path, preserve_files=None):
        """Create a ZIP file from converted code files and preserved assets"""
        try:
            with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zip_ref:
                # Add converted code files
                for filename, content in converted_files:
                    zip_ref.writestr(filename, content)
                    logging.info(f"Added converted file {filename} to output ZIP")
                
                # Add preserved files (images, manifests, etc.)
                if preserve_files:
                    for file_path, relative_path in preserve_files:
                        try:
                            zip_ref.write(file_path, relative_path)
                            logging.info(f"Added preserved asset {relative_path} to output ZIP")
                        except Exception as e:
                            logging.warning(f"Failed to add preserved file {relative_path}: {e}")
            
            logging.info(f"Created output ZIP: {output_path}")
            
        except Exception as e:
            logging.error(f"Error creating ZIP file: {e}")
            raise Exception(f"Failed to create output ZIP: {str(e)}")
    
    def validate_zip_file(self, zip_path):
        """Validate if the uploaded file is a valid ZIP"""
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # Try to read the file list
                zip_ref.namelist()
                return True
        except zipfile.BadZipFile:
            return False
        except Exception:
            return False
    
    def get_file_count(self, zip_path, platform):
        """Get count of valid code files in ZIP for a platform"""
        valid_extensions = self.code_extensions.get(platform, [])
        count = 0
        
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                for file_path in zip_ref.namelist():
                    if not file_path.endswith('/'):
                        file_ext = Path(file_path).suffix.lower()
                        if file_ext in valid_extensions:
                            count += 1
        except Exception:
            pass
        
        return count
    
    def validate_file_platform(self, filename, platform):
        """Validate that a file extension matches the expected platform"""
        valid_extensions = self.code_extensions.get(platform, [])
        file_ext = Path(filename).suffix.lower()
        return file_ext in valid_extensions

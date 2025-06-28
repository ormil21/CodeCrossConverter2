import os
import logging
from flask import Flask, render_template, request, flash, redirect, url_for, send_file, jsonify, session
from werkzeug.utils import secure_filename
from werkzeug.middleware.proxy_fix import ProxyFix
import tempfile
import shutil
from code_converter import CodeConverter
from file_handler import FileHandler

# Set up logging
logging.basicConfig(level=logging.DEBUG)

# Create the Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Configuration
UPLOAD_FOLDER = 'uploads'
CONVERTED_FOLDER = 'converted'
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
ALLOWED_EXTENSIONS = {'zip', 'java', 'kt', 'swift', 'xml'}

# Ensure upload directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(CONVERTED_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['CONVERTED_FOLDER'] = CONVERTED_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

# Initialize services
code_converter = CodeConverter()
file_handler = FileHandler()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/convert', methods=['POST'])
def convert_code():
    try:
        # Check if files were uploaded
        uploaded_files = request.files.getlist('code_file')
        source_platform = request.form.get('source_platform')
        target_platform = request.form.get('target_platform')
        conversion_type = request.form.get('conversion_type', 'full_project')
        
        # Validate inputs
        if not uploaded_files or all(f.filename == '' for f in uploaded_files):
            flash('No files selected', 'error')
            return redirect(url_for('index'))
        
        if not source_platform or not target_platform:
            flash('Please select both source and target platforms', 'error')
            return redirect(url_for('index'))
        
        if source_platform == target_platform:
            flash('Source and target platforms must be different', 'error')
            return redirect(url_for('index'))
        
        # Filter and validate uploaded files
        valid_files = []
        for upload_file in uploaded_files:
            if upload_file.filename and allowed_file(upload_file.filename):
                valid_files.append(upload_file)
        
        if not valid_files:
            flash('No valid files found. Only ZIP, Java, Kotlin, Swift, and XML files are allowed', 'error')
            return redirect(url_for('index'))
        
        # Process files (can be multiple individual files or a single ZIP)
        all_extracted_files = []
        preserve_files = []
        is_zip_file = False
        filename = "conversion"  # Default filename for output
        upload_path = ""  # Initialize to prevent unbound errors
        
        for upload_file in valid_files:
            filename = secure_filename(upload_file.filename)
            if not filename:
                continue
                
            upload_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            upload_file.save(upload_path)
            
            if filename.lower().endswith('.zip'):
                is_zip_file = True
                logging.info(f"Processing ZIP file: {filename}")
                
                # Extract from ZIP
                extraction_result = file_handler.extract_project_files(upload_path, source_platform)
                
                if len(extraction_result) == 4:
                    extracted_files, zip_preserve_files, skipped_files, error_files = extraction_result
                    all_extracted_files.extend(extracted_files)
                    preserve_files.extend(zip_preserve_files)
                else:
                    # Fallback to basic extraction
                    basic_result = file_handler.extract_code_files(upload_path, source_platform)
                    if len(basic_result) == 3:
                        extracted_files, skipped_files, error_files = basic_result
                        all_extracted_files.extend(extracted_files)
                    else:
                        all_extracted_files.extend(basic_result)
            else:
                # Individual code file
                logging.info(f"Processing individual file: {filename}")
                all_extracted_files.append((upload_path, filename))
        
        # Apply conversion type filtering
        if conversion_type != 'full_project':
            filtered_files = []
            for file_path, relative_path in all_extracted_files:
                file_ext = relative_path.lower().split('.')[-1]
                
                if conversion_type == 'logic_only':
                    # Only include logic files (.java, .kt, .swift)
                    if file_ext in ['java', 'kt', 'swift']:
                        filtered_files.append((file_path, relative_path))
                elif conversion_type == 'layouts_only':
                    # Only include layout files (.xml and similar UI files)
                    if file_ext in ['xml'] or 'layout' in relative_path.lower():
                        filtered_files.append((file_path, relative_path))
            
            all_extracted_files = filtered_files
            logging.info(f"Filtered to {len(all_extracted_files)} files for {conversion_type} conversion")
        
        extracted_files = all_extracted_files  # Keep compatibility with existing code
        
        if is_zip_file:
            # Extract code files from ZIP
            logging.info(f"Extracting files from {upload_path}")
            try:
                # Use enhanced project file extraction for full project ZIPs
                extraction_result = file_handler.extract_project_files(upload_path, source_platform)
                
                if len(extraction_result) == 4:
                    extracted_files, preserve_files, skipped_files, error_files = extraction_result
                else:
                    # Fallback to basic extraction
                    basic_result = file_handler.extract_code_files(upload_path, source_platform)
                    if len(basic_result) == 3:
                        extracted_files, skipped_files, error_files = basic_result
                        preserve_files = []
                    else:
                        extracted_files = basic_result
                        preserve_files = []
                        skipped_files = []
                        error_files = []
                
                if not extracted_files:
                    error_msg = f'No {source_platform} code files found in the uploaded ZIP.'
                    if error_files:
                        error_msg += f' {len(error_files)} files had errors: {", ".join(error_files[:3])}'
                        if len(error_files) > 3:
                            error_msg += f' and {len(error_files) - 3} more.'
                    if skipped_files:
                        error_msg += f' {len(skipped_files)} files were skipped (build files, IDE files, etc.)'
                    
                    flash(error_msg, 'error')
                    return redirect(url_for('index'))
                
                # Log extraction summary
                if skipped_files or error_files:
                    logging.info(f"ZIP extraction: {len(extracted_files)} files extracted, {len(skipped_files)} skipped, {len(error_files)} errors")
                
                # Convert code files with enhanced error handling
                logging.info(f"Converting {len(extracted_files)} files from {source_platform} to {target_platform}")
                try:
                    converted_files = code_converter.convert_files(extracted_files, source_platform, target_platform)
                except Exception as conversion_error:
                    logging.error(f"Code conversion failed: {conversion_error}")
                    
                    # If conversion completely fails, create fallback files
                    converted_files = []
                    for file_path, relative_path in extracted_files:
                        try:
                            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                source_code = f.read()
                            
                            # Create fallback conversion
                            fallback_comment = f"// CONVERSION FAILED: {str(conversion_error)[:100]}...\n// Original {source_platform} file preserved below\n\n"
                            fallback_content = fallback_comment + source_code
                            
                            # Keep original filename for fallback
                            converted_files.append((relative_path, fallback_content))
                            
                        except Exception as file_error:
                            logging.warning(f"Failed to create fallback for {relative_path}: {file_error}")
                    
                    if not converted_files:
                        flash('Code conversion failed due to service issues. Please try again later.', 'error')
                        return redirect(url_for('index'))
                
            except Exception as extract_error:
                logging.error(f"ZIP extraction failed: {extract_error}")
                flash(f'Failed to extract ZIP file: {str(extract_error)}', 'error')
                return redirect(url_for('index'))
        else:
            # Process single code file
            logging.info(f"Processing individual file: {filename}")
            
            # Validate that the file extension matches the source platform
            if not file_handler.validate_file_platform(filename, source_platform):
                flash(f'File extension does not match source platform {source_platform}', 'error')
                return redirect(url_for('index'))
            
            # Read the file content
            with open(upload_path, 'r', encoding='utf-8', errors='ignore') as f:
                source_code = f.read()
            
            # Convert the single file
            logging.info(f"Converting single file from {source_platform} to {target_platform}")
            converted_code = code_converter._convert_single_file(
                source_code, source_platform, target_platform, filename
            )
            
            # Generate new filename for converted code
            new_filename = code_converter._get_converted_filename(filename, source_platform, target_platform)
            converted_files = [(new_filename, converted_code)]
        
        # Handle output based on file count
        if len(converted_files) == 1 and not is_zip_file:
            # Single file conversion - save as plain text file
            converted_filename, converted_content = converted_files[0]
            output_filename = converted_filename
            output_path = os.path.join(app.config['CONVERTED_FOLDER'], output_filename)
            
            # Write as plain text file
            with open(output_path, 'w', encoding='utf-8') as f:
                if converted_content:
                    f.write(converted_content)
                else:
                    f.write("// Conversion failed - empty content")
            
            is_single_file = True
        else:
            # Multiple files or ZIP input - create ZIP output
            output_filename = f"converted_{source_platform}_to_{target_platform}_{filename}"
            output_path = os.path.join(app.config['CONVERTED_FOLDER'], output_filename)
            
            # Include preserve files if they exist
            preserve_files_to_add = locals().get('preserve_files', [])
            file_handler.create_zip(converted_files, output_path, preserve_files_to_add)
            is_single_file = False
        
        # Clean up temporary files
        try:
            os.remove(upload_path)
            if is_zip_file:
                for file_path, _ in extracted_files:
                    if os.path.exists(file_path):
                        os.remove(file_path)
        except Exception as e:
            logging.warning(f"Failed to clean up temporary files: {e}")
        
        # Store conversion result in session for preview
        session['conversion_result'] = {
            'files': converted_files,
            'output_path': output_path,
            'output_filename': output_filename,
            'source_platform': source_platform,
            'target_platform': target_platform,
            'is_single_file': is_single_file
        }
        
        flash(f'Successfully converted {len(converted_files)} files!', 'success')
        return redirect(url_for('preview_conversion'))
        
    except Exception as e:
        logging.error(f"Conversion error: {e}")
        
        # Clean up any temporary files
        try:
            upload_path = locals().get('upload_path')
            if upload_path and os.path.exists(upload_path):
                os.remove(upload_path)
            
            extracted_files = locals().get('extracted_files', [])
            if extracted_files:
                for file_path, _ in extracted_files:
                    if os.path.exists(file_path):
                        os.remove(file_path)
        except Exception as cleanup_error:
            logging.warning(f"Failed to clean up temporary files: {cleanup_error}")
        
        # Provide user-friendly error message
        if "network" in str(e).lower() or "timeout" in str(e).lower() or "connection" in str(e).lower():
            flash('Network connectivity issue with AI service. Please try again in a moment.', 'error')
        else:
            flash(f'Error during conversion: {str(e)}', 'error')
        
        return redirect(url_for('index'))

@app.route('/preview')
def preview_conversion():
    """Show preview of converted code with download option"""
    if 'conversion_result' not in session:
        flash('No conversion result found. Please upload and convert a file first.', 'error')
        return redirect(url_for('index'))
    
    result = session['conversion_result']
    return render_template('preview.html', **result)

@app.route('/download')
def download_converted():
    """Download the converted files as ZIP or single file"""
    if 'conversion_result' not in session:
        flash('No conversion result found. Please upload and convert a file first.', 'error')
        return redirect(url_for('index'))
    
    result = session['conversion_result']
    output_path = result['output_path']
    output_filename = result['output_filename']
    is_single_file = result.get('is_single_file', False)
    
    if not os.path.exists(output_path):
        flash('Converted file not found. Please try the conversion again.', 'error')
        return redirect(url_for('index'))
    
    # Set appropriate MIME type for single files
    if is_single_file:
        if output_filename.endswith('.java'):
            mimetype = 'text/x-java-source'
        elif output_filename.endswith('.kt'):
            mimetype = 'text/x-kotlin'
        elif output_filename.endswith('.swift'):
            mimetype = 'text/x-swift'
        else:
            mimetype = 'text/plain'
        
        return send_file(output_path, as_attachment=True, download_name=output_filename, mimetype=mimetype)
    else:
        return send_file(output_path, as_attachment=True, download_name=output_filename)

@app.route('/status')
def conversion_status():
    # This endpoint can be used for AJAX status checks if needed
    return jsonify({'status': 'ready'})

@app.route('/test-upload', methods=['GET', 'POST'])
def test_upload():
    if request.method == 'GET':
        return '''
        <html><body>
        <h2>Simple Upload Test</h2>
        <form method="POST" enctype="multipart/form-data">
            <p>Source: <select name="source_platform" required>
                <option value="android_java">Android Java</option>
                <option value="android_kotlin">Android Kotlin</option>
                <option value="ios_swift">iOS Swift</option>
            </select></p>
            <p>Target: <select name="target_platform" required>
                <option value="android_java">Android Java</option>
                <option value="android_kotlin">Android Kotlin</option>
                <option value="ios_swift">iOS Swift</option>
            </select></p>
            <p>File: <input type="file" name="code_file" accept=".java,.kt,.swift,.zip" required></p>
            <p><input type="submit" value="Test Convert"></p>
        </form>
        </body></html>
        '''
    else:
        # Same logic as convert_code but simplified
        try:
            file = request.files.get('code_file')
            filename = file.filename if file else 'No file'
            return f"Received: {filename}, Source: {request.form.get('source_platform')}, Target: {request.form.get('target_platform')}"
        except Exception as e:
            return f"Error: {str(e)}"

@app.errorhandler(413)
def too_large(e):
    flash('File too large. Maximum size is 50MB.', 'error')
    return redirect(url_for('index'))

@app.errorhandler(500)
def internal_error(e):
    logging.error(f"Internal server error: {e}")
    
    # Check if this is a network-related error
    error_str = str(e).lower()
    if any(term in error_str for term in ['network', 'timeout', 'connection', 'ssl', 'recv']):
        flash('Network connectivity issue with AI service. Please try again in a moment.', 'error')
    else:
        flash('An internal error occurred. Please try again. If the problem persists, try uploading individual files instead of a ZIP.', 'error')
    
    return redirect(url_for('index'))

@app.errorhandler(Exception)
def handle_exception(e):
    # Log the full error for debugging
    logging.exception(f"Unhandled exception: {e}")
    
    # Check for specific error types
    error_str = str(e).lower()
    if 'openai' in error_str or 'api' in error_str:
        flash('AI service error. Please try again in a moment.', 'error')
    elif 'zip' in error_str or 'extract' in error_str:
        flash('ZIP file processing error. Please check your file and try again.', 'error')
    elif any(term in error_str for term in ['network', 'timeout', 'connection']):
        flash('Network connectivity issue. Please try again.', 'error')
    else:
        flash(f'Error: {str(e)[:100]}...', 'error')
    
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

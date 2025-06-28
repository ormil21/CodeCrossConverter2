import os
import logging
import tempfile
from flask import Flask, render_template, request, redirect, url_for, flash, send_file, jsonify
from werkzeug.utils import secure_filename
from werkzeug.middleware.proxy_fix import ProxyFix

# Import our custom modules
from code_converter import CodeConverter
from file_handler import FileHandler

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Flask configuration
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key-change-in-production")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Configuration
UPLOAD_FOLDER = 'uploads'
CONVERTED_FOLDER = 'converted'
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
ALLOWED_EXTENSIONS = {'zip', 'java', 'kt', 'swift', 'xml'}

# Ensure upload directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(CONVERTED_FOLDER, exist_ok=True)

# Configure Flask app
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['CONVERTED_FOLDER'] = CONVERTED_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

# Initialize our handlers
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
        # Get form data
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
        
        # Filter valid files
        valid_files = [f for f in uploaded_files if f.filename and allowed_file(f.filename)]
        
        if not valid_files:
            flash('No valid files found. Only ZIP, Java, Kotlin, Swift, and XML files are allowed', 'error')
            return redirect(url_for('index'))
        
        # Process files
        all_extracted_files = []
        preserve_files = []
        is_multiple_files = len(valid_files) > 1
        filename = "conversion"  # Default output filename
        
        for upload_file in valid_files:
            if not upload_file.filename:
                continue
            secure_name = secure_filename(str(upload_file.filename))
            upload_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_name)
            upload_file.save(upload_path)
            filename = secure_name  # Use last file's name for output
            
            if secure_name.lower().endswith('.zip'):
                # Extract from ZIP
                try:
                    extraction_result = file_handler.extract_project_files(upload_path, source_platform)
                    
                    if len(extraction_result) == 4:
                        extracted_files, zip_preserve_files, skipped_files, error_files = extraction_result
                        all_extracted_files.extend(extracted_files)
                        preserve_files.extend(zip_preserve_files)
                    else:
                        # Fallback extraction
                        basic_result = file_handler.extract_code_files(upload_path, source_platform)
                        if len(basic_result) == 3:
                            extracted_files, skipped_files, error_files = basic_result
                            all_extracted_files.extend(extracted_files)
                        else:
                            all_extracted_files.extend(basic_result)
                            
                except Exception as e:
                    logging.error(f"Error extracting ZIP {secure_name}: {e}")
                    flash(f'Failed to extract ZIP file {secure_name}', 'error')
                    continue
            else:
                # Individual code file
                all_extracted_files.append((upload_path, secure_name))
        
        # Apply conversion type filtering
        if conversion_type != 'full_project' and all_extracted_files:
            filtered_files = []
            for file_path, relative_path in all_extracted_files:
                file_ext = relative_path.lower().split('.')[-1]
                
                if conversion_type == 'logic_only':
                    if file_ext in ['java', 'kt', 'swift']:
                        filtered_files.append((file_path, relative_path))
                elif conversion_type == 'layouts_only':
                    if file_ext in ['xml'] or 'layout' in relative_path.lower():
                        filtered_files.append((file_path, relative_path))
            
            all_extracted_files = filtered_files
            logging.info(f"Filtered to {len(all_extracted_files)} files for {conversion_type} conversion")
        
        if not all_extracted_files:
            flash(f'No {source_platform} code files found matching the conversion type.', 'error')
            return redirect(url_for('index'))
        
        # Convert files
        logging.info(f"Converting {len(all_extracted_files)} files from {source_platform} to {target_platform}")
        
        try:
            converted_files = code_converter.convert_files(all_extracted_files, source_platform, target_platform)
        except Exception as conversion_error:
            logging.error(f"Code conversion failed: {conversion_error}")
            
            # Create fallback files
            converted_files = []
            for file_path, relative_path in all_extracted_files:
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        source_code = f.read()
                    
                    fallback_comment = f"// CONVERSION FAILED: {str(conversion_error)[:100]}...\n// Original {source_platform} file preserved below\n\n"
                    fallback_content = fallback_comment + source_code
                    converted_files.append((relative_path, fallback_content))
                    
                except Exception as file_error:
                    logging.warning(f"Failed to create fallback for {relative_path}: {file_error}")
            
            if not converted_files:
                flash('Code conversion failed due to service issues. Please try again later.', 'error')
                return redirect(url_for('index'))
        
        # Save converted files
        if len(converted_files) == 1 and not is_multiple_files:
            # Single file output
            converted_filename, converted_content = converted_files[0]
            output_filename = f"converted_{source_platform}_to_{target_platform}_{converted_filename}"
            output_path = os.path.join(app.config['CONVERTED_FOLDER'], output_filename)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                if converted_content:
                    f.write(converted_content)
                else:
                    f.write("// Conversion failed - empty content")
            
            is_single_file = True
        else:
            # Multiple files - create ZIP
            output_filename = f"converted_{source_platform}_to_{target_platform}_{filename}"
            output_path = os.path.join(app.config['CONVERTED_FOLDER'], output_filename)
            file_handler.create_zip(converted_files, output_path, preserve_files)
            is_single_file = False
        
        # Store conversion info in session for preview
        logging.info(f"Conversion completed successfully: {output_filename}")
        flash('Code conversion completed successfully!', 'success')
        
        return redirect(url_for('preview_conversion', 
                              filename=output_filename,
                              source=source_platform,
                              target=target_platform,
                              single=is_single_file))
        
    except Exception as e:
        logging.error(f"Conversion error: {e}")
        flash('An error occurred during conversion. Please try again.', 'error')
        return redirect(url_for('index'))

@app.route('/preview/<filename>')
def preview_conversion(filename):
    """Show preview of converted code with download option"""
    source = request.args.get('source', 'unknown')
    target = request.args.get('target', 'unknown')
    is_single = request.args.get('single', 'false').lower() == 'true'
    
    file_path = os.path.join(app.config['CONVERTED_FOLDER'], filename)
    
    if not os.path.exists(file_path):
        flash('Converted file not found.', 'error')
        return redirect(url_for('index'))
    
    preview_content = None
    if is_single:
        # Read single file for preview
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                preview_content = f.read()
        except Exception as e:
            logging.error(f"Error reading preview file: {e}")
            preview_content = "Error reading file content."
    
    return render_template('preview.html', 
                         filename=filename,
                         source_platform=source,
                         target_platform=target,
                         is_single_file=is_single,
                         preview_content=preview_content)

@app.route('/download/<filename>')
def download_converted(filename):
    """Download the converted files"""
    file_path = os.path.join(app.config['CONVERTED_FOLDER'], filename)
    
    if not os.path.exists(file_path):
        flash('File not found.', 'error')
        return redirect(url_for('index'))
    
    # Determine if it's a single file or ZIP based on extension
    is_single_file = not filename.lower().endswith('.zip')
    
    if is_single_file:
        # For single files, send as attachment with proper content type
        return send_file(file_path, as_attachment=True, download_name=filename, mimetype='text/plain')
    else:
        # For ZIP files, send with proper ZIP mimetype
        return send_file(file_path, as_attachment=True, download_name=filename, mimetype='application/zip')

@app.route('/status')
def conversion_status():
    """Return conversion status (for AJAX polling if needed)"""
    return jsonify({'status': 'ready'})

@app.route('/test')
def test_upload():
    """Test route for debugging"""
    return jsonify({
        'upload_folder': app.config['UPLOAD_FOLDER'],
        'converted_folder': app.config['CONVERTED_FOLDER'],
        'max_file_size': app.config['MAX_CONTENT_LENGTH']
    })

# Error handlers
@app.errorhandler(413)
def too_large(e):
    flash('File is too large. Maximum size is 50MB.', 'error')
    return redirect(url_for('index'))

@app.errorhandler(500)
def internal_error(e):
    logging.error(f"Internal server error: {e}")
    flash('An internal error occurred. Please try again.', 'error')
    return redirect(url_for('index'))

@app.errorhandler(Exception)
def handle_exception(e):
    logging.error(f"Unhandled exception: {e}")
    flash('An unexpected error occurred. Please try again.', 'error')
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
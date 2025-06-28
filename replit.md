# Mobile Code Converter

## Overview

This is a Flask-based web application that converts mobile application code between different platforms (Android Java, Android Kotlin, iOS Swift) using OpenAI's GPT-4 API. Users can upload either ZIP files containing multiple source code files or individual code files (.java, .kt, .swift), select source and target platforms, and receive converted code files in a downloadable ZIP format.

## System Architecture

The application follows a modular Flask architecture with clear separation of concerns:

- **Web Layer**: Flask application with HTML templates and static assets
- **Business Logic**: Separate modules for code conversion and file handling
- **AI Integration**: OpenAI GPT-4 API for intelligent code conversion
- **File Processing**: ZIP file extraction and code file filtering

## Key Components

### Backend Components

1. **app.py**: Main Flask application with routing and request handling
   - Handles file uploads with size limits (50MB)
   - Manages conversion workflow
   - Provides error handling and user feedback

2. **code_converter.py**: AI-powered code conversion service
   - Integrates with OpenAI GPT-4 API
   - Handles single file and batch conversions
   - Generates appropriate error comments for failed conversions

3. **file_handler.py**: File processing and extraction utilities
   - Extracts code files from ZIP archives
   - Filters files by platform-specific extensions
   - Manages temporary file operations

4. **main.py**: Application entry point for development server

### Frontend Components

1. **templates/index.html**: Main user interface
   - Bootstrap-based responsive design
   - Dark theme implementation
   - Form validation and user feedback

2. **static/style.css**: Custom styling and animations
   - Enhanced Bootstrap components
   - Responsive design elements
   - Loading states and transitions

3. **static/script.js**: Client-side functionality
   - Platform validation logic
   - File upload handling
   - Progress indicators and user experience enhancements

## Data Flow

1. **File Upload**: User selects either a ZIP file containing multiple source code files or a single code file (.java, .kt, .swift)
2. **Platform Selection**: User chooses source and target platforms
3. **File Processing**: 
   - For ZIP files: Contents are extracted and filtered by file extensions
   - For single files: File extension is validated against the selected source platform
4. **Code Conversion**: Each code file is processed through OpenAI GPT-4
5. **Result Packaging**: Converted files are packaged into a ZIP for download
6. **Cleanup**: Temporary files are removed after processing

## External Dependencies

### Core Technologies
- **Flask**: Web framework for Python
- **OpenAI API**: GPT-4 model for code conversion
- **Bootstrap 5**: Frontend UI framework with dark theme
- **Font Awesome**: Icon library

### Python Libraries
- **werkzeug**: WSGI utilities and file handling
- **zipfile**: ZIP archive processing
- **tempfile**: Temporary file management
- **pathlib**: File path operations

### Platform Support
- **Android Java**: `.java` files
- **Android Kotlin**: `.kt` files  
- **iOS Swift**: `.swift` files

## Deployment Strategy

The application is configured for deployment with:

- **Development Server**: Flask development server on port 5000
- **Production Ready**: ProxyFix middleware for reverse proxy compatibility
- **Environment Variables**: 
  - `OPENAI_API_KEY`: Required for AI functionality
  - `SESSION_SECRET`: Flask session security (defaults to dev key)
- **File System**: Local storage for uploads and temporary processing
- **Error Handling**: Comprehensive logging and user-friendly error messages

### Security Considerations
- File type validation (ZIP only)
- File size limits (50MB maximum)
- Secure filename handling
- Session management with secret keys

## Changelog
- June 28, 2025: Initial setup with ZIP file support
- June 28, 2025: Added support for individual code file uploads (.java, .kt, .swift)
- June 28, 2025: Fixed form submission issues and resolved OpenAI API quota problems
- June 28, 2025: Added code preview page with syntax highlighting and download functionality
- June 28, 2025: Fixed single-file downloads to serve as plain text files instead of ZIP archives
- June 28, 2025: Added copy-to-clipboard functionality for converted code with cross-browser support
- June 28, 2025: Implemented comprehensive error handling with retry logic and graceful fallbacks
- June 28, 2025: Added support for Android project structures including XML layout files
- June 28, 2025: Enhanced ZIP file extraction with detailed error reporting and file type filtering
- June 28, 2025: Implemented comprehensive Android project support with smart file filtering
- June 28, 2025: Added asset preservation system for images and project files  
- June 28, 2025: Enhanced network resilience with multi-layer error handling and fallback systems
- June 28, 2025: Added multiple file upload support for individual code files and mixed file types
- June 28, 2025: Implemented conversion type filtering (Full Project, Logic Only, Layouts Only)
- June 28, 2025: Added comprehensive progress indicators with step-by-step status updates
- June 28, 2025: Enhanced file validation with support for XML layout files and better error messages
- June 28, 2025: Restructured app architecture for better error handling and variable scope management

## User Preferences

Preferred communication style: Simple, everyday language.
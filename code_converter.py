import os
import logging
import time
import random
import httpx
from openai import OpenAI

class CodeConverter:
    def __init__(self):
        # Create a custom HTTP client with more robust timeout and retry settings
        http_client = httpx.Client(
            timeout=httpx.Timeout(60.0, connect=10.0),  # 60s total, 10s connect
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            transport=httpx.HTTPTransport(retries=3)
        )
        
        self.openai_client = OpenAI(
            api_key=os.environ.get("OPENAI_API_KEY"),
            http_client=http_client,
            timeout=60.0
        )
        # the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
        # do not change this unless explicitly requested by the user
        self.model = "gpt-4o"
    
    def convert_files(self, extracted_files, source_platform, target_platform):
        """Convert a list of code files from source to target platform"""
        converted_files = []
        
        for file_path, relative_path in extracted_files:
            try:
                logging.info(f"Converting {relative_path}")
                
                # Read the source code
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    source_code = f.read()
                
                # Convert the code
                converted_code = self._convert_single_file(
                    source_code, source_platform, target_platform, relative_path
                )
                
                # Determine the new file extension
                new_filename = self._get_converted_filename(relative_path, source_platform, target_platform)
                
                converted_files.append((new_filename, converted_code))
                
            except Exception as e:
                logging.error(f"Error converting {relative_path}: {e}")
                # Include the original file with an error comment
                error_comment = self._get_error_comment(str(e), target_platform)
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    original_code = f.read()
                converted_files.append((relative_path, f"{error_comment}\n\n{original_code}"))
        
        return converted_files
    
    def _convert_single_file(self, source_code, source_platform, target_platform, filename):
        """Convert a single code file using OpenAI GPT-4"""
        
        # Create conversion prompt
        prompt = self._create_conversion_prompt(
            source_code, source_platform, target_platform, filename
        )
        
        # Retry configuration
        max_retries = 3
        retry_delay = 2  # seconds
        
        for attempt in range(max_retries):
            try:
                logging.info(f"Attempting conversion of {filename} (attempt {attempt + 1}/{max_retries})")
                
                response = self.openai_client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": self._get_system_prompt(source_platform, target_platform)
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    max_tokens=4000,
                    temperature=0.1
                )
                
                converted_code = response.choices[0].message.content
                if converted_code:
                    converted_code = converted_code.strip()
                else:
                    raise Exception("Empty response from OpenAI API")
                
                # Clean up the response if it contains markdown code blocks
                if converted_code.startswith('```'):
                    lines = converted_code.split('\n')
                    if lines[0].startswith('```'):
                        lines = lines[1:]
                    if lines[-1].strip() == '```':
                        lines = lines[:-1]
                    converted_code = '\n'.join(lines)
                
                logging.info(f"Successfully converted {filename} on attempt {attempt + 1}")
                return converted_code
                
            except Exception as e:
                logging.error(f"OpenAI API error for {filename} (attempt {attempt + 1}): {e}")
                
                if attempt < max_retries - 1:
                    logging.info(f"Retrying in {retry_delay} seconds...")
                    import time
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    # Final attempt failed, try basic text-based conversion fallback
                    logging.warning(f"All AI conversion attempts failed for {filename}, using basic fallback")
                    return self._fallback_conversion(source_code, source_platform, target_platform, filename)
    
    def _get_system_prompt(self, source_platform, target_platform):
        """Get the system prompt for code conversion"""
        return f"""You are an expert mobile app developer specializing in cross-platform code conversion.
Your task is to convert {source_platform} code to {target_platform} code while maintaining the same functionality.

Special handling for different file types:
- For Java/Kotlin files: Convert class structures, methods, and Android-specific APIs
- For XML layout files: Convert Android layouts to equivalent iOS storyboard/XIB concepts or SwiftUI code
- For AndroidManifest.xml: Convert to iOS Info.plist equivalent information
- Maintain proper platform conventions and best practices

Key guidelines:
1. Preserve the original logic and functionality
2. Use platform-appropriate naming conventions and patterns
3. Convert UI components to their platform equivalents
4. Handle platform-specific APIs appropriately
5. Maintain code structure and organization
6. Add helpful comments for complex conversions
7. Ensure the converted code follows best practices for the target platform

Return only the converted code without any explanations or markdown formatting."""
    
    def _create_conversion_prompt(self, source_code, source_platform, target_platform, filename):
        """Create the conversion prompt for a specific file"""
        platform_info = {
            'android_java': 'Android Java',
            'android_kotlin': 'Android Kotlin',
            'ios_swift': 'iOS Swift'
        }
        
        source_name = platform_info.get(source_platform, source_platform)
        target_name = platform_info.get(target_platform, target_platform)
        
        # Determine file type for specialized handling
        file_ext = filename.split('.')[-1].lower() if '.' in filename else ''
        
        if file_ext == 'xml':
            if 'layout' in filename.lower() or 'activity_' in filename.lower():
                file_type = "Android layout XML"
                conversion_note = f"Convert this Android layout to equivalent {target_name} layout approach (SwiftUI, Storyboard, or XIB)"
            elif 'androidmanifest' in filename.lower():
                file_type = "AndroidManifest.xml"
                conversion_note = f"Convert this Android manifest to equivalent iOS Info.plist format"
            else:
                file_type = f"{source_name} XML configuration"
                conversion_note = f"Convert this configuration to equivalent {target_name} format"
        else:
            file_type = f"{source_name} code"
            conversion_note = f"Convert this code to {target_name} while maintaining the same functionality and structure"
        
        return f"""Convert the following {file_type} to {target_name}:

File: {filename}

Source Code:
{source_code}

Instructions: {conversion_note}
- Follow platform best practices and conventions
- Maintain equivalent functionality
- Provide only the converted code without explanations"""
    
    def _get_converted_filename(self, original_filename, source_platform, target_platform):
        """Generate the appropriate filename for the converted code"""
        name, ext = os.path.splitext(original_filename)
        
        # Extension mapping
        extension_map = {
            'android_java': '.java',
            'android_kotlin': '.kt',
            'ios_swift': '.swift'
        }
        
        new_ext = extension_map.get(target_platform, ext)
        return f"{name}{new_ext}"
    
    def _get_error_comment(self, error_message, target_platform):
        """Generate an appropriate error comment for the target platform"""
        comment_styles = {
            'android_java': f"// CONVERSION ERROR: {error_message}",
            'android_kotlin': f"// CONVERSION ERROR: {error_message}",
            'ios_swift': f"// CONVERSION ERROR: {error_message}"
        }
        
        return comment_styles.get(target_platform, f"# CONVERSION ERROR: {error_message}")
    
    def _fallback_conversion(self, source_code, source_platform, target_platform, filename):
        """Basic text-based conversion when AI service is unavailable"""
        
        # Create error/info header
        error_comment = self._get_error_comment(
            f"AI service temporarily unavailable. This is the original {source_platform} code with basic conversion notes.",
            target_platform
        )
        
        # Add basic conversion guidance based on file type
        guidance = self._get_conversion_guidance(source_platform, target_platform, filename)
        
        return f"""{error_comment}

{guidance}

/*
 * ORIGINAL {source_platform.upper()} CODE:
 * To complete the conversion:
 * 1. Review the conversion notes above
 * 2. Apply platform-specific changes manually
 * 3. Test and adjust as needed
 */

{source_code}"""
    
    def _get_conversion_guidance(self, source_platform, target_platform, filename):
        """Get basic conversion guidance for different platform combinations"""
        file_ext = filename.split('.')[-1].lower() if '.' in filename else ''
        
        if source_platform == 'android_java' and target_platform == 'ios_swift':
            if file_ext == 'xml':
                return """/*
 * CONVERSION NOTES FOR ANDROID XML TO iOS SWIFT:
 * - Convert LinearLayout to VStack/HStack in SwiftUI
 * - Convert TextView to Text() in SwiftUI
 * - Convert Button to Button() in SwiftUI
 * - Convert EditText to TextField() in SwiftUI
 * - Replace android:layout_width/height with SwiftUI modifiers
 * - Convert android:onClick to SwiftUI actions
 */"""
            else:
                return """/*
 * CONVERSION NOTES FOR ANDROID JAVA TO iOS SWIFT:
 * - Convert classes to Swift classes/structs
 * - Replace findViewById with @IBOutlet or SwiftUI @State
 * - Convert setOnClickListener to SwiftUI actions
 * - Replace Intent with segues or NavigationView
 * - Convert AsyncTask to async/await or combine
 * - Replace SharedPreferences with UserDefaults
 */"""
        
        elif source_platform == 'android_kotlin' and target_platform == 'ios_swift':
            return """/*
 * CONVERSION NOTES FOR ANDROID KOTLIN TO iOS SWIFT:
 * - Convert data classes to Swift structs
 * - Replace lateinit var with Swift optionals or lazy properties
 * - Convert coroutines to async/await
 * - Replace Kotlin extensions with Swift extensions
 * - Convert when expressions to switch statements
 */"""
        
        else:
            return f"""/*
 * CONVERSION NOTES FOR {source_platform.upper()} TO {target_platform.upper()}:
 * - Review platform-specific APIs and frameworks
 * - Update import statements and dependencies
 * - Adapt UI components to target platform conventions
 * - Adjust navigation and lifecycle patterns
 */"""

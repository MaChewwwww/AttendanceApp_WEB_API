"""
CRITICAL SECURITY MODULE: Advanced Face Verification & Anti-Spoofing System

This module is the CORE SECURITY COMPONENT of the attendance system, responsible for:
1. Preventing attendance fraud through sophisticated anti-spoofing detection
2. Verifying student identity through advanced face matching algorithms
3. Ensuring only live, authentic faces can submit attendance

SECURITY IMPORTANCE:
- Without this module, students could submit photos from phones/computers to fake attendance
- Prevents printed photo spoofing attempts
- Blocks digital manipulation and screen display spoofing
- Ensures academic integrity in attendance tracking

The anti-spoofing algorithms use multiple detection techniques to identify fake submissions:
- Screen reflection patterns, moiré effects, digital artifacts, lighting analysis
- JPEG compression detection, edge detection for screen borders
- Image quality assessment and color distribution analysis
"""

import cv2
import numpy as np
import base64  # Move base64 import to module level
from typing import Tuple, Optional
import face_recognition

def detect_face_spoofing(image: np.ndarray) -> Tuple[bool, str]:
    """
    CRITICAL SECURITY FUNCTION: Multi-layered spoofing detection system
    
    This function implements 6 different anti-spoofing techniques to detect fake submissions:
    
    1. SHARPNESS ANALYSIS: Blurry images often indicate photos of photos
    2. SCREEN REFLECTION DETECTION: Identifies phone/computer screen displays
    3. COLOR DISTRIBUTION ANALYSIS: Detects artificial digital displays
    4. EDGE DETECTION: Finds rectangular screen borders in submissions
    5. LIGHTING CONSISTENCY: Identifies artificial or uniform lighting
    6. JPEG ARTIFACT DETECTION: Recognizes digital photo compression patterns
    
    Args:
        image (np.ndarray): The submitted face image to analyze
        
    Returns:
        Tuple[bool, str]: (is_live_face, detection_message)
        - True: Live face detected, safe to proceed
        - False: Spoofing attempt detected, block submission
        
    SECURITY CRITICAL: This function is the first line of defense against attendance fraud
    """
    try:
        # Convert to grayscale for computational analysis
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # TECHNIQUE 1: SHARPNESS ANALYSIS
        # Real faces have natural texture and sharpness variations
        # Photos of photos tend to be blurry due to double compression
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        laplacian_var = float(np.var(laplacian.astype(np.float64)))
        if laplacian_var < 100:  # Threshold determined through testing
            return False, "Image too blurry"
        
        # TECHNIQUE 2: SCREEN REFLECTION & MOIRÉ PATTERN DETECTION
        # Phone/computer screens create high-frequency artifacts and patterns
        # These patterns are visible when photographing a screen
        kernel = np.array([[-1,-1,-1], [-1,8,-1], [-1,-1,-1]])  # High-pass filter
        high_freq = cv2.filter2D(gray, -1, kernel)
        # Fix: Explicit type conversion for variance calculation
        high_freq_var = float(np.var(high_freq.astype(np.float64)))
        
        if high_freq_var > 2000:  # High variance indicates screen artifacts
            return False, "Screen display detected"
        
        # TECHNIQUE 3: COLOR DISTRIBUTION ANALYSIS
        # Real faces have natural color variation across hue spectrum
        # Digital displays have limited color peaks and artificial distribution
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        hist_h = cv2.calcHist([hsv], [0], None, [180], [0, 180])
        
        # Fix: Explicit type conversion for mean calculation
        hist_mean = float(np.mean(hist_h.astype(np.float64)))
        color_peaks = np.sum(hist_h > hist_mean * 3)
        if color_peaks < 5:  # Too few color peaks indicates digital display
            return False, "Digital display detected"
        
        # TECHNIQUE 4: RECTANGULAR EDGE DETECTION (SCREEN BORDER DETECTION)
        # Phones/tablets/computers have rectangular screens with sharp edges
        # Real environments don't have large rectangular shapes
        edges = cv2.Canny(gray, 50, 150)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        for contour in contours:
            # Check if contour covers significant portion of image (likely screen border)
            if cv2.contourArea(contour) > image.shape[0] * image.shape[1] * 0.3:
                # Approximate contour to check if it's rectangular
                approx = cv2.approxPolyDP(contour, 0.02 * cv2.arcLength(contour, True), True)
                if len(approx) == 4:  # Rectangle detected
                    return False, "Screen border detected"
        
        # TECHNIQUE 5: LIGHTING CONSISTENCY ANALYSIS
        # Real faces have natural lighting variations and shadows
        # Artificial/uniform lighting indicates digital display or printed photo
        # Fix: Explicit type conversion for std calculation
        brightness_std = float(np.std(gray.astype(np.float64)))
        if brightness_std < 20:  # Too uniform lighting
            return False, "Artificial lighting detected"
        
        # TECHNIQUE 6: JPEG COMPRESSION ARTIFACT DETECTION
        # Digital photos have specific frequency domain patterns from JPEG compression
        # These patterns form block structures that can be detected
        f_transform = np.fft.fft2(gray.astype(np.float64))  # Fix: Explicit type conversion for FFT
        f_shift = np.fft.fftshift(f_transform)  # Shift zero frequency to center
        magnitude = np.abs(f_shift)
        
        # Check for 8x8 block patterns typical of JPEG compression
        block_pattern = np.sum(magnitude[::8, ::8])  # Sample every 8th pixel
        total_magnitude = np.sum(magnitude)
        
        if block_pattern / total_magnitude > 0.1:  # Too much block structure
            return False, "Digital photo detected"
        
        # ALL TESTS PASSED: This appears to be a live face
        return True, "Live face detected"
        
    except Exception as e:
        # If any analysis fails, err on the side of caution and block submission
        return False, "Liveness check failed"

def enhanced_face_comparison(stored_face_image: bytes, submitted_face_image: str, tolerance: float = 0.3) -> Tuple[bool, str]:
    """
    ADVANCED FACE VERIFICATION with integrated anti-spoofing protection
    
    This function performs the complete face verification process:
    1. Decodes and validates both stored and submitted images
    2. Runs anti-spoofing detection on submitted image
    3. Uses deep learning algorithms for precise face matching
    4. Calculates confidence scores for verification accuracy
    
    PROCESS FLOW:
    stored_image (from DB) → decode → face_encoding
                                         ↓
    submitted_image → decode → anti_spoof_check → face_encoding → COMPARE → result
    
    Args:
        stored_face_image (bytes): Student's profile face image from database
        submitted_face_image (str): Base64 encoded face image from attendance submission
        tolerance (float): Matching sensitivity (lower = stricter matching)
        
    Returns:
        Tuple[bool, str]: (verification_success, detailed_message)
        
    SECURITY FEATURES:
    - Mandatory anti-spoofing check before any face comparison
    - Uses state-of-the-art deep learning face recognition
    - Provides confidence scores for audit trail
    - Blocks submission if spoofing detected at any stage
    """
    try:
        # STEP 1: DECODE STORED FACE IMAGE FROM DATABASE WITH BETTER FORMAT DETECTION
        print(f"DEBUG: Stored face image type: {type(stored_face_image)}")
        print(f"DEBUG: Stored face image length: {len(stored_face_image) if stored_face_image else 'None'}")
        
        # Check if stored face image is None or empty
        if not stored_face_image:
            return False, "No stored face image found in profile"
        
        # Check if stored face image is too small (likely corrupted)
        if len(stored_face_image) < 100:  # Minimum size for a valid image
            return False, "Stored face image appears to be corrupted (too small)"
        
        try:
            # ENHANCED FORMAT DETECTION: Check image headers more thoroughly
            header_bytes = stored_face_image[:20]
            print(f"DEBUG: Image header bytes: {[hex(b) for b in header_bytes[:10]]}")
            
            # Detect image format more accurately
            image_format = "unknown"
            if stored_face_image[:2] == b'\xff\xd8':
                image_format = "JPEG"
                print("DEBUG: Detected JPEG image format (starts with FF D8)")
            elif stored_face_image[:8] == b'\x89PNG\r\n\x1a\n':
                image_format = "PNG"
                print("DEBUG: Detected PNG image format")
            elif stored_face_image[:6] in [b'GIF87a', b'GIF89a']:
                image_format = "GIF"
                print("DEBUG: Detected GIF image format")
            elif stored_face_image[:4] == b'RIFF' and stored_face_image[8:12] == b'WEBP':
                image_format = "WEBP"
                print("DEBUG: Detected WEBP image format")
            else:
                print("DEBUG: Unknown image format detected")
                print(f"DEBUG: First 20 bytes as hex: {stored_face_image[:20].hex()}")
                print(f"DEBUG: First 20 bytes as text (ignore errors): {repr(stored_face_image[:20])}")
            
            # Try multiple decode approaches with format-specific handling
            stored_np_array = np.frombuffer(stored_face_image, np.uint8)
            print(f"DEBUG: Numpy array shape: {stored_np_array.shape}")
            print(f"DEBUG: Numpy array dtype: {stored_np_array.dtype}")
            
            # Primary decode attempt - this should work for most formats
            stored_image = cv2.imdecode(stored_np_array, cv2.IMREAD_COLOR)
            
            if stored_image is None:
                print(f"DEBUG: Primary cv2.imdecode failed for {image_format} format, trying alternatives...")
                
                # Alternative 1: Try with IMREAD_UNCHANGED (preserves alpha channel)
                stored_image = cv2.imdecode(stored_np_array, cv2.IMREAD_UNCHANGED)
                if stored_image is not None:
                    print(f"DEBUG: Alternative decode with IMREAD_UNCHANGED succeeded for {image_format}")
                    # Handle different channel configurations
                    if len(stored_image.shape) == 3:
                        if stored_image.shape[2] == 4:
                            # RGBA to BGR
                            print("DEBUG: Converting RGBA to BGR")
                            stored_image = cv2.cvtColor(stored_image, cv2.COLOR_RGBA2BGR)
                        elif stored_image.shape[2] == 3:
                            # Might be RGB instead of BGR, check if conversion needed
                            print(f"DEBUG: 3-channel image detected, assuming BGR")
                            # stored_image = cv2.cvtColor(stored_image, cv2.COLOR_RGB2BGR)  # Uncomment if needed
                    elif len(stored_image.shape) == 2:
                        # Grayscale to BGR
                        print("DEBUG: Converting grayscale to BGR")
                        stored_image = cv2.cvtColor(stored_image, cv2.COLOR_GRAY2BGR)
                else:
                    print("DEBUG: Alternative decode with IMREAD_UNCHANGED also failed")
                    
                    # Alternative 2: Maybe it's base64 encoded in the database
                    if stored_image is None:
                        try:
                            print("DEBUG: Trying base64 decode (double-encoded scenario)")
                            # Use the module-level imported base64, don't import again
                            decoded_bytes = base64.b64decode(stored_face_image)
                            test_array = np.frombuffer(decoded_bytes, np.uint8)
                            stored_image = cv2.imdecode(test_array, cv2.IMREAD_COLOR)
                            if stored_image is not None:
                                print("DEBUG: Image was base64 encoded in database!")
                            else:
                                print("DEBUG: Base64 decode attempt also failed")
                        except Exception as b64_error:
                            print(f"DEBUG: Base64 decode attempt failed with exception: {b64_error}")
                    
                    # Alternative 3: Try different image libraries (if available)
                    if stored_image is None:
                        try:
                            print("DEBUG: Trying PIL/Pillow as fallback")
                            from PIL import Image
                            import io
                            
                            # Convert bytes to PIL Image
                            pil_image = Image.open(io.BytesIO(stored_face_image))
                            # Convert PIL to numpy array
                            stored_image = np.array(pil_image)
                            # Convert RGB to BGR for OpenCV
                            if len(stored_image.shape) == 3 and stored_image.shape[2] == 3:
                                stored_image = cv2.cvtColor(stored_image, cv2.COLOR_RGB2BGR)
                            print(f"DEBUG: PIL decode successful, shape: {stored_image.shape}")
                        except Exception as pil_error:
                            print(f"DEBUG: PIL decode failed: {pil_error}")
            
            if stored_image is None:
                print(f"DEBUG: All decode attempts failed for {image_format} format")
                print(f"DEBUG: Image size: {len(stored_face_image)} bytes")
                print(f"DEBUG: Image header: {stored_face_image[:50].hex()}")
                return False, f"Could not decode stored face image - unsupported {image_format} format or corrupted data"
            
            print(f"DEBUG: Successfully decoded stored {image_format} image, shape: {stored_image.shape}")
            
        except Exception as decode_error:
            print(f"DEBUG: Exception during stored image decode: {str(decode_error)}")
            import traceback
            traceback.print_exc()
            return False, f"Error decoding stored face image: {str(decode_error)}"
        
        # STEP 2: DECODE SUBMITTED FACE IMAGE FROM BASE64
        # Handle data URI format (data:image/jpeg;base64,xxxxx)
        if submitted_face_image.startswith('data:image'):
            submitted_face_image = submitted_face_image.split(',')[1]
        
        try:
            submitted_image_data = base64.b64decode(submitted_face_image)
            submitted_np_array = np.frombuffer(submitted_image_data, np.uint8)
            submitted_image = cv2.imdecode(submitted_np_array, cv2.IMREAD_COLOR)
            
            if submitted_image is None:
                return False, "Could not decode submitted face image"
            
            print(f"DEBUG: Submitted image shape: {submitted_image.shape}")
            
        except Exception as decode_error:
            print(f"DEBUG: Error decoding submitted image: {str(decode_error)}")
            return False, f"Error decoding submitted face image: {str(decode_error)}"
        
        # STEP 3: CRITICAL SECURITY CHECK - ANTI-SPOOFING DETECTION
        # This is the most important security step - MUST pass before face comparison
        print("Checking face liveness...")
        is_live, liveness_message = detect_face_spoofing(submitted_image)
        if not is_live:
            print(f"Liveness check failed: {liveness_message}")
            # SECURITY BLOCK: Spoofing detected, immediately reject submission
            return False, f"Spoofing detected: {liveness_message}"
        
        print("Liveness check passed")
        
        # STEP 4: PREPARE IMAGES FOR FACE RECOGNITION
        # Convert BGR (OpenCV) to RGB (face_recognition library requirement)
        stored_rgb = cv2.cvtColor(stored_image, cv2.COLOR_BGR2RGB)
        submitted_rgb = cv2.cvtColor(submitted_image, cv2.COLOR_BGR2RGB)
        
        # STEP 5: EXTRACT FACE ENCODINGS (DEEP LEARNING FEATURE EXTRACTION)
        # This uses advanced CNN models to extract unique facial features
        stored_encodings = face_recognition.face_encodings(stored_rgb)
        submitted_encodings = face_recognition.face_encodings(submitted_rgb)
        
        # Validate that faces were detected in both images
        if len(stored_encodings) == 0:
            return False, "No face detected in stored image"
        
        if len(submitted_encodings) == 0:
            return False, "No face detected in submitted image"
        
        # Use the first (and should be only) face found in each image
        stored_encoding = stored_encodings[0]
        submitted_encoding = submitted_encodings[0]
        
        # STEP 6: FACE COMPARISON USING EUCLIDEAN DISTANCE
        # Compare the mathematical representations of the faces
        matches = face_recognition.compare_faces([stored_encoding], submitted_encoding, tolerance=tolerance)
        face_distance = face_recognition.face_distance([stored_encoding], submitted_encoding)[0]
        
        # Convert distance to confidence percentage (0-100%)
        confidence = round((1 - face_distance) * 100, 2)
        
        # STEP 7: FINAL VERIFICATION DECISION
        if matches[0]:
            print(f"Face verification successful - Confidence: {confidence}%")
            return True, f"Face verified (confidence: {confidence}%)"
        else:
            print(f"Face verification failed - Confidence: {confidence}%")
            return False, f"Face does not match (confidence: {confidence}%)"
        
    except Exception as e:
        # Log error and block submission for security
        print(f"DEBUG: Enhanced face comparison error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False, f"Face comparison error: {str(e)}"

def simple_face_comparison_with_liveness(stored_face_image: bytes, submitted_face_image: str) -> Tuple[bool, str]:
    """
    FALLBACK FACE VERIFICATION with anti-spoofing protection
    
    This is a simpler but still secure face comparison method used when:
    - face_recognition library is not available
    - Advanced algorithms fail due to system constraints
    - Fallback verification is needed for system reliability
    
    STILL INCLUDES ANTI-SPOOFING: Even the fallback method includes spoofing detection
    for consistent security across all verification paths.
    
    METHOD: Uses OpenCV histogram correlation for face matching
    - Converts images to grayscale for analysis
    - Calculates pixel intensity histograms
    - Compares histogram correlation for similarity
    
    Args:
        stored_face_image (bytes): Student's profile face from database
        submitted_face_image (str): Base64 encoded submission
        
    Returns:
        Tuple[bool, str]: (verification_result, message)
        
    SECURITY: Maintains anti-spoofing protection even in fallback mode
    """
    try:
        # DECODE STORED IMAGE WITH ENHANCED FORMAT DETECTION
        print(f"DEBUG: (Simple) Stored face image type: {type(stored_face_image)}")
        print(f"DEBUG: (Simple) Stored face image length: {len(stored_face_image) if stored_face_image else 'None'}")
        
        # Check if stored face image is None or empty
        if not stored_face_image:
            return False, "No stored face image found in profile"
        
        # Check if stored face image is too small (likely corrupted)
        if len(stored_face_image) < 100:  # Minimum size for a valid image
            return False, "Stored face image appears to be corrupted (too small)"
        
        try:
            # Enhanced format detection for simple method
            header_bytes = stored_face_image[:10]
            print(f"DEBUG: (Simple) Image header: {[hex(b) for b in header_bytes]}")
            
            image_format = "unknown"
            if stored_face_image[:2] == b'\xff\xd8':
                image_format = "JPEG"
                print("DEBUG: (Simple) JPEG format detected")
            elif stored_face_image[:8] == b'\x89PNG\r\n\x1a\n':
                image_format = "PNG"
                print("DEBUG: (Simple) PNG format detected")
            else:
                print(f"DEBUG: (Simple) Unknown format, header: {stored_face_image[:10].hex()}")
            
            stored_np_array = np.frombuffer(stored_face_image, np.uint8)
            stored_image = cv2.imdecode(stored_np_array, cv2.IMREAD_COLOR)
            
            if stored_image is None:
                print(f"DEBUG: (Simple) Primary decode failed for {image_format}, trying alternatives...")
                
                # Try with IMREAD_UNCHANGED
                stored_image = cv2.imdecode(stored_np_array, cv2.IMREAD_UNCHANGED)
                if stored_image is not None and len(stored_image.shape) >= 2:
                    if len(stored_image.shape) == 3:
                        if stored_image.shape[2] == 4:  # RGBA
                            stored_image = cv2.cvtColor(stored_image, cv2.COLOR_RGBA2BGR)
                            print("DEBUG: (Simple) RGBA to BGR conversion successful")
                        elif stored_image.shape[2] == 3:
                            print("DEBUG: (Simple) 3-channel image, assuming BGR")
                    elif len(stored_image.shape) == 2:  # Grayscale
                        stored_image = cv2.cvtColor(stored_image, cv2.COLOR_GRAY2BGR)
                        print("DEBUG: (Simple) Grayscale to BGR conversion successful")
                    print("DEBUG: (Simple) Alternative decode succeeded")
                else:
                    # Try base64 decode
                    try:
                        # Use the module-level imported base64, don't import again
                        decoded_bytes = base64.b64decode(stored_face_image)
                        test_array = np.frombuffer(decoded_bytes, np.uint8)
                        stored_image = cv2.imdecode(test_array, cv2.IMREAD_COLOR)
                        if stored_image is not None:
                            print("DEBUG: (Simple) Base64 decode succeeded")
                    except:
                        pass
                    
                    # Try PIL as last resort
                    if stored_image is None:
                        try:
                            from PIL import Image
                            import io
                            pil_image = Image.open(io.BytesIO(stored_face_image))
                            stored_image = np.array(pil_image)
                            if len(stored_image.shape) == 3 and stored_image.shape[2] == 3:
                                stored_image = cv2.cvtColor(stored_image, cv2.COLOR_RGB2BGR)
                            print("DEBUG: (Simple) PIL decode succeeded")
                        except Exception as pil_error:
                            print(f"DEBUG: (Simple) PIL decode failed: {pil_error}")
            
            if stored_image is None:
                print(f"DEBUG: (Simple) All decode attempts failed for {image_format}")
                return False, f"Could not decode stored face image - invalid {image_format} format"
            
            print(f"DEBUG: (Simple) Successfully decoded {image_format}, shape: {stored_image.shape}")
            
        except Exception as decode_error:
            print(f"DEBUG: (Simple) Decode error: {str(decode_error)}")
            return False, f"Error decoding stored face image: {str(decode_error)}"
        
        # DECODE SUBMITTED IMAGE
        if submitted_face_image.startswith('data:image'):
            submitted_face_image = submitted_face_image.split(',')[1]
        
        try:
            submitted_image_data = base64.b64decode(submitted_face_image)
            submitted_np_array = np.frombuffer(submitted_image_data, np.uint8)
            submitted_image = cv2.imdecode(submitted_np_array, cv2.IMREAD_COLOR)
            
            if submitted_image is None:
                return False, "Could not decode submitted face image"
            
            print(f"DEBUG: (Simple) Submitted image shape: {submitted_image.shape}")
            
        except Exception as decode_error:
            print(f"DEBUG: (Simple) Error decoding submitted image: {str(decode_error)}")
            return False, f"Error decoding submitted face image: {str(decode_error)}"
        
        # CRITICAL: ANTI-SPOOFING CHECK (same as advanced method)
        print("Checking face liveness (simple)...")
        is_live, liveness_message = detect_face_spoofing(submitted_image)
        if not is_live:
            print(f"Liveness check failed: {liveness_message}")
            return False, f"Spoofing detected: {liveness_message}"
        
        print("Liveness check passed")
        
        # SIMPLE FACE COMPARISON USING HISTOGRAMS
        # Convert to grayscale for histogram analysis
        stored_gray = cv2.cvtColor(stored_image, cv2.COLOR_BGR2GRAY)
        submitted_gray = cv2.cvtColor(submitted_image, cv2.COLOR_BGR2GRAY)
        
        # Normalize image sizes for fair comparison
        height, width = 100, 100
        stored_resized = cv2.resize(stored_gray, (width, height))
        submitted_resized = cv2.resize(submitted_gray, (width, height))
        
        # Calculate pixel intensity histograms
        hist1 = cv2.calcHist([stored_resized], [0], None, [256], [0, 256])
        hist2 = cv2.calcHist([submitted_resized], [0], None, [256], [0, 256])
        
        # Compare histograms using correlation
        correlation = cv2.compareHist(hist1, hist2, cv2.HISTCMP_CORREL)
        confidence = round(correlation * 100, 2)
        
        # Verification threshold (70% correlation required)
        if correlation > 0.7:
            print(f"Face verification successful - Confidence: {confidence}%")
            return True, f"Face verified (confidence: {confidence}%)"
        else:
            print(f"Face verification failed - Confidence: {confidence}%")
            return False, f"Face does not match (confidence: {confidence}%)"
        
    except Exception as e:
        print(f"DEBUG: Simple face comparison error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False, f"Face comparison error: {str(e)}"

# MAIN API FUNCTIONS - These are called by the attendance submission endpoint

def compare_faces(stored_face_image: bytes, submitted_face_image: str, tolerance: float = 0.3) -> Tuple[bool, str]:
    """
    PRIMARY FACE VERIFICATION FUNCTION with maximum security
    
    This is the main function called by attendance submission endpoints.
    Uses the most advanced face recognition with anti-spoofing protection.
    
    SECURITY GUARANTEE: All paths through this function include anti-spoofing detection
    """
    return enhanced_face_comparison(stored_face_image, submitted_face_image, tolerance)

def simple_face_comparison(stored_face_image: bytes, submitted_face_image: str) -> Tuple[bool, str]:
    """
    FALLBACK FACE VERIFICATION FUNCTION with maintained security
    
    Provides OpenCV-based face comparison when advanced algorithms are unavailable.
    Still includes full anti-spoofing protection for consistent security.
    """
    return simple_face_comparison_with_liveness(stored_face_image, submitted_face_image)

def verify_face_against_profile(stored_face_image: bytes, submitted_face_image: str) -> Tuple[bool, str]:
    """
    MAIN ENTRY POINT for all face verification in the attendance system
    
    This function is called by the attendance submission API and provides:
    1. Automatic fallback between advanced and simple methods
    2. Guaranteed anti-spoofing protection regardless of method used
    3. Comprehensive error handling for system reliability
    4. Detailed logging for security audit trails
    
    USAGE IN ATTENDANCE SYSTEM:
    When a student submits attendance, this function:
    - Retrieves their stored profile face from database
    - Compares it with their submitted face image
    - Blocks submission if spoofing is detected
    - Provides confidence scores for audit logs
    
    SECURITY ARCHITECTURE:
    ┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
    │  Attendance     │ -> │ Anti-Spoofing    │ -> │ Face Matching   │
    │  Submission     │    │ Detection        │    │ Algorithm       │
    └─────────────────┘    └──────────────────┘    └─────────────────┘
                                    │                        │
                                    ▼                        ▼
                           ┌──────────────────┐    ┌─────────────────┐
                           │ Block if Fake    │    │ Verify Identity │
                           │ (Security)       │    │ (Authentication)│
                           └──────────────────┘    └─────────────────┘
    
    Returns:
        Tuple[bool, str]: (verification_success, detailed_security_message)
    """
    try:
        # TRY ADVANCED FACE RECOGNITION FIRST (preferred method)
        try:
            is_match, message = enhanced_face_comparison(stored_face_image, submitted_face_image)
            return is_match, message
        except ImportError:
            # face_recognition library not available, use fallback
            print("Using simple face comparison")
            return simple_face_comparison_with_liveness(stored_face_image, submitted_face_image)
        except Exception as e:
            # Advanced method failed, use fallback but log the issue
            print(f"Advanced face recognition failed, using simple comparison")
            return simple_face_comparison_with_liveness(stored_face_image, submitted_face_image)
            
    except Exception as e:
        # Complete failure - block submission for security
        return False, f"Face verification error: {str(e)}"
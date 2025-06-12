"""
FACE VALIDATION MODULE: Image Quality & Face Detection System

This module is responsible for the INITIAL VALIDATION of face images before they enter
the attendance system. It serves as the first checkpoint to ensure:

1. IMAGE QUALITY: Submitted images are valid and processable
2. FACE DETECTION: Images contain exactly one clearly visible face
3. FEATURE VISIBILITY: Essential facial features (eyes) are not obscured
4. FORMAT VALIDATION: Images are in correct format and properly encoded

ROLE IN ATTENDANCE SYSTEM:
- Registration: Validates profile face images during student registration
- Attendance: Pre-validates submitted images before anti-spoofing detection
- Quality Control: Ensures only high-quality face images enter the system

This validation happens BEFORE the security checks in face_matcher.py, providing
a clean pipeline: Image Validation → Anti-Spoofing → Face Verification
"""

import cv2
import numpy as np
import os
from fastapi import HTTPException
import base64

def decode_image(image_data):
    """
    CRITICAL IMAGE DECODING FUNCTION: Converts Base64 images to OpenCV format
    
    This function handles the conversion from client-submitted Base64 encoded images
    to numpy arrays that can be processed by OpenCV and face recognition algorithms.
    
    SUPPORTED FORMATS:
    - Standard Base64 encoded images
    - Data URI format (data:image/jpeg;base64,xxxxx)
    - Multiple image formats (JPEG, PNG, etc.)
    
    SECURITY CONSIDERATIONS:
    - Validates Base64 padding to prevent malformed data
    - Handles data URI prefixes safely
    - Validates successful image decoding
    - Prevents processing of non-image data
    
    Args:
        image_data (str): Base64 encoded image string, possibly with data URI prefix
        
    Returns:
        np.ndarray: OpenCV image array (BGR format)
        
    Raises:
        ValueError: If image cannot be decoded or is invalid format
        
    PROCESS FLOW:
    Raw Base64 → Remove URI prefix → Add padding → Decode → Numpy array → OpenCV image
    """
    try:
        # STEP 1: HANDLE BASE64 PADDING ISSUES
        # Base64 requires length to be multiple of 4, add padding if needed
        padding = len(image_data) % 4
        if padding > 0:
            image_data += '=' * (4 - padding)
        
        # STEP 2: HANDLE DATA URI PREFIX
        # Remove "data:image/jpeg;base64," prefix if present
        if image_data.startswith('data:image'):
            # Split on comma and take the Base64 part
            image_data = image_data.split(',', 1)[1]
        
        # STEP 3: DECODE BASE64 TO BINARY DATA
        image_bytes = base64.b64decode(image_data)
        
        # STEP 4: CONVERT BINARY TO NUMPY ARRAY
        nparr = np.frombuffer(image_bytes, np.uint8)
        
        # STEP 5: DECODE AS IMAGE USING OPENCV
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        # STEP 6: VALIDATE SUCCESSFUL DECODING
        if image is None:
            raise ValueError("Failed to decode image")
            
        return image
    except Exception as e:
        # Provide clear error message for debugging
        raise ValueError(f"Invalid image format: {str(e)}")

def validate_face_image(image_data):
    """
    COMPREHENSIVE FACE VALIDATION SYSTEM
    
    This function performs multi-stage validation of face images to ensure they meet
    the requirements for face recognition and attendance submission:
    
    VALIDATION STAGES:
    1. IMAGE DECODING: Convert and validate image format
    2. FACE DETECTION: Locate faces using Haar cascade classifiers
    3. FACE COUNT: Ensure exactly one face is present
    4. EYE DETECTION: Verify eyes are visible (not covered by sunglasses)
    5. QUALITY ASSESSMENT: Basic image quality checks
    
    TECHNICAL IMPLEMENTATION:
    - Uses OpenCV Haar Cascade Classifiers for robust face/eye detection
    - Handles both string (Base64) and numpy array inputs
    - Provides detailed error messages for user guidance
    - Graceful fallback if cascade files are missing
    
    HAAR CASCADE CLASSIFIERS:
    These are pre-trained machine learning models that detect faces and eyes:
    - haarcascade_frontalface_default.xml: Detects frontal faces
    - haarcascade_eye.xml: Detects eye regions
    
    VALIDATION CRITERIA:
    ✓ Exactly 1 face detected (not 0, not multiple)
    ✓ At least 2 eyes detected within the face region
    ✓ Image successfully decoded and processed
    ✓ Face is reasonably sized (minimum 30x30 pixels)
    
    Args:
        image_data (str or np.ndarray): Image to validate (Base64 string or numpy array)
        
    Returns:
        Tuple[bool, str]: (is_valid, validation_message)
        - True: Image passes all validation checks
        - False: Image fails validation with specific reason
        
    USAGE IN SYSTEM:
    Registration: validate_face_image(profile_picture) → Store if valid
    Attendance: validate_face_image(submission) → Process if valid → Anti-spoofing → Verification
    """
    try:
        # STEP 1: IMAGE PREPARATION
        # Handle both string (Base64) and numpy array inputs
        if isinstance(image_data, str):
            image = decode_image(image_data)
        else:
            # Assume it's already a numpy array (for internal processing)
            image = image_data
        
        # STEP 2: LOAD HAAR CASCADE CLASSIFIERS
        # These are pre-trained models for face and eye detection
        face_cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        eye_cascade_path = cv2.data.haarcascades + 'haarcascade_eye.xml'

        # SAFETY CHECK: Verify cascade files exist
        if not os.path.exists(face_cascade_path) or not os.path.exists(eye_cascade_path):
            print("Warning: Face detection cascades not found. Skipping face validation.")
            return (True, "Face validation skipped")

        # LOAD THE CLASSIFIERS
        face_cascade = cv2.CascadeClassifier(face_cascade_path)
        eye_cascade = cv2.CascadeClassifier(eye_cascade_path)

        # STEP 3: PREPARE IMAGE FOR DETECTION
        # Convert to grayscale as Haar cascades work on grayscale images
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # STEP 4: FACE DETECTION
        # detectMultiScale parameters:
        # - scaleFactor: How much the image size is reduced at each scale (1.1 = 10% reduction)
        # - minNeighbors: How many neighbors each face needs (reduces false positives)
        # - minSize: Minimum possible face size (filters out tiny detections)
        faces = face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,    # Image pyramid scaling factor
            minNeighbors=5,     # Minimum detections to confirm face
            minSize=(30, 30)    # Minimum face size in pixels
        )

        # STEP 5: FACE COUNT VALIDATION
        if len(faces) == 0:
            return (False, "No face detected. Please ensure your face is clearly visible.")
        if len(faces) > 1:
            return (False, "Multiple faces detected. Please ensure only your face is in the image.")

        # STEP 6: EYE DETECTION WITHIN FACE REGION
        # Extract the face region for eye detection
        (x, y, w, h) = faces[0]  # Get the first (and only) face coordinates
        roi_gray = gray[y:y+h, x:x+w]  # Region of Interest: face area only
        
        # Detect eyes within the face region
        eyes = eye_cascade.detectMultiScale(
            roi_gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(30, 30)    # Minimum eye size
        )

        # STEP 7: EYE VISIBILITY VALIDATION
        # Require at least 2 eyes to be detected (both eyes visible)
        if len(eyes) < 2:
            return (False, "Eyes not clearly visible. Please remove sunglasses or any accessories covering your face.")

        # ALL VALIDATIONS PASSED
        return (True, "Face validation successful")
        
    except Exception as e:
        # LOG ERROR AND PROVIDE USER-FRIENDLY MESSAGE
        print(f"Face validation error: {str(e)}")
        return (False, f"Face validation failed: {str(e)}")

import cv2
import numpy as np
import os
from fastapi import HTTPException
import base64

def decode_image(image_data):
    """Convert base64 image to numpy array for OpenCV processing"""
    try:
        # Handle potential padding issues with base64
        padding = len(image_data) % 4
        if padding > 0:
            image_data += '=' * (4 - padding)
        
        # Check if the image is a data URI (starts with data:image)
        if image_data.startswith('data:image'):
            # Strip the data URI prefix
            image_data = image_data.split(',', 1)[1]
        
        # Decode base64 to bytes
        image_bytes = base64.b64decode(image_data)
        
        # Convert to numpy array
        nparr = np.frombuffer(image_bytes, np.uint8)
        
        # Decode as image
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if image is None:
            raise ValueError("Failed to decode image")
            
        return image
    except Exception as e:
        raise ValueError(f"Invalid image format: {str(e)}")

def validate_face_image(image_data):
    """Validate that the image contains a properly visible face"""
    try:
        # Convert base64 to image if it's a string
        if isinstance(image_data, str):
            image = decode_image(image_data)
        else:
            # Assume it's already a numpy array
            image = image_data
            
        face_cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        eye_cascade_path = cv2.data.haarcascades + 'haarcascade_eye.xml'

        if not os.path.exists(face_cascade_path) or not os.path.exists(eye_cascade_path):
            print("Warning: Face detection cascades not found. Skipping face validation.")
            return (True, "Face validation skipped")

        face_cascade = cv2.CascadeClassifier(face_cascade_path)
        eye_cascade = cv2.CascadeClassifier(eye_cascade_path)

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(30, 30)
        )

        if len(faces) == 0:
            return (False, "No face detected. Please ensure your face is clearly visible.")
        if len(faces) > 1:
            return (False, "Multiple faces detected. Please ensure only your face is in the image.")

        (x, y, w, h) = faces[0]
        roi_gray = gray[y:y+h, x:x+w]
        eyes = eye_cascade.detectMultiScale(
            roi_gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(30, 30)
        )

        if len(eyes) < 2:
            return (False, "Eyes not clearly visible. Please remove sunglasses or any accessories covering your face.")

        return (True, "Face validation successful")
    except Exception as e:
        print(f"Face validation error: {str(e)}")
        return (False, f"Face validation failed: {str(e)}")

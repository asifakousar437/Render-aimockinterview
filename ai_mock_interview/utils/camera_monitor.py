import cv2
import base64
import numpy as np

def detect_faces(base64_image):
    try:
        img_data = base64.b64decode(base64_image.split(',')[1])
        np_arr = np.frombuffer(img_data, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Load face cascade with improved parameters
        face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )

        # Enhanced face detection with more strict parameters to reduce false positives
        faces1 = face_cascade.detectMultiScale(gray, 1.05, 6, minSize=(50, 50))
        faces2 = face_cascade.detectMultiScale(gray, 1.1, 8, minSize=(40, 40))
        
        # Combine results and remove duplicates
        all_faces = list(faces1) + list(faces2)
        
        # More strict non-maximum suppression to avoid duplicates
        unique_faces = []
        for face in all_faces:
            is_duplicate = False
            for unique_face in unique_faces:
                # Check if faces overlap significantly
                x1, y1, w1, h1 = face
                x2, y2, w2, h2 = unique_face
                
                # Calculate intersection
                x_overlap = max(0, min(x1 + w1, x2 + w2) - max(x1, x2))
                y_overlap = max(0, min(y1 + h1, y2 + h2) - max(y1, y2))
                
                # More strict overlap criteria (70% instead of 50%)
                if x_overlap > 0.7 * min(w1, w2) and y_overlap > 0.7 * min(h1, h2):
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                # Additional filter: only keep faces with reasonable aspect ratio and size
                x, y, w, h = face
                aspect_ratio = w / h
                if 0.7 <= aspect_ratio <= 1.4 and w >= 50 and h >= 50:
                    unique_faces.append(face)
        
        face_count = len(unique_faces)
        
        # Debug logging
        print(f"DEBUG: Face detection - Raw faces: {len(all_faces)}, Unique faces: {face_count}")
        
        return face_count

    except Exception as e:
        print(f"DEBUG: Face detection error: {e}")
        return 0
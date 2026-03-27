import cv2
import numpy as np
import base64
import json
from collections import deque

# Try to import optional dependencies
try:
    import sounddevice as sd
    SOUNDDEVICE_AVAILABLE = True
except ImportError:
    SOUNDDEVICE_AVAILABLE = False
    print("Warning: sounddevice not available, using simulated audio")

try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False
    print("Warning: YOLO not available, using basic detection")

try:
    from mediapipe.tasks import python
    from mediapipe.tasks.python import vision
    import mediapipe as mp
    MEDIAPIPE_AVAILABLE = True
except ImportError:
    MEDIAPIPE_AVAILABLE = False
    print("Warning: MediaPipe not available, using basic detection")

# ---------------- CONFIG ----------------

LIP_THRESHOLD = 3
SYNC_THRESHOLD = 0.2
MAX_HISTORY = 20

# ---------------- HISTORY ----------------

class LipSyncDetector:
    def __init__(self):
        self.audio_history = deque(maxlen=MAX_HISTORY)
        self.lip_history = deque(maxlen=MAX_HISTORY)
        self.noise_history = deque(maxlen=50)
        self.frame_count = 0
        self.person_count = 1
        self.lip_distance = 0
        self.audio_level = 0
        self.cheating_events = []
        
    def process_frame(self, frame_data):
        """Process frame data and return lip sync analysis"""
        try:
            # Decode base64 frame
            import io
            from PIL import Image
            
            image_data = base64.b64decode(frame_data.split(',')[1])
            image = Image.open(io.BytesIO(image_data))
            frame = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
            
            h, w, _ = frame.shape
            self.frame_count += 1
            
            # Simulate face detection (simplified)
            person_count = 1  # Default to 1 person
            lip_distance = 0
            
            # Basic lip detection simulation (simplified)
            # In real implementation, this would use MediaPipe face landmarks
            if self.frame_count % 10 == 0:  # Process every 10th frame
                # Simulate lip movement detection
                lip_distance = np.random.uniform(0, 10)  # Simulated lip movement
            
            # Simulate audio level (simplified)
            # In real implementation, this would come from actual microphone
            audio_level = np.random.uniform(0, 0.1) if self.frame_count % 5 == 0 else self.audio_level
            
            self.person_count = person_count
            self.lip_distance = lip_distance
            self.audio_level = audio_level
            
            # Process audio and lip history
            self.audio_history.append(audio_level)
            self.lip_history.append(lip_distance)
            
            # Calculate sync
            audio_active = audio_level > 0.02
            lip_active = lip_distance > LIP_THRESHOLD
            
            # Calculate similarity
            similarity = 1.0
            if len(self.audio_history) > 0 and len(self.lip_history) > 0:
                audio_vec = np.array(list(self.audio_history))
                lip_vec = np.array(list(self.lip_history))
                
                if np.linalg.norm(audio_vec) > 0 and np.linalg.norm(lip_vec) > 0:
                    audio_norm = audio_vec / (np.linalg.norm(audio_vec) + 1e-6)
                    lip_norm = lip_vec / (np.linalg.norm(lip_vec) + 1e-6)
                    similarity = np.dot(audio_norm, lip_norm)
            
            # Detect cheating (simplified logic)
            cheating = False
            if person_count > 1:
                cheating = True
            elif audio_active and not lip_active:
                cheating = True
            elif lip_active and not audio_active:
                cheating = True
            elif audio_active and lip_active and similarity < SYNC_THRESHOLD:
                cheating = True
            
            if cheating:
                self.cheating_events.append({
                    'timestamp': self.frame_count,
                    'type': 'lip_sync_mismatch',
                    'similarity': similarity,
                    'audio_level': audio_level,
                    'lip_distance': lip_distance
                })
            
            # Generate FFT data for graph (simplified)
            fft_data = np.random.random(50) * 255  # Simulated FFT data
            
            return {
                'cheating': cheating,
                'similarity': similarity,
                'audio_level': audio_level,
                'lip_distance': lip_distance,
                'person_count': person_count,
                'fft_data': fft_data.tolist(),
                'lip_active': lip_active,
                'audio_active': audio_active
            }
            
        except Exception as e:
            print(f"Lip sync detection error: {e}")
            return {
                'cheating': False,
                'similarity': 1.0,
                'audio_level': 0,
                'lip_distance': 0,
                'person_count': 1,
                'fft_data': [0]*50,
                'lip_active': False,
                'audio_active': False
            }
    
    def get_realism_score(self):
        """Calculate overall realism score based on lip sync consistency"""
        if not self.cheating_events:
            return 100
        
        total_events = len(self.cheating_events)
        cheating_events = len([e for e in self.cheating_events if e['type'] == 'lip_sync_mismatch'])
        
        if total_events == 0:
            return 100
        
        # Higher score = fewer cheating events
        realism_score = max(0, 100 - (cheating_events / total_events * 100))
        return round(realism_score, 2)

# Global instance
lip_sync_detector = LipSyncDetector()

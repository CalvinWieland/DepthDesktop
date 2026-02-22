import math
import cv2
import numpy as np
import time
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from typing import Tuple, Union

# lists of indices of each individual eye point
PUPIL_CENTERS = [468, 473]
BRIDGE_NOSE = [168]
IRIS_OUTLINES = [469, 470, 471, 472, 474, 475, 476, 477]

# AI generated: normalize values to pixel coordinates
def _normalized_to_pixel_coordinates(
    normalized_x: float, normalized_y: float, image_width: int,
    image_height: int) -> Union[None, Tuple[int, int]]:
    def is_valid_normalized_value(value: float) -> bool:
        return (value > 0 or math.isclose(0, value)) and (value < 1 or math.isclose(1, value))

    if not (is_valid_normalized_value(normalized_x) and is_valid_normalized_value(normalized_y)):
        return None
    x_px = min(math.floor(normalized_x * image_width), image_width - 1)
    y_px = min(math.floor(normalized_y * image_height), image_height - 1)
    return x_px, y_px

# shows the pupils (dots)
def visualize_pupils(image, detection_result) -> np.ndarray:
    annotated_image = image.copy()
    height, width, _ = image.shape

    if not detection_result.face_landmarks:
        return annotated_image
    
    for face_landmarks in detection_result.face_landmarks:
        for idx, landmark in enumerate(face_landmarks):
            if idx in PUPIL_CENTERS:
                keypoint_px = _normalized_to_pixel_coordinates(landmark.x, landmark.y, width, height)
                if keypoint_px:
                    cv2.circle(annotated_image, keypoint_px, 3, (0, 0, 255), -1)
            elif idx in IRIS_OUTLINES:
                keypoint_px = _normalized_to_pixel_coordinates(landmark.x, landmark.y, width, height)
                if keypoint_px:
                    cv2.circle(annotated_image, keypoint_px, 1, (0, 255, 0), -1)

    return annotated_image

# run the program
if __name__ == '__main__':
    MODEL_FILE = 'face_landmarker_v2_with_blendshapes.task'

    print("Initializing Depth Tracker...")
    
    base_options = python.BaseOptions(model_asset_path=MODEL_FILE)
    options = vision.FaceLandmarkerOptions(
        base_options=base_options,
        running_mode=vision.RunningMode.VIDEO,
        num_faces=1,
        min_face_detection_confidence=0.5,
        min_face_presence_confidence=0.5,
        min_tracking_confidence=0.5
    )
    landmarker = vision.FaceLandmarker.create_from_options(options)

    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("Error: Could not open webcam.")
        exit()

    print("Webcam opened! Estimating depth... Press 'q' to quit.")
    start_time = time.time()

    last_mid = (0,0)

    while True:
        ret, frame = cap.read()
        if not ret:
            break
            
        frame = cv2.flip(frame, 1)
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

        frame_timestamp_ms = int((time.time() - start_time) * 1000)
        detection_result = landmarker.detect_for_video(mp_image, frame_timestamp_ms)

        annotated_image = visualize_pupils(frame, detection_result)

        if detection_result.face_landmarks:
            face_landmarks = detection_result.face_landmarks[0]
            height, width, _ = frame.shape
            
            right_pupil = face_landmarks[468]
            left_pupil = face_landmarks[473]
            
            right_px = _normalized_to_pixel_coordinates(right_pupil.x, right_pupil.y, width, height)
            left_px = _normalized_to_pixel_coordinates(left_pupil.x, left_pupil.y, width, height)

            if right_px and left_px:
                # get pixel distance between pupils
                pixel_distance = math.hypot(left_px[0] - right_px[0], left_px[1] - right_px[1])
                
                if pixel_distance > 0:
                    # find "raw distance", which is the distance between user and camera before adjust for angles
                    raw_distance = 327 / pixel_distance

                    # find the midpoint between the two pupils
                    mid_x = int((left_px[0] + right_px[0]) / 2)
                    mid_y = int((left_px[1] + right_px[1]) / 2)
                    mid_px = (mid_x, mid_y)

                    if (last_mid[0] - mid_px[0] > 15):
                        cv2.putText(annotated_image, f"Going left", 
                            (30, 220), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                        
                    if (last_mid[0] - mid_px[0] < -15):
                        cv2.putText(annotated_image, f"Going right", 
                            (30, 240), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                    
                    cv2.circle(annotated_image, mid_px, 3, (0, 0, 255), -1)

                    # get angle
                    angleX = (35 - ((mid_x / width) * 70))
                    angleY = (22 - ((mid_y / height) * 44))

                    # degrees to rads
                    rad_x = math.radians(angleX)
                    rad_y = math.radians(angleY)

                    # get the real z depth by taking the distance and arc cosining it with x and y angles
                    corrected_z_depth = raw_distance / (math.cos(rad_x) * math.cos(rad_y))

                    # get the x, y, z depth
                    real_x = -1 * corrected_z_depth * math.tan(rad_x)
                    real_y = corrected_z_depth * math.tan(rad_y)
                    real_z = corrected_z_depth

                    # display data
                    cv2.putText(annotated_image, f"True Depth (Z): {real_z:.2f} ft", 
                                (30, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                    cv2.putText(annotated_image, f"Left/Right (X): {real_x:.2f} ft", 
                                (30, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
                    cv2.putText(annotated_image, f"Up/Down (Y): {-real_y:.2f} ft",
                                (30, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
                    cv2.putText(annotated_image, f"Angle X: {angleX:.1f} deg", 
                                (30, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
                    cv2.putText(annotated_image, f"Raw Dist: {raw_distance:.2f} ft", 
                                (30, 180), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                    
                    last_mid = mid_px
                    
        cv2.imshow('MediaPipe Depth Tracker', annotated_image)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    landmarker.close()
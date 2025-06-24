import time
import cv2
import numpy as np
import tensorflow as tf
from keras_facenet import FaceNet

from business.services import log_service
from business.services import student_service  # ADDED for student details
from config import HAAR_CASCADE
from database.database import find_closest_student

# Assuming embedder and get_embedding_from_crop are defined in this file or correctly imported
embedder = FaceNet()


def get_embedding_from_crop(face_rgb: np.ndarray):  # Definition from original post
    try:
        # If we have a GPU and TF is configured for it:
        with tf.device('/gpu:0'):
            detections = embedder.extract(face_rgb, threshold=0.85)
            if not detections:
                return None
            return detections[0]['embedding'].tolist()
    except RuntimeError as e:
        print(f"RuntimeError during embedding extraction: {e}")
        # Fallback to CPU or handle error
        try:
            print("Falling back to CPU for embedding extraction.")
            detections = embedder.extract(face_rgb, threshold=0.85)  # Try without tf.device context
            if not detections:
                return None
            return detections[0]['embedding'].tolist()
        except Exception as ex_cpu:
            print(f"Error during CPU fallback for embedding: {ex_cpu}")
            return None
    except Exception as e_gen:  # Catch other potential errors
        print(f"General error during embedding extraction: {e_gen}")
        return None


INTEGRATED_WEBCAM = 0
EXTERNAL_WEBCAM = 1
EMBED_EVERY_N_FRAMES = 15


def generate_processed_frames():
    cap = cv2.VideoCapture(INTEGRATED_WEBCAM, cv2.CAP_DSHOW)
    if not cap.isOpened():
        log_service.record_event("VideoService: Failed to open webcam.", "VideoService")
        print("VideoService: Failed to open webcam.")
        return  # Exit if camera cannot be opened

    face_cascade = cv2.CascadeClassifier(HAAR_CASCADE)
    if face_cascade.empty():
        log_service.record_event("VideoService: Failed to load Haar Cascade.", "VideoService")
        print("VideoService: Failed to load Haar Cascade for face detection.")
        cap.release()
        return  # Exit if cascade cannot be loaded

    frame_count = 0
    last_boxes = []
    last_labels = []
    last_colors = []
    prev_time = time.time()

    while True:
        success, frame = cap.read()
        if not success:
            log_service.record_event("VideoService: Failed to read frame from webcam.", "VideoService")
            break

        frame_count += 1
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Only perform detection if it's time or if there are no previous boxes
        if frame_count % EMBED_EVERY_N_FRAMES == 0 or not last_boxes:
            boxes = face_cascade.detectMultiScale(gray, 1.3, 5)

            if boxes is not None and len(boxes) > 0:  # Check if boxes is not None
                new_labels = []
                new_colors = []
                current_boxes_for_drawing = []  # Store boxes corresponding to new_labels/colors

                crops = []
                box_coords_for_crops = []  # Store (x,y,w,h) for each crop
                for (x, y, w, h) in boxes:
                    face_bgr = frame[y:y + h, x:x + w]
                    face_rgb = cv2.cvtColor(face_bgr, cv2.COLOR_BGR2RGB)
                    crops.append(face_rgb)
                    box_coords_for_crops.append((x, y, w, h))

                embs = [get_embedding_from_crop(c) for c in crops]

                for i, emb in enumerate(embs):
                    current_box = box_coords_for_crops[i]  # Get the box for this embedding
                    current_boxes_for_drawing.append(current_box)

                    if emb is None:
                        new_labels.append("NoFace")
                        new_colors.append((0, 0, 255))  # Red for no face in crop
                        log_service.record_event("No face in crop for embedding", "VideoService") # This might be too verbose
                        continue

                    matches = find_closest_student(emb, k=1)
                    if matches and matches[0]["distance"] < 0.7:
                        sid = matches[0]["student_id"]
                        dist = matches[0]["distance"]

                        student_details = student_service.get_student_by_id(sid)
                        if student_details:
                            middle_name_str = student_details.get('middle_name') or ''
                            full_name = f"{student_details['first_name']} {middle_name_str} {student_details['last_name']}".replace(
                                '  ', ' ').strip()
                            lbl = f"{full_name} ({dist:.2f})"
                            col = (0, 255, 0)  # Green for recognized
                            log_msg = f"Recognized student {full_name} ({sid})"
                            log_service.record_event(log_msg, "VideoService", student_id=sid)
                        else:
                            lbl = f"Unknown Student ({sid}) ({dist:.2f})"  # ID matched, but no student record
                            col = (0, 165, 255)  # Orange for recognized ID but missing DB record
                            log_msg = f"Recognized student ID {sid} but no matching student record found."
                            # Log without student_id FK if student record is missing to avoid FK violation
                            log_service.record_event(log_msg, "VideoService")
                    else:
                        lbl = "Unknown Face"
                        col = (0, 0, 255)  # Red for unknown
                        log_service.record_event("Unknown face detected (no match or distance too high)",
                                                 "VideoService")

                    new_labels.append(lbl)
                    new_colors.append(col)

                # Update caches if new detections were processed
                if new_labels:  # only update if we processed new_labels
                    last_boxes = current_boxes_for_drawing  # Use boxes that correspond to labels
                    last_labels = new_labels
                    last_colors = new_colors
            elif frame_count % EMBED_EVERY_N_FRAMES == 0:  # No faces detected on Nth frame
                last_boxes = []  # Clear last known boxes if no faces are detected now
                last_labels = []
                last_colors = []

        # Draw boxes, labels, and colors from the cache
        for i, box in enumerate(last_boxes):  # Iterate using index
            if i < len(last_labels) and i < len(last_colors):  # Ensure labels and colors exist for the box
                x, y, w, h = box
                lbl = last_labels[i]
                col = last_colors[i]
                cv2.rectangle(frame, (x, y), (x + w, y + h), col, 2)
                cv2.putText(frame, lbl, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, col, 2)  # Smaller font

        now = time.time()
        fps = 1.0 / max(now - prev_time, 1e-6)
        prev_time = now
        cv2.putText(frame, f"FPS: {fps:.1f}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255),
                    2)  # Adjusted position/size

        ret, buf = cv2.imencode('.jpg', frame)
        if not ret:
            continue
        yield buf.tobytes()

    cap.release()
import os
import cv2
import numpy as np
import time
import logging
from collections import deque
from datetime import timedelta
from django.utils import timezone
from django.db import transaction
from insightface.app import FaceAnalysis
from fer.fer import FER
from pgvector.django import CosineDistance
from core.constant import WINDOW_DURATION_AFTER_MINS
from core.models import Patient, Session, EmotionResult, Camera, Alert
from core.views.doctor_view import WINDOW_DURATION_BEFORE_MINS

# OPEN_CV WINDOWS FIX
os.environ["OPENCV_VIDEOIO_PRIORITY_MSMF"] = "0"


# LOGGER
logger = logging.getLogger("emotion_tracking")
logger.setLevel(logging.INFO)

if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("[%(asctime)s] %(levelname)s | %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)


# -------------------------
# CONFIG
# -------------------------
# How often FER runs per patient — lower = more samples per second bucket
# 0.2 means up to 5 FER readings per second, giving the aggregation real data
PROCESS_COOLDOWN = 0.2

BULK_FLUSH_SECONDS = 10
FACE_DISTANCE_THRESHOLD = 0.5

ALERT_WINDOW_SECONDS = 30  # must match largest window_seconds in ALERT_RULES
ALERT_COOLDOWN_SECONDS = 30 # min seconds between alerts for same patient

# Emotions considered negative for alert purposes
NEGATIVE_EMOTIONS = {"sad", "fear", "angry", "disgust"}

# (emotion_set, window_seconds, min_percentage, severity)
ALERT_RULES = [
    # sustained high-intensity fear or anger → CRITICAL
    ({"fear", "angry"},    30, 80.0, Alert.Severity.CRITICAL),
    # sustained high-intensity any negative → HIGH
    (NEGATIVE_EMOTIONS,    30, 80.0, Alert.Severity.HIGH),
    # sustained anger or disgust → MEDIUM
    ({"angry", "disgust"}, 30, 70.0, Alert.Severity.MEDIUM),
    # sustained sadness or fear → MEDIUM
    ({"sad", "fear"},      30, 70.0, Alert.Severity.MEDIUM),
    # early sadness or fear → LOW
    ({"sad", "fear"},      30, 50.0, Alert.Severity.LOW),
]


class EmotionTrackingService:
    def __init__(self, camera_index=0, show_window=True):
        self.cap = cv2.VideoCapture(camera_index)
        self.show_window = show_window

        # AI models
        self.app = FaceAnalysis(
            name='buffalo_s',
            allowed_modules=['detection', 'recognition']
        )
        self.app.prepare(ctx_id=-1, det_size=(320, 320))

        self.emotion_detector = FER(mtcnn=False)

        # DB objects
        self.camera_obj = Camera.objects.first()

        # runtime state
        self.last_processed = {}
        self.last_flush_time = time.time()

        self.second_buffer = {}
        self.batch_buffer = []

        # Persistent UI state — survives frames where emotion detection fails
        # key: patient.id -> {bbox, name, emotion, percentage}
        self.ui_state = {}

        # Sliding window of confirmed 1-sec results per patient
        # key: patient.id -> deque of {emotion, score, session}
        # Used to evaluate alert rules across recent seconds
        self.recent_results = {}

        # Cooldown per patient to avoid flooding duplicate alerts
        # key: patient.id -> last alert timestamp
        self.last_alert_time = {}
        

        logger.info("EmotionTrackingService initialized")

    # -------------------------
    # PATIENT MATCHING
    # -------------------------
    def match_patient(self, embedding):
        embedding = embedding / np.linalg.norm(embedding)

        result = (
            Patient.objects
            .annotate(distance=CosineDistance('face_embedding', embedding.tolist()))
            .order_by('distance')
            .first()
        )

        if result and result.distance < FACE_DISTANCE_THRESHOLD:
            return result

        return None

    # -------------------------
    # SESSION
    # -------------------------
    def get_active_session(self, patient):
        now = timezone.now()

        return (
            Session.objects
            .filter(
                patient=patient,
                status=Session.Status.SCHEDULED,
                end_time__isnull=True,
                start_time__gte=now - timedelta(minutes=WINDOW_DURATION_BEFORE_MINS),
                start_time__lte=now + timedelta(minutes=WINDOW_DURATION_AFTER_MINS),
            )
            .order_by('start_time')
            .first()
        )

    # -------------------------
    # EMOTION
    # Pass full frame so FER's internal detector works correctly.
    # -------------------------
    def detect_emotion(self, face_crop):
        results = self.emotion_detector.detect_emotions(face_crop)

        if not results:
            return None, None

        best_emotion = None
        best_percentage = 0.0

        for face_result in results:
            emotions = face_result["emotions"]
            emotion = max(emotions, key=emotions.get)
            percentage = emotions[emotion] * 100

            if percentage > best_percentage:
                best_emotion = emotion
                best_percentage = percentage

        return best_emotion, best_percentage

    # -------------------------
    # ALERT EVALUATION
    # Called after each confirmed 1-sec bucket is finalized.
    # Checks the sliding window of recent results against ALERT_RULES.
    # -------------------------
    def evaluate_alerts(self, patient_id, session):
        window = self.recent_results.get(patient_id)
        if not window:
            return

        # Alert cooldown — don't fire again too soon
        now = time.time()
        if now - self.last_alert_time.get(patient_id, 0) < ALERT_COOLDOWN_SECONDS:
            return

        # Evaluate rules from most severe to least — fire only the worst match
        for emotion_set, window_seconds, min_percentage, severity in ALERT_RULES:
            if len(window) < window_seconds:
                continue

            recent = list(window)[-window_seconds:]

            # Count how many seconds had a matching dominant emotion
            matching = sum(1 for r in recent if r["emotion"] in emotion_set)
            percentage = (matching / window_seconds) * 100

            if percentage < min_percentage:
                continue

            # Find the most frequent emotion in the matching seconds
            dominant = max(
                emotion_set,
                key=lambda e: sum(1 for r in recent if r["emotion"] == e)
            )
            avg_score = sum(r["score"] for r in recent if r["emotion"] in emotion_set) / matching

            message = (
                f"Patient {patient_id} showed {dominant} in "
                f"{matching}/{window_seconds} seconds ({percentage:.1f}%) "
                f"avg score {avg_score:.1f}%"
            )

            Alert.objects.create(
                session=session,
                message=message,
                severity=severity,
                status=Alert.Status.TRIGGERED,
                timestamp=timezone.now(),
            )

            self.last_alert_time[patient_id] = now

            logger.warning(
                f"ALERT [{severity.upper()}] | patient {patient_id} | {message}"
            )

            # Stop at first (most severe) matching rule
            break

    # -------------------------
    # FRAME PROCESSING
    # -------------------------
    def process_frame(self, frame):
        faces = self.app.get(frame)

        seen_ids = set()

        for face in faces:
            emb = face.embedding
            patient = self.match_patient(emb)

            if not patient:
                continue

            bbox = face.bbox.astype(int)
            h, w = frame.shape[:2]

            x1, y1, x2, y2 = bbox[0], bbox[1], bbox[2], bbox[3]

            # Add padding so FER's internal detector has context around the face
            pad = int((x2 - x1) * 0.3)  # 30% of face width
            x1 = max(0, x1 - pad)
            y1 = max(0, y1 - pad)
            x2 = min(w, x2 + pad)
            y2 = min(h, y2 + pad)

            face_crop = frame[y1:y2, x1:x2]

            if face_crop.size == 0:
                continue

      
            seen_ids.add(patient.id)

            # Always update bbox so the box tracks face movement every frame
            if patient.id in self.ui_state:
                self.ui_state[patient.id]["bbox"] = bbox
            else:
                self.ui_state[patient.id] = {
                    "bbox": bbox,
                    "name": f"ID:{patient.id}",
                    "emotion": "detecting...",
                    "percentage": 0.0,
                }

            now = time.time()

            # Cooldown gate — controls how many FER samples per second
            if now - self.last_processed.get(patient.id, 0) < PROCESS_COOLDOWN:
                continue

            self.last_processed[patient.id] = now

            session = self.get_active_session(patient)
            if not session:
                logger.info(f"No active session for patient {patient.id}")
                continue
                
            emotion, percentage = self.detect_emotion(face_crop)

            if emotion is None:
                logger.info(f"Emotion not detected for patient {patient.id}")
                continue

            # Update UI label with latest reading
            self.ui_state[patient.id].update({
                "emotion": emotion,
                "percentage": percentage,
            })

            # -------------------------
            # 1-second bucket aggregation
            # sec_key groups ALL readings that fall in the same wall-clock second.
            # With PROCESS_COOLDOWN=0.2 we get ~5 readings per bucket,
            # so the avg/dominant emotion is based on real data, not a single sample.
            # -------------------------
            sec_key = (patient.id, int(now))

            if sec_key not in self.second_buffer:
                self.second_buffer[sec_key] = {
                    "session": session,
                    "camera": self.camera_obj,
                    # count per emotion label this second: {emotion: {sum, count}}
                    "emotions": {},
                    # floored to second boundary for clean DB timestamps
                    "start_time": timezone.now().replace(microsecond=0),
                }

            bucket = self.second_buffer[sec_key]
            entry = bucket["emotions"].get(emotion, {"sum": 0.0, "count": 0})
            entry["sum"] += percentage
            entry["count"] += 1
            bucket["emotions"][emotion] = entry

            logger.debug(
                f"Patient {patient.id} | {emotion} {percentage:.1f}% "
                f"[bucket {sec_key[1]}: {bucket['emotions']}]"
            )

        # Remove patients who are no longer in frame
        for pid in set(self.ui_state.keys()) - seen_ids:
            del self.ui_state[pid]

    # -------------------------
    # FLUSH
    # -------------------------
    def flush_data(self):
        now = time.time()

        to_delete = []

        for (patient_id, sec), data in list(self.second_buffer.items()):
            # Only flush completed seconds (not the current one still being filled)
            if sec < int(now):
                emotions = data["emotions"]

                if emotions:
                    # Average score per emotion label across all readings in this second
                    avg_per_emotion = {
                        e: v["sum"] / v["count"]
                        for e, v in emotions.items()
                    }

                    # The dominant emotion = highest average score this second
                    dominant_emotion = max(avg_per_emotion, key=avg_per_emotion.get)
                    dominant_score = avg_per_emotion[dominant_emotion]

                    total_readings = sum(v["count"] for v in emotions.values())

                    self.batch_buffer.append(
                        EmotionResult(
                            session=data["session"],
                            camera=data["camera"],
                            emotion=dominant_emotion,
                            percentage=dominant_score,
                            # Clean 1-second window: 1:01.000000 → 1:02.000000
                            start_time=data["start_time"],
                            end_time=data["start_time"] + timedelta(seconds=1),
                        )
                    )

                    logger.info(
                        f"1-sec bucket | patient {patient_id} | "
                        f"{dominant_emotion} {dominant_score:.1f}% "
                        f"(from {total_readings} readings: {avg_per_emotion})"
                    )

                    # -------------------------
                    # Update sliding window and evaluate alerts
                    # -------------------------
                    if patient_id not in self.recent_results:
                        self.recent_results[patient_id] = deque(maxlen=ALERT_WINDOW_SECONDS)

                    self.recent_results[patient_id].append({
                        "emotion": dominant_emotion,
                        "score": dominant_score,
                        "session": data["session"],
                    })

                    # Evaluate alert rules against the updated window
                    self.evaluate_alerts(patient_id, data["session"])

                to_delete.append((patient_id, sec))

        for k in to_delete:
            self.second_buffer.pop(k, None)

        # -------------------------
        # BULK INSERT
        # -------------------------
        if len(self.batch_buffer) >= 10 or (now - self.last_flush_time >= BULK_FLUSH_SECONDS):
            if self.batch_buffer:
                try:
                    EmotionResult.objects.bulk_create(self.batch_buffer)
                    logger.info(f"BULK INSERT | {len(self.batch_buffer)} records")
                except Exception as e:
                    logger.error(f"DB INSERT ERROR: {e}")

                self.batch_buffer.clear()

            self.last_flush_time = now

    # -------------------------
    # START LOOP
    # -------------------------
    def start(self):
        if not self.cap.isOpened():
            raise RuntimeError("Camera not available")

        logger.info("Service started")

        cv2.namedWindow("Clinic System", cv2.WINDOW_NORMAL)

        while True:
            ret, frame = self.cap.read()

            if not ret:
                logger.warning("Camera frame not received")
                time.sleep(0.1)
                continue

            self.process_frame(frame)
            self.flush_data()

            # -------------------------
            # DRAW — always runs
            # -------------------------
            for item in self.ui_state.values():
                x1, y1, x2, y2 = item["bbox"]
                h, w = frame.shape[:2]
                x1, x2 = max(0, x1), min(w - 1, x2)
                y1, y2 = max(0, y1), min(h - 1, y2)

                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

                y_text = max(30, y1 - 10)

                cv2.putText(
                    frame,
                    item["name"],
                    (x1, y_text),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.65,
                    (0, 255, 0),
                    2,
                )

                cv2.putText(
                    frame,
                    f"{item['emotion']} {item['percentage']:.1f}%",
                    (x1, y_text + 22),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.65,
                    (0, 255, 255),
                    2,
                )

            if self.show_window:
                cv2.imshow("Clinic System", frame)

                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

        self.shutdown()

    # -------------------------
    # CLEANUP
    # -------------------------
    def shutdown(self):
        if self.batch_buffer:
            try:
                EmotionResult.objects.bulk_create(self.batch_buffer)
                logger.info(f"Final flush | {len(self.batch_buffer)} records")
            except Exception as e:
                logger.error(f"Final flush error: {e}")

        self.cap.release()
        cv2.destroyAllWindows()
        logger.info("Service stopped cleanly")
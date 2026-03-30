import cv2
from fer.fer import FER

emotion_detector = FER(mtcnn=True)
cap = cv2.VideoCapture(0)

while True:
    ret, frame = cap.read()
    if not ret:
        break

   
    emotions = emotion_detector.detect_emotions(frame)

    for face in emotions:
        (x, y, w, h) = face["box"]
        emotion, score = emotion_detector.top_emotion(frame)

        cv2.rectangle(frame, (x, y), (x+w, y+h), (0,255,0), 2)

        if emotion:
            cv2.putText(frame, emotion, (x, y-10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9,
                        (0,255,0), 2)

    cv2.imshow("Emotion Detection", frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
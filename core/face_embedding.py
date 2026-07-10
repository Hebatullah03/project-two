from insightface.app import FaceAnalysis
import numpy as np
import cv2


app = FaceAnalysis(
    name='buffalo_s',allowed_modules=['detection', 'recognition']
)

app.prepare(ctx_id=0, det_size=(320, 320))


def get_face_embedding(image_file):
    file_bytes = np.frombuffer(image_file.read(), np.uint8)
    img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)

    faces = app.get(img)

    if len(faces) == 0:
        return None

    embedding = faces[0].embedding
    return embedding.tolist()
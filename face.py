"""
Face authentication for JARVIS — streams the camera into the themed HTML auth
panel (via callbacks) instead of a raw OpenCV window. OpenCV LBPH, all local.
"""
import os, time, base64
import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
FACE_DIR = os.path.join(HERE, ".face")
MODEL = os.path.join(FACE_DIR, "owner.yml")
_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

def enrolled():
    return os.path.exists(MODEL)

def _faces(gray):
    return _cascade.detectMultiScale(gray, 1.2, 5, minSize=(120, 120))

def _dataurl(frame):
    ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 60])
    return ("data:image/jpeg;base64," + base64.b64encode(buf).decode("ascii")) if ok else None

def enroll(samples=35, on_frame=None, on_status=None):
    """Capture the owner's face, streaming frames to the panel. Train + save."""
    os.makedirs(FACE_DIR, exist_ok=True)
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        return False
    imgs, t0 = [], time.time()
    while len(imgs) < samples and time.time() - t0 < 45:
        ok, frame = cap.read()
        if not ok:
            continue
        frame = cv2.flip(frame, 1)
        small = cv2.resize(frame, (480, 360))
        sx, sy = 480 / frame.shape[1], 360 / frame.shape[0]
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        for (x, y, w, h) in _faces(gray):
            imgs.append(cv2.resize(gray[y:y+h, x:x+w], (200, 200)))
            cv2.rectangle(small, (int(x*sx), int(y*sy)), (int((x+w)*sx), int((y+h)*sy)), (255, 180, 40), 2)
            break
        if on_frame:  on_frame(_dataurl(small))
        if on_status: on_status(f"REGISTERING YOUR FACE  {len(imgs)}/{samples}", "scan")
        time.sleep(0.03)
    cap.release()
    if len(imgs) < 5:
        return False
    rec = cv2.face.LBPHFaceRecognizer_create()
    rec.train(imgs, np.array([0] * len(imgs)))
    rec.write(MODEL)
    return True

def recognize_loop(on_frame=None, on_status=None, threshold=72, max_seconds=180):
    """Stream the camera; return True when the owner appears, None if no camera."""
    if not enrolled():
        return None
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        return None
    rec = cv2.face.LBPHFaceRecognizer_create()
    rec.read(MODEL)
    t0 = time.time()
    while time.time() - t0 < max_seconds:
        ok, frame = cap.read()
        if not ok:
            continue
        frame = cv2.flip(frame, 1)
        small = cv2.resize(frame, (480, 360))
        sx, sy = 480 / frame.shape[1], 360 / frame.shape[0]
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = _faces(gray)
        owner = False
        for (x, y, w, h) in faces:
            label, conf = rec.predict(cv2.resize(gray[y:y+h, x:x+w], (200, 200)))
            ok_user = (label == 0 and conf < threshold)
            owner = owner or ok_user
            col = (90, 255, 130) if ok_user else (80, 80, 255)
            cv2.rectangle(small, (int(x*sx), int(y*sy)), (int((x+w)*sx), int((y+h)*sy)), col, 2)
        if on_frame:
            on_frame(_dataurl(small))
        if owner:
            if on_status: on_status("ACCESS GRANTED  -  WELCOME, SIR", "ok")
            time.sleep(0.9); cap.release(); return True
        if on_status:
            on_status("UNKNOWN FACE  -  ACCESS DENIED" if len(faces) else "AUTHENTICATING...  LOOK AT THE CAMERA",
                      "deny" if len(faces) else "scan")
        time.sleep(0.03)
    cap.release()
    return False

if __name__ == "__main__":
    print("Look at the camera to register your face…")
    print("Enrolled." if enroll(on_status=lambda t, s: print(t, end="\r")) else "\nFailed (camera permission?).")

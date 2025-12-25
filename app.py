import os
import csv
import uuid
import secrets
import numpy as np
import torch
import torch.nn.functional as F
from flask import Flask, render_template, request, redirect, url_for, flash, session
import serial
import time
from threading import Thread, Lock
import queue
from deepface import DeepFace
import cv2
from speechbrain.pretrained import EncoderClassifier
import torchaudio
from pydub import AudioSegment

app = Flask(__name__)
app.secret_key = "OMSK_N_USSR_CLASSIFIED_VOICE_V2"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_FILE = os.path.join(BASE_DIR, "operative_archives.csv")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "dossier_uploads")
FACE_DB_PATH = os.path.join(BASE_DIR, "enrolled_faces_img")
VOICE_DB_FILE = os.path.join(BASE_DIR, "voice_database.csv")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(FACE_DB_PATH, exist_ok=True)

VOICE_THRESHOLD = 0.80
EMBEDDING_DIM = 192
FACE_THRESSHOLD = 0.30
SERIAL_PORT = 'COM3'
BAUD_RATE = 9600
ser = None

try:
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=2)
    print(f"Attempting connection on {SERIAL_PORT}...")
    line = ser.readline().decode('utf-8').strip()
    if line == "READY":
        print(f"SUCCESS: Handshake complete. Sensor controller is online.")
    else:
        print(f"ERROR: Handshake failed. Received: '{line}'.")
        ser.close();
        ser = None
except serial.SerialException:
    print(f"ERROR: Could not open serial port '{SERIAL_PORT}'.")
    print("WARNING: Hardware functions disabled.")

arduino_responses = queue.Queue()
scan_lock = Lock()


def listen_to_sensor_controller():
    while True:
        if ser and ser.in_waiting > 0:
            try:
                response = ser.readline().decode('utf-8').strip()
                if response:
                    print(f"[SCI LOG] Received: '{response}'")
                    arduino_responses.put(response)
            except UnicodeDecodeError:
                pass
        time.sleep(0.1)


if ser:
    listener_thread = Thread(target=listen_to_sensor_controller, daemon=True)
    listener_thread.start()

print("Loading vocal recognition engram model...")
spk_model = EncoderClassifier.from_hparams("speechbrain/spkrec-ecapa-voxceleb")
print("Model loading complete. System is operational.")


def init_csv():
    if not os.path.exists(CSV_FILE) or os.path.getsize(CSV_FILE) == 0:
        with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["user_id", "fingerprint_hash", "display_name"])


def load_users():
    if not os.path.exists(CSV_FILE): return []
    with open(CSV_FILE, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def overwrite_users(users):
    with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["user_id", "fingerprint_hash", "display_name"])
        writer.writeheader()
        writer.writerows(users)


def append_user(user_id, fingerprint_hash, display_name):
    with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([user_id, fingerprint_hash, display_name])


def find_user_by_fingerprint_id(fingerprint_id):
    for user in load_users():
        if user.get("fingerprint_hash") == fingerprint_id: return user
    return None


def load_voice_database():
    db = {}
    if not os.path.exists(VOICE_DB_FILE): return db
    with open(VOICE_DB_FILE, mode='r', newline='', encoding='utf-8') as f:
        reader = csv.reader(f)
        try:
            next(reader)
        except StopIteration:
            return db
        for row in reader:
            if not row: continue
            user_id = row[0]
            embedding_values = [float(x) for x in row[1:EMBEDDING_DIM + 1]]
            db[user_id] = torch.tensor(embedding_values)
    return db


def save_voice_database(db):
    header = ['user_id'] + [f'emb_{i}' for i in range(EMBEDDING_DIM)]
    with open(VOICE_DB_FILE, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for user_id, embedding in db.items():
            embedding_list = embedding.cpu().numpy().tolist()
            writer.writerow([user_id] + embedding_list)


def get_voice_embedding(received_audio_path):
    temp_wav_path = os.path.join(UPLOAD_FOLDER, f"temp_{uuid.uuid4().hex}.wav")
    try:
        audio = AudioSegment.from_file(received_audio_path)
        audio.export(temp_wav_path, format="wav")
        signal, fs = torchaudio.load(temp_wav_path)
        with torch.no_grad():
            embedding = spk_model.encode_batch(signal)
            embedding = embedding.squeeze()
        return embedding
    except Exception as e:
        print(f"Error processing voice embedding: {e}")
        return None
    finally:
        if os.path.exists(temp_wav_path):
            os.remove(temp_wav_path)


def compare_embeddings(emb1, emb2):
    return F.cosine_similarity(emb1, emb2, dim=0).item()


@app.route("/")
def index():
    init_csv()
    return render_template("index.html", users_count=len(load_users()))


@app.route("/enroll", methods=["GET", "POST"])
def enroll_index():
    if request.method == "POST":
        session.clear()
        session['enroll_name'] = request.form.get("display_name", "").strip()
        return redirect(url_for("enroll_fp"))
    return render_template("enroll.html")


@app.route("/enroll/fp", methods=["GET", "POST"])
def enroll_fp():
    if "enroll_name" not in session: return redirect(url_for("enroll_index"))
    if request.method == "POST":
        if session.get('enroll_fp_hash'):
            return redirect(url_for("enroll_face"))
        else:
            flash("Biometric capture incomplete.", "danger")
    return render_template("enroll_fp.html", name=session.get("enroll_name"))


@app.route("/enroll/face", methods=["GET", "POST"])
def enroll_face():
    if "enroll_fp_hash" not in session: return redirect(url_for("enroll_fp"))
    if request.method == "POST":
        f = request.files.get("face")
        if not f: return {"status": "error", "message": "No image received."}
        temp_image_path = os.path.join(UPLOAD_FOLDER, f"{uuid.uuid4().hex}.jpg")
        f.save(temp_image_path)
        try:
            face_objs = DeepFace.extract_faces(img_path=temp_image_path, enforce_detection=True)
            cropped_face = (face_objs[0]['face'] * 255).astype('uint8')
            user_id = str(uuid.uuid4())
            session['enroll_user_id'] = user_id
            reference_image_path = os.path.join(FACE_DB_PATH, f"{user_id}.jpg")
            cv2.imwrite(reference_image_path, cv2.cvtColor(cropped_face, cv2.COLOR_RGB2BGR))
            os.remove(temp_image_path)
            token = secrets.token_hex(16)
            session['next_step_token'] = token
            session.modified = True
            return {"status": "success", "message": "Face recognized and processed.", "token": token}
        except ValueError:
            os.remove(temp_image_path)
            return {"status": "error", "message": "No face detected."}
        except Exception as e:
            os.remove(temp_image_path)
            print(f"Error: {e}")
            return {"status": "error", "message": "System error during analysis."}
    return render_template("enroll_face.html", name=session.get("enroll_name"))


@app.route("/enroll/voice", methods=["GET", "POST"])
def enroll_voice():
    if request.method == "GET":
        token = request.args.get('token')
        if not token or token != session.get('next_step_token'):
            flash("Unauthorized access to enrollment step.", "danger")
            return redirect(url_for('enroll_face'))
        session.pop('next_step_token', None)
        return render_template("enroll_voice.html", name=session.get("enroll_name"))
    if request.method == "POST":
        if "enroll_user_id" not in session:
            return {"status": "error", "message": "Session expired or invalid. Please restart enrollment."}
        files = request.files.getlist('voice_samples')
        if len(files) != 3:
            return {"status": "error", "message": "Expected 3 voice samples."}
        embeddings = []
        for f in files:
            fname = os.path.join(UPLOAD_FOLDER, f.filename)
            f.save(fname)
            emb = get_voice_embedding(fname)
            os.remove(fname)
            if emb is None or torch.isnan(emb).any():
                return {"status": "error", "message": "One of the voice samples was invalid. Please try again."}
            embeddings.append(emb)
        final_embedding = torch.mean(torch.stack(embeddings), dim=0)
        user_id = session.get('enroll_user_id')
        display_name = session.get("enroll_name", "")
        fingerprint_hash = session.get("enroll_fp_hash")
        voice_db = load_voice_database()
        voice_db[user_id] = final_embedding
        save_voice_database(voice_db)
        append_user(user_id, fingerprint_hash, display_name)
        session.clear()
        flash(f"Operative {display_name} successfully enrolled with all biometrics.", "success")
        return {"status": "success", "redirect_url": url_for('index')}


@app.route("/login/fingerprint", methods=["GET", "POST"])
def login_fp():
    if request.method == "GET":
        session.clear()
        return render_template("login_fp.html")
    if request.method == "POST":
        if session.get('login_fp_verified'):
            return redirect(url_for("login_face"))
        else:
            flash("Biometric verification was not completed or timed out.", "danger")
            return redirect(url_for("login_fp"))


@app.route("/login/face", methods=["GET", "POST"])
def login_face():
    if not session.get('login_fp_verified'): return redirect(url_for("login_fp"))
    if request.method == "POST":
        f = request.files.get("face")
        if not f: return {"status": "error", "message": "No image received."}

        candidate_temp_path = os.path.join(UPLOAD_FOLDER, f"{uuid.uuid4().hex}_login.jpg")
        f.save(candidate_temp_path)

        user_id = session.get('login_user_id')
        reference_image_path = os.path.join(FACE_DB_PATH, f"{user_id}.jpg")
        is_verified = False

        print("\n--- INITIATING 1:1 FACE VERIFICATION ---")
        print(f"  > REFERENCE: {reference_image_path}")
        print(f"  > CANDIDATE: {candidate_temp_path}")

        if os.path.exists(reference_image_path):
            try:
                
                result = DeepFace.verify(
                    img1_path=reference_image_path,
                    img2_path=candidate_temp_path,
                    enforce_detection=True
                )

                distance = result['distance']
                is_verified = distance <= FACE_THRESSHOLD

                print(
                    f"  > DeepFace Result: Verified={is_verified}, Distance={distance:.4f}, Threshold={FACE_THRESSHOLD:.2f}")

            except Exception as e:
                print(f"  > FAILURE: DeepFace processing error: {e}")

        os.remove(candidate_temp_path)
        print("--- VERIFICATION COMPLETE ---")

        if is_verified:
            session['face_verified'] = True
            token = secrets.token_hex(16)
            session['next_step_token'] = token
            session.modified = True
            return {"status": "success", "token": token}
        else:
            return {"status": "error", "message": "Face did not match dossier. Please retry."}

    return render_template("login_face.html", name=session.get('login_user_display_name'))


@app.route("/login/voice", methods=["GET", "POST"])
def login_voice():
    if request.method == "GET":
        token = request.args.get('token')
        if not token or token != session.get('next_step_token'):
            flash("Unauthorized access to verification step.", "danger")
            return redirect(url_for('login_face'))
        session.pop('next_step_token', None)
        return render_template("login_voice.html", name=session.get('login_user_display_name'))
    if request.method == "POST":
        if "login_user_id" not in session:
            return {"status": "error", "message": "Session expired. Please restart authentication."}
        f = request.files.get("voice")
        if not f: return {"status": "error", "message": "No voice sample received."}
        fname = os.path.join(UPLOAD_FOLDER, f.filename)
        f.save(fname)
        login_embedding = get_voice_embedding(fname)
        os.remove(fname)
        if login_embedding is None or torch.isnan(login_embedding).any():
            return {"status": "error", "message": "Could not process voice sample."}
        user_id = session.get('login_user_id')
        voice_db = load_voice_database()
        enrolled_embedding = voice_db.get(user_id)
        if enrolled_embedding is None:
            return {"status": "error", "message": "CRITICAL: No voice engram found for this operative."}
        score = compare_embeddings(enrolled_embedding, login_embedding)
        if score >= VOICE_THRESHOLD:
            user = find_user_by_fingerprint_id(session['login_user_fingerprint_hash'])
            session['user_id'] = user['user_id']
            session['display_name'] = user['display_name']
            flash(f"All-factor authentication successful. Welcome, {user['display_name']}.", "success")
            return {"status": "success", "redirect_url": url_for('nuclear')}
        else:
            session.clear()
            flash("Authentication failed: Vocal signature mismatch. Access denied.", "danger")
            return {"status": "error", "message": f"Vocal signature mismatch. Score: {score:.2f}",
                    "redirect_url": url_for('login_fp')}


@app.route("/nuclear")
def nuclear():
    if "user_id" not in session:
        flash("Authentication required.", "warning")
        return redirect(url_for("index"))
    return render_template("nuclear.html", name=session.get("display_name"))


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been securely logged out.", "info")
    return redirect(url_for("index"))


@app.route("/manage")
def manage_users():
    if "user_id" not in session:
        flash("Authentication required to access management console.", "warning")
        return redirect(url_for("index"))
    all_users = load_users()
    return render_template("manage_users.html", users=all_users)


@app.route("/delete_user/<user_id>", methods=["POST"])
def delete_user(user_id):
    if "user_id" not in session: return redirect(url_for("index"))
    all_users = load_users()
    user_to_delete = next((user for user in all_users if user['user_id'] == user_id), None)
    if not user_to_delete:
        flash("Operative not found.", "danger")
        return redirect(url_for("manage_users"))
    if ser:
        fp_hash = user_to_delete.get("fingerprint_hash", "")
        if fp_hash.startswith("AS608_ID_"):
            fp_id = fp_hash.split('_')[-1]
            ser.write(f"DELETE_FINGER:{fp_id}\n".encode('utf-8'))
    try:
        os.remove(os.path.join(FACE_DB_PATH, f"{user_id}.jpg"))
    except FileNotFoundError:
        pass
    voice_db = load_voice_database()
    if user_id in voice_db:
        del voice_db[user_id]
        save_voice_database(voice_db)
    remaining_users = [user for user in all_users if user['user_id'] != user_id]
    overwrite_users(remaining_users)
    flash(f"Operative {user_to_delete['display_name']} has been purged from all archives.", "success")
    return redirect(url_for("manage_users"))


@app.route("/cleanup_orphans", methods=["POST"])
def cleanup_orphans():
    if "user_id" not in session or not ser: return redirect(url_for("manage_users"))
    registered_hashes = {user['fingerprint_hash'] for user in load_users()}
    ser.write(b"LIST_FINGERS\n")
    sensor_ids = set()
    try:
        while True:
            response = arduino_responses.get(timeout=3)
            if response.startswith("FINGER_ID:"):
                sensor_ids.add(int(response.split(':')[1]))
            elif response == "LIST_COMPLETE":
                break
    except queue.Empty:
        flash("Did not receive a complete list from the sensor.", "danger")
        return redirect(url_for("manage_users"))
    registered_ids = {int(h.split('_')[-1]) for h in registered_hashes if h.startswith("AS608_ID_")}
    orphan_ids = sensor_ids - registered_ids
    if not orphan_ids:
        flash("No orphan signatures found. Sensor is clean.", "info")
        return redirect(url_for("manage_users"))
    for orphan_id in orphan_ids:
        ser.write(f"DELETE_FINGER:{orphan_id}\n".encode('utf-8'))
        time.sleep(0.1)
    flash(f"Successfully purged {len(orphan_ids)} orphan signature(s) from the sensor.", "success")
    return redirect(url_for("manage_users"))


@app.route("/start_scan/<mode>")
def start_scan(mode):
    if not ser: return {"status": "error", "message": "Sensor controller is offline."}
    if not scan_lock.acquire(blocking=False): return {"status": "error", "message": "Another scan is in progress."}
    while not arduino_responses.empty(): arduino_responses.get()
    ser.write((mode.upper() + '\n').encode('utf-8'))
    session['scan_mode'] = mode
    return {"status": "initiated"}


@app.route("/check_scan_status")
def check_scan_status():
    if not scan_lock.locked(): return {"status": "idle"}
    try:
        response = arduino_responses.get_nowait()
        if "SUCCESS_ENROLL" in response:
            fp_id = response.split(':')[1]
            session['enroll_fp_hash'] = f"AS608_ID_{fp_id}"
            scan_lock.release()
            return {"status": "success", "message": f"Signature captured (ID: {fp_id})"}
        elif "SUCCESS_LOGIN" in response:
            fp_id = response.split(':')[1]
            fp_hash = f"AS608_ID_{fp_id}"
            user = find_user_by_fingerprint_id(fp_hash)
            if user:
                session['login_fp_verified'] = True
                session['login_user_id'] = user['user_id']
                session['login_user_display_name'] = user['display_name']
                session['login_user_fingerprint_hash'] = fp_hash
                scan_lock.release()
                return {"status": "success", "message": f"Identity confirmed: {user['display_name']}"}
            else:
                scan_lock.release()
                return {"status": "error", "message": "Signature not in archives."}
        elif "ERROR" in response:
            error_message = response.split(':')[1]
            scan_lock.release()
            return {"status": "error", "message": f"Sensor Error: {error_message}"}
        else:
            return {"status": "pending", "message": response}
    except queue.Empty:
        return {"status": "pending", "message": "Awaiting sensor response..."}


if __name__ == "__main__":
    init_csv()
    app.run(debug=True, port=5000, use_reloader=False)
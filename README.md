# OMSK Multi-Factor Biometric Authentication System

A role-play themed, three-factor biometric authentication system using fingerprint, face, and voice recognition, built with Flask and integrated with Arduino hardware.

## ✨ Features

*   **Three-Factor Authentication:** A sequential security protocol requiring operatives to verify their identity via:
    1.  **Fingerprint:** Hardware-based verification using an AS608 optical sensor.
    2.  **Face:** Live 1-to-1 facial verification using a webcam.
    3.  **Voice:** Live speaker verification using a microphone.
*   **Live Biometric Capture:** Utilizes modern browser APIs (`MediaStream`, `MediaRecorder`) to capture face and voice data directly from the client, requiring no pre-existing files.
*   **Hardware Integration:** Communicates with an Arduino Mega controller via a robust serial handshake protocol to manage the fingerprint sensor.
*   **Role-Play Themed Interface:** A stylized "OMSK Great Trial" interface, including an interactive strategic launch console with animations and sound effects, accessible only after successful authentication.
*   **Operative Management:** A secure console for viewing all enrolled operatives, purging individual records (from all databases and hardware), and cleaning up "orphan" fingerprints from the sensor's memory.
*   **Standalone Purge Utility:** A command-line script to perform a full factory reset of all biometric and user data for a clean system state.

---

## ⚙️ System Architecture

The application is built on a client-server architecture, orchestrating communication between the web frontend, the Python backend, and the physical hardware controller.

1.  **Frontend (Flask Templates & JS):** Renders the user interface and captures live biometric data from the operative's webcam and microphone.
2.  **Backend (Flask `app.py`):** Acts as the central command. It serves the web pages, manages user sessions, and controls the authentication workflow. It receives biometric data from the frontend and uses specialized libraries for analysis.
3.  **Hardware Module (Arduino & AS608):** The Flask backend communicates via a serial (USB) connection to the Arduino. The Arduino sketch translates high-level commands (e.g., `ENROLL`, `LOGIN`) into low-level operations for the AS608 sensor, which stores and matches fingerprint templates.
4.  **Software Modules (DeepFace & SpeechBrain):** The backend uses these powerful Python libraries to perform complex biometric analysis:
    *   **DeepFace:** For 1-to-1 facial verification between a live image and a stored reference image.
    *   **SpeechBrain:** To convert live audio into voiceprints (embeddings) and compare them for speaker verification.

---

## 🔧 Technologies Used

*   **Backend:**
    *   Python 3.11+
    *   Flask (for the web server and templating)
    *   DeepFace (for facial recognition)
    *   SpeechBrain (for speaker verification)
    *   PySerial (for Arduino communication)
    *   Pydub (for server-side audio format conversion)
    *   OpenCV (`opencv-python-headless`) (for image processing)
    *   Torch & Torchaudio
*   **Frontend:**
    *   HTML5
    *   CSS3
    *   JavaScript (ES6+)
    *   MediaStream API (Webcam)
    *   MediaRecorder API (Microphone)
*   **Hardware:**
    *   Arduino Mega 2560
    *   AS608 Optical Fingerprint Sensor
*   **System Dependencies:**
    *   FFmpeg (required by Pydub for audio conversion)

---

## 🚀 Setup and Installation

Follow these steps to get the system operational.

### 1. Hardware Setup
-   Connect the AS608 sensor to the Arduino Mega using the **`Serial2`** port:
    -   `VCC` -> `5V`
    -   `GND` -> `GND`
    -   `TX` (Sensor) -> `RX2` (Pin 17 on Mega)
    -   `RX` (Sensor) -> `TX2` (Pin 16 on Mega)
-   Connect the Arduino Mega to your computer via USB.
-   Open the Arduino IDE, install the **"Adafruit Fingerprint Sensor Library"**, and upload the final provided `.ino` sketch to the board.

### 2. Backend Setup
-   **Create a Virtual Environment:**
    ```bash
    python -m venv .venv
    .venv\Scripts\activate
    ```
-   **Install Python Dependencies:**
    ```bash
    pip install flask pyserial deepface speechbrain pydub opencv-python-headless torch torchaudio --extra-index-url https://download.pytorch.org/whl/cpu
    ```
-   **Install FFmpeg:** Pydub requires FFmpeg. The easiest way to install it on Windows is using a package manager like Chocolatey:
    ```bash
    choco install ffmpeg
    ```
    Alternatively, download it from the official website and add its `bin` directory to your system's PATH.
-   **Configure COM Port:** Open `app.py` and change the `SERIAL_PORT` variable (e.g., `'COM3'`) to match the port your Arduino is connected to.

### 3. Frontend Setup
-   Create a directory `static/audio/` in your project folder.
-   Place your three sound effect files into this directory with the following names:
    -   `countdown_beep.mp3` (A 10-second audio file with beeps)
    -   `launch_rumble.mp3`
    -   `abort_alarm.mp3`

### 4. Run the Application
-   Ensure the Arduino IDE's Serial Monitor is **closed**.
-   Run the Flask application from your terminal:
    ```bash
    python app.py
    ```
-   Open your web browser and navigate to `http://127.0.0.1:5000`.

---

## How to Use

### Enrollment
1.  From the main page, click **"ENROLL NEW OPERATIVE"**.
2.  Enter an operative designation (e.g., "Commander Ivan") and proceed.
3.  **Fingerprint:** Click "INITIATE SCAN" and follow the on-screen prompts, placing your finger on the sensor as directed.
4.  **Face:** The webcam will activate. Click "CAPTURE & ANALYZE". The system will automatically detect your face and confirm if it's valid.
5.  **Voice:** Record three separate samples of the required passphrase. The "COMPLETE ENROLLMENT" button will activate once all three are recorded. Click it to finish.

### Authentication
1.  From the main page, click **"INITIATE AUTHENTICATION"**.
2.  **Fingerprint:** Click "INITIATE VERIFICATION" and place your enrolled finger on the sensor.
3.  **Face:** The webcam will activate. Capture your face. The system will perform a 1-to-1 verification against your enrolled image.
4.  **Voice:** Record the required passphrase for the final verification.
5.  Upon success, you will be granted access to the **Strategic Launch Console**.

---

## 🛠️ Maintenance

The project includes a utility for performing a full data wipe.

-   **File:** `purge_all_data.py`
-   **Function:** This script will connect to the Arduino to wipe all fingerprints, delete the `operative_archives.csv`, and delete the `enrolled_faces_img` folder.
-   **Usage:**
    1.  Stop the Flask server.
    2.  Run the script: `python purge_all_data.py`
    3.  Type `PURGE ALL DATA` to confirm the irreversible action.

---

## 🔮 Future Work

*   **Database Migration:** Transition from CSV files to a secure SQL database (e.g., PostgreSQL) for better data integrity and scalability.
*   **Anti-Spoofing:** Implement liveness detection for facial recognition to prevent attacks using static photos or videos.
*   **Data Encryption:** Encrypt the stored facial images and voice database at rest.
*   **Real-Time Communication:** Replace the HTTP polling mechanism with WebSockets for instant, low-latency status updates from the hardware.

# purge_all_data.py
# A standalone maintenance script to perform a full system data wipe.
# This utility will:
#   1. Wipe all stored fingerprints from the AS608 sensor.
#   2. Delete the operative_archives.csv file.
#   3. Delete the entire enrolled_faces directory.
# WARNING: This action is irreversible and will reset the application to a factory state.

import serial
import time
import os
import shutil

# --- CONFIGURATION ---
# CRITICAL: Ensure this matches the COM port of your Arduino Mega.
SERIAL_PORT = 'COM3'
BAUD_RATE = 9600
FINGERPRINT_CAPACITY = 127

# Define the paths to the data that will be deleted.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_FILE_PATH = os.path.join(BASE_DIR, "operative_archives.csv")
FACE_DB_PATH = os.path.join(BASE_DIR, "enrolled_faces")


def purge_all_data():
    """
    Executes the three-stage purge protocol.
    """
    # --- Stage 1: Purge Sensor Memory ---
    print("\n--- STAGE 1 of 3: Purging Biometric Sensor Memory ---")
    sensor_purged = purge_sensor_fingerprints()
    if not sensor_purged:
        print("\nAborting purge due to sensor communication failure.")
        return

    # --- Stage 2: Purge Application Archives (CSV) ---
    print("\n--- STAGE 2 of 3: Purging Operative Archives (CSV) ---")
    try:
        if os.path.exists(CSV_FILE_PATH):
            os.remove(CSV_FILE_PATH)
            print(f"SUCCESS: Deleted '{os.path.basename(CSV_FILE_PATH)}'.")
        else:
            print(f"INFO: '{os.path.basename(CSV_FILE_PATH)}' not found. Already clean.")
    except Exception as e:
        print(f"ERROR: Could not delete CSV file. Reason: {e}")
        return

    # --- Stage 3: Purge Face Dossiers (Folder) ---
    print("\n--- STAGE 3 of 3: Purging Facial Dossier Database ---")
    try:
        if os.path.exists(FACE_DB_PATH):
            shutil.rmtree(FACE_DB_PATH)
            print(f"SUCCESS: Deleted '{os.path.basename(FACE_DB_PATH)}' directory and all its contents.")
        else:
            print(f"INFO: '{os.path.basename(FACE_DB_PATH)}' directory not found. Already clean.")
    except Exception as e:
        print(f"ERROR: Could not delete face database directory. Reason: {e}")
        return

    print("\n========================================================")
    print("  FULL SYSTEM PURGE COMPLETE.")
    print("  The application has been reset to a factory state.")
    print("========================================================")


def purge_sensor_fingerprints():
    """Connects to the controller and wipes all stored fingerprints."""
    ser = None
    try:
        print(f"Attempting to connect to sensor controller on {SERIAL_PORT}...")
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=2)

        line = ser.readline().decode('utf-8').strip()
        if line != "READY":
            print(f"ERROR: Handshake failed. Controller sent '{line}'.")
            return False

        print("SUCCESS: Connection established. Preparing to purge all signatures.")
        time.sleep(1)

        deleted_count = 0
        for i in range(1, FINGERPRINT_CAPACITY + 1):
            command = f"DELETE_FINGER:{i}\n"
            ser.write(command.encode('utf-8'))
            response = ser.readline().decode('utf-8').strip()
            if f"SUCCESS_DELETE:{i}" in response:
                deleted_count += 1
            time.sleep(0.05)

        print(f"SUCCESS: Confirmed deletion for {deleted_count} signatures on sensor.")
        return True

    except serial.SerialException:
        print(f"CRITICAL ERROR: Could not open serial port '{SERIAL_PORT}'.")
        print("Please ensure the controller is connected and no other program is using the port.")
        return False
    except Exception as e:
        print(f"An unexpected error occurred during sensor purge: {e}")
        return False
    finally:
        if ser and ser.is_open:
            ser.close()
            print("Sensor connection closed.")


if __name__ == "__main__":
    print("=========================================================")
    print("  OMSK FULL SYSTEM DATA PURGE UTILITY")
    print("=========================================================")
    print("WARNING: This utility will permanently delete ALL fingerprints,")
    print("         ALL user records, and ALL face data.")
    print("         This action is IRREVERSIBLE.")

    # Safety confirmation prompt
    confirm = input("Type 'PURGE ALL DATA' to confirm and proceed: ")

    if confirm == "PURGE ALL DATA":
        print("\nConfirmation received. Initiating full system purge protocol...")
        purge_all_data()
    else:
        print("\nPurge aborted. No changes have been made.")
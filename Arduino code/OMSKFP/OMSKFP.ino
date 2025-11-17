// OMSK Biometric Controller - 3rd VERSION

#include <Adafruit_Fingerprint.h>

#define SENSOR_SERIAL Serial2
Adafruit_Fingerprint finger = Adafruit_Fingerprint(&SENSOR_SERIAL);

int nextAvailableId = 0;

void setup() {
  Serial.begin(9600);
  while (!Serial);
  SENSOR_SERIAL.begin(57600);
  delay(100);
  if (!finger.verifyPassword()) {
    while (1) { delay(1); } 
  }
  finger.getTemplateCount();
  nextAvailableId = finger.templateCount + 1;
  Serial.println("READY");
}

void loop() {
  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n');
    command.trim();

    if (command == "ENROLL") {
      enrollFingerprint();
    } else if (command == "LOGIN") {
      loginWithFingerprint();
    } else if (command.startsWith("DELETE_FINGER:")) {
      deleteFingerprint(command);
    } else if (command == "LIST_FINGERS") {
      listFingerprints();
    }
  }
}

// --- MANAGEMENT FUNCTIONS ---

void deleteFingerprint(String command) {
  // Extracts the ID from a command like "DELETE_FINGER:14"
  int idToDelete = command.substring(command.indexOf(':') + 1).toInt();
  if (idToDelete > 0) {
    if (finger.deleteModel(idToDelete) == FINGERPRINT_OK) {
      Serial.print("SUCCESS_DELETE:");
      Serial.println(idToDelete);
    } else {
      Serial.print("ERROR:DELETE_FAILED:");
      Serial.println(idToDelete);
    }
  }
}

void listFingerprints() {
  finger.getTemplateCount();
  int templateCount = finger.templateCount;
  // The library doesn't provide a direct list of IDs, so we check each slot.
  // This is a reliable way to find all stored templates, even if there are gaps.
  for (int i = 1; i <= 127; i++) {
    if (finger.loadModel(i) == FINGERPRINT_OK) {
      // If we can successfully load a model at this ID, it exists.
      Serial.print("FINGER_ID:");
      Serial.println(i);
    }
  }
  Serial.println("LIST_COMPLETE");
}


// --- EXISTING PROTOCOLS ---
void enrollFingerprint() {
  int id_to_enroll = nextAvailableId;
  Serial.print("ENROLL_STARTING:");
  Serial.println(id_to_enroll);
  Serial.println("WAITING_FINGER_1");
  while (finger.getImage() != FINGERPRINT_OK);
  if (finger.image2Tz(1) != FINGERPRINT_OK) { Serial.println("ERROR:IMAGE_CONVERSION_1_FAILED"); return; }
  Serial.println("FINGER_AWAY");
  delay(2000);
  while (finger.getImage() != FINGERPRINT_NOFINGER);
  Serial.println("WAITING_FINGER_2");
  while (finger.getImage() != FINGERPRINT_OK);
  if (finger.image2Tz(2) != FINGERPRINT_OK) { Serial.println("ERROR:IMAGE_CONVERSION_2_FAILED"); return; }
  if (finger.createModel() != FINGERPRINT_OK) { Serial.println("ERROR:NO_MATCH"); return; }
  if (finger.storeModel(id_to_enroll) == FINGERPRINT_OK) {
    Serial.print("SUCCESS_ENROLL:");
    Serial.println(id_to_enroll);
    nextAvailableId++;
  } else { Serial.println("ERROR:STORE_FAILED"); }
}

void loginWithFingerprint() {
    Serial.println("LOGIN_STARTING");
    Serial.println("WAITING_FINGER");
    while (finger.getImage() != FINGERPRINT_OK);
    if (finger.image2Tz(1) != FINGERPRINT_OK) { Serial.println("ERROR:IMAGE_CONVERSION_FAILED"); return; }
    if (finger.fingerSearch() == FINGERPRINT_OK) {
        Serial.print("SUCCESS_LOGIN:");
        Serial.println(finger.fingerID);
    } else { Serial.println("ERROR:NOT_FOUND"); }
}

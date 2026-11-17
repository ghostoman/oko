// FaceTracker, main board: keyestudio ESP32 (ESP32-WROOM-32E, 38 pin). Pins and default tuning.
#pragma once
#define PIN_CAM_RX   16   // <- ESP32-CAM U0T
#define PIN_CAM_TX   17   // -> ESP32-CAM U0R
#define PIN_PAN      18   // pan servo signal (orange)
#define PIN_TILT     19   // tilt servo signal (orange)
#define BAUD         921600

// defaults (all can be changed over serial and saved with "save")
#define DEF_FOV        56.0f   // OV2640 stock lens: field of view along the long side of the picture, deg
#define DEF_KP         0.70f   // share of the measured error taken out by one correction (1.0 = jump straight to the face)
#define DEF_LAG        80      // ms between the middle of an exposure and its picture reaching the detector, plus servo lag
#define DEF_PRED       1.0f    // prediction: 1 = aim where the face will be after the whole delay, 0 = no prediction
#define DEF_LEAD       60      // extra lead, ms: time the servo itself needs to start moving
#define DEF_DEAD       2.0f    // dead zone, deg: inside it the servos stay still
#define DEF_SPEED      90.0f   // max servo speed, deg/s
#define DEF_SMOOTH     500     // ms: the head eases into a move and eases out of it, reaching the target in about this time (0 = straight moves)
#define DEF_US_PER_DEG 10.3f   // MG90S: about 10.3 us per degree
#define DEF_PAN_LIM    80.0f
#define DEF_TILT_MIN  -40.0f
#define DEF_TILT_MAX   40.0f
#define DEF_HOME_MS    6000    // face lost for this long -> return to centre

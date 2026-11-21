// FaceTracker, main board: keyestudio ESP32. Drives the two MG90S and keeps the face reported by the ESP32-CAM
// in the middle of its picture. The camera rides on the tilting head, so the loop is closed.
// Control: every report says where the face was in the picture; the servo position at the moment that picture was
// taken is looked up in a short history and the target becomes "that position + kp * error". Nothing is integrated,
// so the loop stays calm at any frame rate.
// Prediction (2.2): the face direction is filtered into a position and a speed, and between two camera reports the
// target keeps moving with that speed, ahead by the whole delay of the chain. A moving face is followed, not chased.
// 2.3: the first live try of the prediction was worse than the plain law, so it is OFF after every start (plain 2.1 law,
// function controlPlain). "set pred <gain>" switches it on until the next restart, for tuning.
// 2.5: smooth moves. The servos follow the target like a critically damped spring ("set smooth <ms>"): a move starts gently,
// slows down gently and never overshoots. "set aimx/aimy <deg>" keeps the face off the middle of the ESP32-CAM picture,
// to centre it in the webcam that sits next to it.
// 2.6: runs for hours. A health watchdog restarts the camera sensor when its picture stops (no reports, frame timeouts)
// or when no face has been seen for 40 s (a stuck exposure or a torn DMA picture looks exactly like "nobody there").
// The automatic axis flip only judges a correction after the servo has arrived, needs 6 strikes, and is written to
// flash only after the new direction has proven itself. A task watchdog reboots the board if the loop ever hangs.
// "bridge" turns the board into a plain USB <-> camera serial link (115200) for flashing the ESP32-CAM, see flash_cam_bridge.ps1.
// USB serial 921600: commands + telemetry for tools\ft_monitor.py.   Build: fqbn esp32:esp32:esp32
#include <Arduino.h>
#include <Preferences.h>
#include "soc/soc.h"
#include "soc/rtc_cntl_reg.h"
#include "config.h"
#include "esp_task_wdt.h"

#define FW_VERSION "2.6"
#define CH_PAN  0
#define CH_TILT 2
struct Cfg {
  uint8_t magic; int8_t panDir, tiltDir; int16_t panTrim, tiltTrim;
  float kp, dead, speed, usPerDeg, fov, panLim, tiltMin, tiltMax, aimX, aimY; uint32_t homeMs; uint16_t lag, lead; float pred; uint16_t smooth;
} cfg;
const uint8_t CFG_MAGIC = 0x72;
Preferences prefs;
HardwareSerial Cam(2);
enum State { ST_NOLINK, ST_MANUAL, ST_SEARCH, ST_LOCK };
const char *ST_NAME[] = {"NOLINK", "MANUAL", "SEARCH", "LOCK"};
State state = ST_NOLINK;
volatile float tgtPan = 0, tgtTilt = 0, curPan = 0, curTilt = 0;
#define HIST 64                                           // servo positions of the last 640 ms, one every 10 ms
volatile float histPan[HIST], histTilt[HIST]; volatile uint32_t histN = 0;
bool tracking = true, streamOn = false;
uint32_t lastCam = 0, lastSeen = 0, lastStat = 0, camFrames = 0, camMs = 0;
float fps = 0, nx = 0, ny = 0, nw = 0, score = 0;     // face, normalised 0..1
// health watchdog
uint32_t bootMs = 0, lastHeal = 0, heals = 0, flips = 0, timeouts = 0, lastTimeout = 0; int camXclk = 20; bool flipPending = false; int flipGood = 0;
int divPan = 0, divTilt = 0; float prevEx = 0, prevEy = 0; bool prevStepPan = false, prevStepTilt = false;

void cfgDefaults() {
  cfg.magic = CFG_MAGIC; cfg.panDir = -1; cfg.tiltDir = 1; cfg.panTrim = 0; cfg.tiltTrim = 0;
  cfg.kp = DEF_KP; cfg.dead = DEF_DEAD; cfg.speed = DEF_SPEED; cfg.usPerDeg = DEF_US_PER_DEG; cfg.fov = DEF_FOV;
  cfg.panLim = DEF_PAN_LIM; cfg.tiltMin = DEF_TILT_MIN; cfg.tiltMax = DEF_TILT_MAX; cfg.aimX = 0; cfg.aimY = 0; cfg.homeMs = DEF_HOME_MS; cfg.lag = DEF_LAG; cfg.lead = DEF_LEAD; cfg.pred = DEF_PRED; cfg.smooth = DEF_SMOOTH;
}
void cfgStore() { prefs.putBytes("cfg", &cfg, sizeof(cfg)); }

static inline uint32_t usToDuty(float us) { return (uint32_t)(us * 65535.0f / 20000.0f + 0.5f); }
void servoTask(void *) {
  int lastP = -1, lastT = -1; float vP = 0, vT = 0; const float dt = 0.01f;
  for (;;) {
    if (cfg.smooth >= 50) {
      // critically damped follower: velocity starts from zero (ease in), dies out near the target (ease out), no overshoot.
      // 90 % of a move is done after cfg.smooth ms. A new target in the middle of a move just bends the path.
      float w = 3.9f / (cfg.smooth * 0.001f), dP = tgtPan - curPan, dT = tgtTilt - curTilt;
      vP = constrain(vP + (w * w * dP - 2 * w * vP) * dt, -cfg.speed, cfg.speed);
      vT = constrain(vT + (w * w * dT - 2 * w * vT) * dt, -cfg.speed, cfg.speed);
      if (fabsf(dP) < 0.03f && fabsf(vP) < 0.5f) { curPan = tgtPan; vP = 0; } else curPan += vP * dt;
      if (fabsf(dT) < 0.03f && fabsf(vT) < 0.5f) { curTilt = tgtTilt; vT = 0; } else curTilt += vT * dt;
    } else {
      float step = cfg.speed * dt; vP = vT = 0;
      curPan += constrain(tgtPan - curPan, -step, step); curTilt += constrain(tgtTilt - curTilt, -step, step);
    }
    int up = constrain((int)(1500 + cfg.panTrim + curPan * cfg.usPerDeg + 0.5f), 520, 2480);
    int ut = constrain((int)(1500 + cfg.tiltTrim + curTilt * cfg.usPerDeg + 0.5f), 520, 2480);
    if (up != lastP) { ledcWrite(CH_PAN, usToDuty(up)); lastP = up; }      // nothing changed -> nothing rewritten -> no jitter
    if (ut != lastT) { ledcWrite(CH_TILT, usToDuty(ut)); lastT = ut; }
    histPan[histN & (HIST - 1)] = curPan; histTilt[histN & (HIST - 1)] = curTilt; histN++;
    vTaskDelay(pdMS_TO_TICKS(10));
  }
}
void setTarget(float p, float t) { tgtPan = constrain(p, -cfg.panLim, cfg.panLim); tgtTilt = constrain(t, cfg.tiltMin, cfg.tiltMax); }

// --- the face as a direction in servo angles: filtered position, speed, and the moment they belong to
#define VMAX 200.0f
bool usePred = false;         // prediction is an experiment: off after every start
bool estOk = false; float estPan = 0, estTilt = 0, velPan = 0, velTilt = 0; uint32_t estT = 0, estSeen = 0;
// flight recorder: the last 256 camera reports, read back with "log" (the USB link may drop while the servos pull current)
struct Rec { uint32_t t; int16_t ex, ey, pan, tilt, vp, vt, ms; } rec[256]; uint32_t recN = 0;
void recPut(float ex, float ey, uint32_t ms) {
  Rec &r = rec[recN++ & 255]; r.t = millis(); r.ex = ex * 10; r.ey = ey * 10; r.pan = curPan * 10; r.tilt = curTilt * 10; r.vp = velPan; r.vt = velTilt; r.ms = ms;
}
void recDump() {
  uint32_t n = min(recN, (uint32_t)256), t0 = n ? rec[(recN - n) & 255].t : 0;
  Serial.printf("#LOG %u records: ms, errX, errY, pan, tilt, speedPan, speedTilt, detect ms (err 999 = no face)\n", n);
  for (uint32_t i = recN - n; i != recN; i++) { Rec &r = rec[i & 255]; Serial.printf("#L %u %.1f %.1f %.1f %.1f %d %d %d\n", r.t - t0, r.ex / 10.0f, r.ey / 10.0f, r.pan / 10.0f, r.tilt / 10.0f, r.vp, r.vt, r.ms); }
  Serial.println("#LOGEND");
}

void steer() {            // aim where the face is by now; runs all the time while a face is being followed
  if (!usePred || !estOk || !tracking) return;
  uint32_t now = millis();
  if (now - estSeen > 450) { estOk = false; return; }       // no fresh report: stop extrapolating
  float T = (min((int32_t)(now - estT), (int32_t)500) + (int32_t)cfg.lead) / 1000.0f * cfg.pred;
  float dp = estPan + velPan * T, dtl = estTilt + velTilt * T, p = tgtPan, t = tgtTilt;
  if (fabsf(dp - p) > cfg.dead * 0.5f || fabsf(velPan) > 4.0f) p = dp;       // a still face: do not chase the noise
  if (fabsf(dtl - t) > cfg.dead * 0.5f || fabsf(velTilt) > 4.0f) t = dtl;
  setTarget(p, t);
}

void control(float cx, float cy, int W, int H, uint32_t ms) {
  float dpp = cfg.fov / max(W, H);                          // degrees per pixel
  float ex = (cx - W * 0.5f) * dpp - cfg.aimX;              // + = face is to the right in the picture
  float ey = (H * 0.5f - cy) * dpp - cfg.aimY;              // + = face is above the centre
  // self-check of the direction signs: if the error keeps growing although the servo has arrived, flip that axis
  if (prevStepPan && fabsf(tgtPan - curPan) < 3.0f) { if (fabsf(ex) > fabsf(prevEx) + 1.5f && ex * prevEx > 0) divPan++; else divPan = max(0, divPan - 1); }
  if (prevStepTilt && fabsf(tgtTilt - curTilt) < 3.0f) { if (fabsf(ey) > fabsf(prevEy) + 1.5f && ey * prevEy > 0) divTilt++; else divTilt = max(0, divTilt - 1); }
  if (divPan >= 6) { cfg.panDir = -cfg.panDir; divPan = 0; estOk = false; flips++; flipPending = true; flipGood = 0; Serial.println("# pan direction flipped automatically (not saved yet)"); }
  if (divTilt >= 6) { cfg.tiltDir = -cfg.tiltDir; divTilt = 0; estOk = false; flips++; flipPending = true; flipGood = 0; Serial.println("# tilt direction flipped automatically (not saved yet)"); }
  // where the servos stood when this picture was taken
  uint32_t lat = ms + cfg.lag, back = min((uint32_t)(HIST - 1), lat / 10), hn = histN;
  float pan0 = hn > back ? histPan[(hn - 1 - back) & (HIST - 1)] : curPan, tilt0 = hn > back ? histTilt[(hn - 1 - back) & (HIST - 1)] : curTilt;
  float mp = pan0 + cfg.panDir * ex, mt = tilt0 + cfg.tiltDir * ey;      // the face as an absolute direction at that moment
  uint32_t now = millis(), tc = now - lat;
  float dt = (int32_t)(tc - estT) / 1000.0f;
  if (!estOk || dt > 0.7f) { estPan = mp; estTilt = mt; velPan = velTilt = 0; estOk = true; estT = tc; }
  else if (dt > 0.03f) {                                    // alpha-beta filter; kp = how much one report is trusted
    float a = constrain(cfg.kp, 0.2f, 1.0f), b = a * 0.5f;
    float pp = estPan + velPan * dt, pt = estTilt + velTilt * dt, rp = mp - pp, rt = mt - pt;
    estPan = pp + a * rp; estTilt = pt + a * rt;
    velPan = constrain(velPan + b * rp / dt, -VMAX, VMAX); velTilt = constrain(velTilt + b * rt / dt, -VMAX, VMAX);
    estT = tc;
  }
  estSeen = now; recPut(ex, ey, ms);
  prevStepPan = fabsf(ex) > cfg.dead && fabsf(tgtPan) < cfg.panLim;
  prevStepTilt = fabsf(ey) > cfg.dead && tgtTilt > cfg.tiltMin && tgtTilt < cfg.tiltMax;
  prevEx = ex; prevEy = ey;
  steer();
}

// The plain law of firmware 2.1: target = servo position when the picture was taken + kp * error. No prediction.
void controlPlain(float cx, float cy, int W, int H, uint32_t ms) {
  float dpp = cfg.fov / max(W, H);                          // degrees per pixel
  float ex = (cx - W * 0.5f) * dpp - cfg.aimX;              // + = face is to the right in the picture
  float ey = (H * 0.5f - cy) * dpp - cfg.aimY;              // + = face is above the centre
  // self-check of the direction signs: if corrections keep making the error bigger, flip that axis.
  // 2.6: a correction is only judged once the servo has arrived (a fast-moving face is not a wrong sign), 6 strikes are
  // needed, and the flip stays in RAM until 15 good corrections prove it; only then it is saved.
  bool arrivedP = fabsf(tgtPan - curPan) < 1.5f, arrivedT = fabsf(tgtTilt - curTilt) < 1.5f;
  if (prevStepPan && arrivedP) { if (fabsf(ex) > fabsf(prevEx) + 1.5f && ex * prevEx > 0) divPan++; else divPan = max(0, divPan - 1); }
  if (prevStepTilt && arrivedT) { if (fabsf(ey) > fabsf(prevEy) + 1.5f && ey * prevEy > 0) divTilt++; else divTilt = max(0, divTilt - 1); }
  if (divPan >= 6) { cfg.panDir = -cfg.panDir; divPan = 0; flips++; flipPending = true; flipGood = 0; Serial.println("# pan direction flipped automatically (not saved yet)"); }
  if (divTilt >= 6) { cfg.tiltDir = -cfg.tiltDir; divTilt = 0; flips++; flipPending = true; flipGood = 0; Serial.println("# tilt direction flipped automatically (not saved yet)"); }
  if (flipPending && (prevStepPan || prevStepTilt) && fabsf(ex) + fabsf(ey) < fabsf(prevEx) + fabsf(prevEy) && ++flipGood >= 15) { flipPending = false; cfgStore(); Serial.println("# new direction confirmed and saved"); }
  // where the servos stood when this picture was taken
  uint32_t back = min((uint32_t)(HIST - 1), (ms + cfg.lag) / 10), hn = histN;
  float pan0 = hn > back ? histPan[(hn - 1 - back) & (HIST - 1)] : curPan, tilt0 = hn > back ? histTilt[(hn - 1 - back) & (HIST - 1)] : curTilt;
  float p = tgtPan, t = tgtTilt;
  prevStepPan = fabsf(ex) > cfg.dead; prevStepTilt = fabsf(ey) > cfg.dead;
  if (prevStepPan) p = pan0 + cfg.panDir * ex * cfg.kp;
  if (prevStepTilt) t = tilt0 + cfg.tiltDir * ey * cfg.kp;
  if (fabsf(p) >= cfg.panLim) prevStepPan = false;
  if (t <= cfg.tiltMin || t >= cfg.tiltMax) prevStepTilt = false;
  prevEx = ex; prevEy = ey;
  recPut(ex, ey, ms);
  setTarget(p, t);
}

void sendStatus() {
  Serial.printf("#S {\"st\":\"%s\",\"n\":%d,\"x\":%.3f,\"y\":%.3f,\"w\":%.3f,\"sc\":%.2f,\"pan\":%.1f,\"tilt\":%.1f,\"fps\":%.1f,\"ms\":%u,\"heap\":%u,\"pd\":%d,\"td\":%d,\"vp\":%.1f,\"vt\":%.1f,\"up\":%u,\"heal\":%u,\"to\":%u,\"flips\":%u}\n",
                ST_NAME[state], state == ST_LOCK ? 1 : 0, nx, ny, nw, score, (float)curPan, (float)curTilt, fps, camMs, ESP.getFreeHeap(), cfg.panDir, cfg.tiltDir, estOk ? velPan : 0.0f, estOk ? velTilt : 0.0f, (millis() - bootMs) / 1000, heals, timeouts, flips);
}
void show() {
  Serial.printf("panDir %d tiltDir %d panTrim %d tiltTrim %d\nkp %.2f dead %.1f speed %.0f usdeg %.2f fov %.0f panlim %.0f tiltmin %.0f tiltmax %.0f aimx %.1f aimy %.1f home %u lag %u pred %.2f lead %u smooth %u\n",
                cfg.panDir, cfg.tiltDir, cfg.panTrim, cfg.tiltTrim, cfg.kp, cfg.dead, cfg.speed, cfg.usPerDeg, cfg.fov, cfg.panLim, cfg.tiltMin, cfg.tiltMax, cfg.aimX, cfg.aimY, cfg.homeMs, cfg.lag, cfg.pred, cfg.lead, cfg.smooth);
  Cam.println("show");
}
void help() {
  Serial.println(F("FaceTracker main " FW_VERSION " commands:\n"
    "  status | stream 0/1 | frame        telemetry, one picture from the camera\n"
    "  track 0/1 | center                 tracking on/off; both servos to the middle and stop (for fitting the horns)\n"
    "  pan <deg> | tilt <deg>             manual move\n"
    "  flip pan|tilt   trim pan|tilt <us> reverse an axis, centre trim\n"
    "  set <kp|dead|speed|usdeg|fov|panlim|tiltmin|tiltmax|aimx|aimy|home|lag|pred|lead|smooth> <value>\n"
    "                                     smooth: ms for an eased move (0 = straight); aimx/aimy: keep the face this many deg off the centre\n"
    "  cam <rot 0..4|scale v|score v|stages 1..3|led 0..255|save|defaults|show>   settings of the ESP32-CAM (rot 4 = auto)\n"
    "  cam <fast 0/1|in px|roi v|xclk MHz|clk reg|perf>                           its speed: window around the face, sensor clock, timing\n"
    "  bridge                             USB <-> camera link at 115200 for flashing the ESP32-CAM (flash_cam_bridge.ps1 ends it)\n"
    "  log | log clear                    the last 256 camera reports with servo angles (to tune the tracking)\n"
    "  show | save | defaults | reboot"));
}
void command(String s) {
  s.trim(); if (!s.length()) return;
  int sp = s.indexOf(' '); String c = sp < 0 ? s : s.substring(0, sp); String a = sp < 0 ? "" : s.substring(sp + 1); a.trim();
  int sp2 = a.indexOf(' '); String a1 = sp2 < 0 ? a : a.substring(0, sp2); String a2 = sp2 < 0 ? "" : a.substring(sp2 + 1);
  float v = a2.length() ? a2.toFloat() : a1.toFloat();
  if (c == "help" || c == "?") help();
  else if (c == "status") sendStatus();
  else if (c == "stream") streamOn = a.toInt();
  else if (c == "frame") Cam.println("frame");
  else if (c == "cam") Cam.println(a);
  else if (c == "track") { tracking = a.toInt(); estOk = false; Serial.println(tracking ? "tracking on" : "tracking off"); }
  else if (c == "center") { tracking = false; setTarget(0, 0); Serial.println("centred, tracking off"); }
  else if (c == "pan") { tracking = false; setTarget(v, tgtTilt); }
  else if (c == "tilt") { tracking = false; setTarget(tgtPan, v); }
  else if (c == "flip") { if (a1 == "pan") cfg.panDir = -cfg.panDir; else if (a1 == "tilt") cfg.tiltDir = -cfg.tiltDir; show(); }
  else if (c == "trim") { if (a1 == "pan") cfg.panTrim = (int16_t)v; else if (a1 == "tilt") cfg.tiltTrim = (int16_t)v; show(); }
  else if (c == "set") {
    if (a1 == "kp") cfg.kp = v; else if (a1 == "dead") cfg.dead = v; else if (a1 == "speed") cfg.speed = v; else if (a1 == "usdeg") cfg.usPerDeg = v;
    else if (a1 == "fov") cfg.fov = v; else if (a1 == "panlim") cfg.panLim = v; else if (a1 == "tiltmin") cfg.tiltMin = v; else if (a1 == "tiltmax") cfg.tiltMax = v;
    else if (a1 == "aimx") cfg.aimX = v; else if (a1 == "aimy") cfg.aimY = v; else if (a1 == "home") cfg.homeMs = (uint32_t)v; else if (a1 == "lag") cfg.lag = (uint16_t)constrain(v, 0.0f, 600.0f);
    else if (a1 == "pred") { cfg.pred = constrain(v, 0.0f, 2.0f); usePred = cfg.pred > 0; estOk = false; } else if (a1 == "lead") cfg.lead = (uint16_t)constrain(v, 0.0f, 300.0f);
    else if (a1 == "smooth") cfg.smooth = (uint16_t)constrain(v, 0.0f, 3000.0f); else Serial.println("unknown key");
    show();
  }
  else if (c == "show") show();
  else if (c == "save") { cfgStore(); Cam.println("save"); Serial.println("saved"); }
  else if (c == "defaults") { cfgDefaults(); show(); }
  else if (c == "bridge") { prefs.putBool("bridge", true); Serial.println("bridge mode: restarting as a 115200 link to the camera"); Serial.flush(); delay(100); ESP.restart(); }
  else if (c == "log") { if (a1 == "clear") recN = 0; else recDump(); }
  else if (c == "reboot") ESP.restart();
  else Serial.println("? (help)");
}

// one line from the camera board
void camLine(char *l) {
  uint32_t now = millis();
  if (l[0] == 'F' && l[1] == ' ') {
    int cx, cy, w, sc, W, H; unsigned ms;
    if (sscanf(l + 2, "%d %d %d %d %d %d %u", &cx, &cy, &w, &sc, &W, &H, &ms) == 7 && W > 0 && H > 0) {
      lastCam = lastSeen = now; camFrames++; camMs = ms; nx = (float)cx / W; ny = (float)cy / H; nw = (float)w / W; score = sc / 100.0f;
      if (tracking) { state = ST_LOCK; if (usePred) control(cx, cy, W, H, ms); else controlPlain(cx, cy, W, H, ms); }
    }
  } else if (l[0] == 'N' && l[1] == ' ') {
    lastCam = now; camFrames++; prevStepPan = prevStepTilt = false; sscanf(l + 2, "%*d %*d %u", &camMs); if (tracking) recPut(99.9f, 99.9f, camMs);
    if (tracking) state = ST_SEARCH;
  } else if (l[0] == '#') {
    Serial.println(l);
    const char *xk = strstr(l, " xclk ");
    if (strncmp(l, "# cam ", 6) == 0 && xk) camXclk = constrain(atoi(xk + 6), 5, 24);
    if (strstr(l, "frame timeout")) { timeouts++; lastTimeout = now; }
    int w, h, n;
    if (sscanf(l, "#IMG %d %d %d", &w, &h, &n) == 3 && n > 0 && n <= 80000) {      // picture: pass the raw bytes straight to the PC
      uint32_t t0 = millis(); static uint8_t buf[512];
      while (n > 0 && millis() - t0 < 3000) { int k = Cam.readBytes(buf, min(n, (int)sizeof(buf))); if (k > 0) { Serial.write(buf, k); n -= k; } }
      Serial.println(); sendStatus();
    }
  }
}
// Restart the camera sensor (deinit + init on the ESP32-CAM) without touching its settings
void healCam(const char *why) {
  lastHeal = millis(); heals++;
  Serial.printf("# health: restarting the camera sensor (%s), #%u\n", why, heals);
  Cam.printf("xclk %d\n", camXclk);
}
void health(uint32_t now) {
  if (now - bootMs < 8000 || now - lastHeal < 6000) return;
  if (now - lastCam > 4000) { healCam("no reports"); return; }                                  // picture stopped
  if (timeouts >= 3 && now - lastTimeout < 3000) { timeouts = 0; healCam("frame timeouts"); return; }
  // nobody seen for 40 s while tracking: a frozen exposure or a torn picture looks the same as an empty room,
  // so give the sensor a fresh start every 40 s (costs about half a second of picture)
  if (tracking && now - lastSeen > 40000 && now - lastHeal > 40000) healCam("no face for 40 s");
}
void pollCam() {
  static char line[200]; static int n = 0;
  while (Cam.available()) {
    char ch = Cam.read();
    if (ch == '\n') { line[n] = 0; if (n) camLine(line); n = 0; } else if (ch != '\r' && n < 199) line[n++] = ch; else if (n >= 199) n = 0;
  }
}
void pollUsb() {
  static String line;
  while (Serial.available()) { char ch = Serial.read(); if (ch == '\n' || ch == '\r') { command(line); line = ""; } else if (line.length() < 80) line += ch; }
}

// Transparent USB <-> camera serial link for flashing the ESP32-CAM without rewiring (camera U0T/U0R stay on IO16/IO17).
// Survives resets (the flag lives in flash) and ends on the text ~~FT-EXIT~~ from the PC or after 10 idle minutes.
void bridgeRun() {
  Serial.flush(); Serial.end(); Serial.setRxBufferSize(16384); Serial.begin(115200);
  Cam.setRxBufferSize(8192); Cam.begin(115200, SERIAL_8N1, PIN_CAM_RX, PIN_CAM_TX);
  static uint8_t b[2048]; const char *EX = "~~FT-EXIT~~"; int em = 0; uint32_t last = millis(); bool done = false;
  while (!done && millis() - last < 600000UL) {
    int n = Serial.available(), k = Cam.available();
    if (n > 0) {
      n = Serial.readBytes(b, min(n, (int)sizeof(b))); Cam.write(b, n); last = millis();
      for (int i = 0; i < n && !done; i++) { em = (b[i] == EX[em]) ? em + 1 : (b[i] == EX[0] ? 1 : 0); if (!EX[em]) done = true; }
    }
    if (k > 0) { k = Cam.readBytes(b, min(k, (int)sizeof(b))); Serial.write(b, k); }
    if (n <= 0 && k <= 0) delay(1);
  }
  prefs.putBool("bridge", false); delay(50); ESP.restart();
}

void setup() {
  WRITE_PERI_REG(RTC_CNTL_BROWN_OUT_REG, 0);            // servos on USB power dip the 5 V rail: do not reset on it
  Serial.begin(BAUD); delay(200);
  bootMs = millis();
  Serial.println("\nFaceTracker main " FW_VERSION);
  prefs.begin("ft", false);
  if (prefs.getBool("bridge", false)) bridgeRun();      // never returns
  memset(&cfg, 0, sizeof(cfg));
  size_t n = prefs.getBytes("cfg", &cfg, sizeof(cfg));
  if (cfg.magic != CFG_MAGIC || (n != sizeof(cfg) && n != offsetof(Cfg, smooth) && n != offsetof(Cfg, pred))) cfgDefaults();
  else if (n != sizeof(cfg)) {                           // settings saved by an older version: keep them, add the new ones
    if (n <= offsetof(Cfg, pred)) { cfg.lead = DEF_LEAD; cfg.pred = DEF_PRED; }
    cfg.smooth = DEF_SMOOTH; cfgStore();
  }
  Cam.setRxBufferSize(4096); Cam.setTimeout(200); Cam.begin(BAUD, SERIAL_8N1, PIN_CAM_RX, PIN_CAM_TX);
  ledcSetup(CH_PAN, 50, 16); ledcSetup(CH_TILT, 50, 16);
  ledcWrite(CH_PAN, usToDuty(1500 + cfg.panTrim)); ledcAttachPin(PIN_PAN, CH_PAN);
  delay(350);                                            // start the servos one after another: lower current peak
  ledcWrite(CH_TILT, usToDuty(1500 + cfg.tiltTrim)); ledcAttachPin(PIN_TILT, CH_TILT);
  delay(350);
  xTaskCreatePinnedToCore(servoTask, "servo", 3072, nullptr, 3, nullptr, 0);
  lastSeen = millis(); help(); show();
  esp_task_wdt_init(20, true); esp_task_wdt_add(NULL);   // a hung loop reboots the board after 20 s
}
void loop() {
  pollUsb(); pollCam();
  uint32_t now = millis();
  static uint32_t tf = 0, nf = 0;
  if (now - tf > 1000) { fps = (camFrames - nf) * 1000.0f / (now - tf); tf = now; nf = camFrames; }
  if (now - lastCam > 2000) state = ST_NOLINK; else if (!tracking) state = ST_MANUAL;
  if (streamOn && now - lastStat > 200) { lastStat = now; sendStatus(); }
  static uint32_t th = 0;
  if (tracking && now - lastSeen > cfg.homeMs && now - th > 100) {       // nobody for a while: glide back to the middle
    th = now;
    if (fabsf(tgtPan) > 1 || fabsf(tgtTilt) > 1) setTarget(tgtPan * 0.92f, tgtTilt * 0.92f); else setTarget(0, 0);
  }
  health(now);
  steer();
  esp_task_wdt_reset();
  delay(1);
}

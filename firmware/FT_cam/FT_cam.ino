// FaceTracker, camera board: ESP32-CAM (AI-Thinker, OV2640). Finds the face and reports it to the main ESP32.
// Link: UART0 (U0T -> main IO16, U0R <- main IO17), 921600 baud. Power: 3V3 pin from the main board.
// Every frame one line goes out:   F <cx> <cy> <w> <score*100> <W> <H> <ms>    (tracked face)   or   N <W> <H> <ms>
// Speed: the detector costs about 17 us per input pixel, so once a face is locked only a square window around it is
// cut out, averaged down to <in> x <in> pixels and searched (fast path). The whole picture is searched only to find
// a face or after a miss. The sensor runs free (2 frame buffers, newest frame wins), so the loop never waits for it.
// Works with or without PSRAM (QVGA with it, QQVGA without). Wi-Fi is never started.
// Build: fqbn esp32:esp32:esp32:PSRAM=enabled,PartitionScheme=huge_app   (see ..\flash.ps1 cam)
#include <Arduino.h>
#include <Preferences.h>
#include <list>
#include <vector>
#include "esp_camera.h"
#include "esp_heap_caps.h"
#include "soc/soc.h"
#include "soc/rtc_cntl_reg.h"
#include "human_face_detect_msr01.hpp"
#include "human_face_detect_mnp01.hpp"

#define FW_VERSION "1.1"
#define BAUD 921600
#define PIN_LED 4            // flash LED, kept dark unless "led <0..255>"
#define IN_MAX 96            // largest side of the fast-path detector input, px
// rot: 0/1/2/3 = x90 deg, 4 = auto.  clk: OV2640 CLKRC register (3 = driver default, 1 = sensor twice as fast).
// xclk: sensor clock, MHz.  in: fast-path input side, px.  fast: 1 = use the window around the face.  roi: window side / face size.
struct Cfg { uint8_t magic, rot, stages, led, clk, xclk, in, fast; float scale, score, roi; } cfg;
struct Face { bool ok; float x, y, w, h, score; };
const uint8_t MAGIC = 0x63;
Preferences prefs;
HumanFaceDetectMSR01 *s1 = nullptr, *s3 = nullptr; HumanFaceDetectMNP01 *s2 = nullptr;
bool camOk = false, psram = false, locked = false, wantFrame = false;
uint16_t *rbuf = nullptr, *rb2 = nullptr; int rcap = 0;
int confirm = 0, miss = 0, rotTry = 0, votes[4] = {0, 0, 0, 0};
float fx = 0, fy = 0, fsz = 0;
uint32_t pN = 0, pGrab = 0, pDet = 0, pRoi = 0, pT = 0;

void defaults() {
  cfg.magic = MAGIC; cfg.rot = 4; cfg.stages = 2; cfg.led = 0; cfg.clk = 3; cfg.xclk = 20; cfg.in = 56; cfg.fast = 1;
  cfg.scale = 0; cfg.score = 0.3f; cfg.roi = 1.8f;
}
void mk() {
  if (s1) delete s1; if (s2) delete s2; if (s3) delete s3;
  float sc = cfg.scale > 0.05f ? constrain(cfg.scale, 0.13f, 1.0f) : (psram ? 0.3f : 0.5f);     // below 0.13 the network input gets too small
  s1 = new HumanFaceDetectMSR01(cfg.score, 0.3F, 10, sc); s2 = new HumanFaceDetectMNP01(0.4F, 0.3F, 5);
  s3 = new HumanFaceDetectMSR01(cfg.score, 0.3F, 5, 1.0F);
}
void show() {
  Serial.printf("# cam %s: rot %d stages %d scale %.2f score %.2f led %d fast %d in %d roi %.2f xclk %d clk %d psram %d heap %u\n", FW_VERSION,
                cfg.rot, cfg.stages, cfg.scale, cfg.score, cfg.led, cfg.fast, cfg.in, cfg.roi, cfg.xclk, cfg.clk, psram, ESP.getFreeHeap());
}
void applyClk() { sensor_t *s = esp_camera_sensor_get(); if (s && s->set_reg) s->set_reg(s, 0x111, 0xff, cfg.clk); }

bool camInit() {
  camera_config_t c = {};
  c.ledc_channel = LEDC_CHANNEL_0; c.ledc_timer = LEDC_TIMER_0;
  c.pin_d0 = 5; c.pin_d1 = 18; c.pin_d2 = 19; c.pin_d3 = 21; c.pin_d4 = 36; c.pin_d5 = 39; c.pin_d6 = 34; c.pin_d7 = 35;
  c.pin_xclk = 0; c.pin_pclk = 22; c.pin_vsync = 25; c.pin_href = 23; c.pin_sccb_sda = 26; c.pin_sccb_scl = 27; c.pin_pwdn = 32; c.pin_reset = -1;
  c.xclk_freq_hz = constrain((int)cfg.xclk, 5, 24) * 1000000; c.pixel_format = PIXFORMAT_RGB565; c.jpeg_quality = 12;
  c.fb_count = psram ? 2 : 1; c.grab_mode = psram ? CAMERA_GRAB_LATEST : CAMERA_GRAB_WHEN_EMPTY;
  c.frame_size = psram ? FRAMESIZE_QVGA : FRAMESIZE_QQVGA; c.fb_location = psram ? CAMERA_FB_IN_PSRAM : CAMERA_FB_IN_DRAM;
  esp_err_t e = esp_camera_init(&c);
  if (e != ESP_OK) { Serial.printf("# camera init failed 0x%x (is the ribbon cable seated?)\n", e); esp_camera_deinit(); return false; }
  if (cfg.clk != 3) applyClk();
  Serial.printf("# camera ok, %s\n", psram ? "QVGA, PSRAM" : "QQVGA, no PSRAM");
  return true;
}
// rotate src (w x h) by k*90 deg clockwise into dst; returns the new width/height through nw/nh
void rotate(const uint16_t *s, uint16_t *d, int w, int h, int k, int &nw, int &nh) {
  if (k == 2) { nw = w; nh = h; int n = w * h; for (int i = 0; i < n; i++) d[n - 1 - i] = s[i]; return; }
  nw = h; nh = w;
  for (int y = 0; y < h; y++) for (int x = 0; x < w; x++) {
    if (k == 1) d[x * nw + (h - 1 - y)] = s[y * w + x]; else d[(w - 1 - x) * nw + y] = s[y * w + x];
  }
}
// Fast path: cut the square (x0, y0, side), given in upright picture coordinates, out of the raw frame (w x h, turned by
// k*90 deg) and shrink it to m x m. Every output pixel is the mean of 4 samples, which also takes some noise out.
void extract(const uint16_t *s, int w, int h, int k, float x0, float y0, float side, uint16_t *d, int m) {
  static int16_t tx[2 * IN_MAX], ty[2 * IN_MAX];
  int W = (k & 1) ? h : w, H = (k & 1) ? w : h; float st = side / m;
  for (int i = 0; i < 2 * m; i++) {
    tx[i] = constrain((int)(x0 + (i * 0.5f + 0.25f) * st), 0, W - 1);
    ty[i] = constrain((int)(y0 + (i * 0.5f + 0.25f) * st), 0, H - 1);
  }
  for (int j = 0; j < m; j++) for (int i = 0; i < m; i++) {
    int r = 0, g = 0, b = 0;
    for (int q = 0; q < 4; q++) {
      int X = tx[2 * i + (q & 1)], Y = ty[2 * j + (q >> 1)], x, y;
      switch (k) { case 1: x = Y; y = h - 1 - X; break; case 2: x = w - 1 - X; y = h - 1 - Y; break; case 3: x = w - 1 - Y; y = X; break; default: x = X; y = Y; }
      uint16_t v = s[y * w + x]; v = (uint16_t)((v << 8) | (v >> 8));        // the frame is RGB565, high byte first
      r += v >> 11; g += (v >> 5) & 63; b += v & 31;
    }
    uint16_t v = (uint16_t)(((r >> 2) << 11) | ((g >> 2) << 5) | (b >> 2));
    d[j * m + i] = (uint16_t)((v << 8) | (v >> 8));
  }
}
// best face out of the detector's list; boxes are mapped back to the upright picture: X = ox + x * sc
Face pick(std::list<dl::detect::result_t> &res, float ox, float oy, float sc, bool gate, int W, int &n) {
  Face best = {false, 0, 0, 0, 0, 0}; n = res.size(); float bc = 1e9;
  for (auto &r : res) {
    float x = ox + (r.box[0] + r.box[2]) * 0.5f * sc, y = oy + (r.box[1] + r.box[3]) * 0.5f * sc, w = (r.box[2] - r.box[0]) * sc, h = (r.box[3] - r.box[1]) * sc;
    if (w < 10 || h < 10) continue;
    float cost;
    if (gate) { float d = hypotf(x - fx, y - fy); if (d > 0.6f * W) continue; cost = d - 40.0f * r.score; } else cost = -(w * h) * r.score;
    if (cost < bc) { bc = cost; best = {true, x, y, w, h, r.score}; }
  }
  return best;
}
void sendFrame(const uint16_t *img, int W, int H) {      // at most 160 px on the long side, RGB565 big endian
  int st = (W > 160 || H > 160) ? 2 : 1, w = W / st, h = H / st;
  Serial.printf("#IMG %d %d %d\n", w, h, w * h * 2);
  for (int y = 0; y < h; y++) { static uint16_t line[160]; for (int x = 0; x < w; x++) line[x] = img[y * st * W + x * st]; Serial.write((uint8_t *)line, w * 2); }
  Serial.println();
}
void command(String s) {
  s.trim(); int sp = s.indexOf(' '); String c = sp < 0 ? s : s.substring(0, sp); float v = sp < 0 ? 0 : s.substring(sp + 1).toFloat();
  if (c == "frame") wantFrame = true;
  else if (c == "rot") { cfg.rot = constrain((int)v, 0, 4); memset(votes, 0, sizeof(votes)); locked = false; show(); }
  else if (c == "stages") { cfg.stages = constrain((int)v, 1, 3); show(); }
  else if (c == "scale") { cfg.scale = v; mk(); show(); }
  else if (c == "score") { cfg.score = v; mk(); show(); }
  else if (c == "led") { cfg.led = constrain((int)v, 0, 255); ledcWrite(2, cfg.led); show(); }
  else if (c == "fast") { cfg.fast = v > 0; show(); }
  else if (c == "in") { cfg.in = constrain((int)v, 40, IN_MAX); show(); }
  else if (c == "roi") { cfg.roi = constrain(v, 1.2f, 3.0f); show(); }
  else if (c == "clk") { cfg.clk = (uint8_t)constrain((int)v, 0, 255); applyClk(); show(); }
  else if (c == "xclk") { cfg.xclk = constrain((int)v, 5, 24); esp_camera_deinit(); camOk = camInit(); show(); }
  else if (c == "perf") {
    uint32_t dt = millis() - pT;
    if (pN && dt) Serial.printf("# perf frames %u fps %.1f grab %.1f ms detect %.1f ms fast %u%%\n", pN, pN * 1000.0f / dt, pGrab / 1000.0f / pN, (float)pDet / pN, pRoi * 100 / pN);
    pN = pGrab = pDet = pRoi = 0; pT = millis();
  }
  else if (c == "save") { prefs.putBytes("cfg", &cfg, sizeof(cfg)); Serial.println("# cam saved"); }
  else if (c == "defaults") { defaults(); mk(); esp_camera_deinit(); camOk = camInit(); show(); }
  else if (c == "show") show();
}
void setup() {
  WRITE_PERI_REG(RTC_CNTL_BROWN_OUT_REG, 0);
  Serial.begin(BAUD); delay(100);
  prefs.begin("ftc", false);
  if (prefs.getBytes("cfg", &cfg, sizeof(cfg)) != sizeof(cfg) || cfg.magic != MAGIC) defaults();
  ledcSetup(2, 5000, 8); ledcAttachPin(PIN_LED, 2); ledcWrite(2, cfg.led);
  psram = psramFound() && ESP.getPsramSize() > 1000000 && ESP.getFreePsram() > 500000;
  rb2 = (uint16_t *)heap_caps_malloc(IN_MAX * IN_MAX * 2, MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT);
  Serial.println("\n# FaceTracker cam " FW_VERSION); mk(); camOk = camInit(); show(); pT = millis();
}
void loop() {
  static String line;
  while (Serial.available()) { char ch = Serial.read(); if (ch == '\n' || ch == '\r') { if (line.length()) command(line); line = ""; } else if (line.length() < 40) line += ch; }
  if (!camOk) { static uint32_t t = 0; if (millis() - t > 3000) { t = millis(); camOk = camInit(); } delay(20); return; }
  uint32_t ta = micros();
  camera_fb_t *fb = esp_camera_fb_get();
  if (!fb) { Serial.println("# frame timeout"); delay(50); return; }
  uint32_t tb = micros();
  int fw = fb->width, fh = fb->height, k = cfg.rot == 4 ? (rotTry & 3) : cfg.rot;
  if (k && rcap < fw * fh) { if (rbuf) free(rbuf); rbuf = (uint16_t *)(psram ? ps_malloc(fw * fh * 2) : malloc(fw * fh * 2)); rcap = rbuf ? fw * fh : 0; }
  if (k && !rbuf) k = 0;
  int W = (k & 1) ? fh : fw, H = (k & 1) ? fw : fh, n = 0;
  bool roi = cfg.fast && locked && miss == 0 && fsz > 8 && rb2 && !wantFrame;
  Face f; uint32_t t0 = millis();
  if (roi) {                                             // fast path: only the window around the face
    int m = cfg.in;
    float side = constrain(cfg.roi * fsz, 64.0f, (float)min(W, H));
    float x0 = constrain(fx - side * 0.5f, 0.0f, W - side), y0 = constrain(fy - side * 0.5f, 0.0f, H - side);
    extract((uint16_t *)fb->buf, fw, fh, k, x0, y0, side, rb2, m);
    esp_camera_fb_return(fb);                            // hand the buffer back at once: the sensor keeps the newest frame ready
    std::vector<int> shape = {m, m, 3};
    f = pick(s3->infer(rb2, shape), x0, y0, side / m, true, W, n);
  } else {                                               // whole picture: looking for a face, or re-finding it after a miss
    uint16_t *img = (uint16_t *)fb->buf;
    if (k) { int nw, nh; rotate((uint16_t *)fb->buf, rbuf, fw, fh, k, nw, nh); img = rbuf; esp_camera_fb_return(fb); fb = nullptr; }
    bool two = cfg.stages == 3 || (cfg.stages == 2 && !locked);
    std::vector<int> shape = {H, W, 3};
    std::list<dl::detect::result_t> *res = &s1->infer(img, shape);
    if (two && res->size() > 0) res = &s2->infer(img, shape, *res);
    f = pick(*res, 0, 0, 1, locked, W, n);
    if (wantFrame) { wantFrame = false; sendFrame(img, W, H); }
    if (fb) esp_camera_fb_return(fb);
  }
  uint32_t ms = millis() - t0;
  pN++; pGrab += tb - ta; pDet += ms; if (roi) pRoi++;
  if (f.ok) {
    if (cfg.rot == 4 && ++votes[k] >= 3) { cfg.rot = k; prefs.putBytes("cfg", &cfg, sizeof(cfg)); Serial.printf("# picture orientation found: rot %d\n", k); }
    float sz = max(f.w, f.h);
    fx = constrain(f.x, 0.0f, (float)W); fy = constrain(f.y, 0.0f, (float)H); fsz = (locked && fsz > 8) ? 0.6f * fsz + 0.4f * sz : sz; miss = 0;
    if (!locked && ++confirm >= 2) locked = true;
    if (locked) { Serial.printf("F %d %d %d %d %d %d %u\n", (int)f.x, (int)f.y, (int)f.w, (int)(f.score * 100), W, H, ms); return; }
  } else {
    if (cfg.rot == 4 && !locked) rotTry++;
    confirm = 0; if (locked && ++miss > 12) { locked = false; fsz = 0; }
  }
  Serial.printf("N %d %d %u\n", W, H, ms);
}

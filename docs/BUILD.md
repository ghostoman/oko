# Build OKO-1

> The same guide lives at https://sdtech.page/oko/build/ with pictures and copy buttons.

One evening, no soldering, about 976 ₴ in Ukraine or $24 worldwide in parts (prices checked 17 Nov 2026), plus a PETG-capable 3D printer and the webcam you already own.

## 0. Parts

| Part | Qty | ₴ (Ukraine) | $ (global) | Note |
|---|---|---|---|---|
| ESP32 DevKit (ESP32-WROOM-32) | 1 | 245 | 6.00 | Main board: servo control and USB power |
| ESP32-CAM AI-Thinker + OV2640 | 1 | 281 | 7.00 | Tracking eye: on-device face detection |
| MG90S metal-gear micro servo | 2 | 198 | 5.18 | Pan and tilt |
| Dupont jumpers 20 cm (F-F + M-F) | 1 | 150 | 3.00 | 4 to the camera, 2 per servo |
| WAGO 221-413 lever connector | 1 | 22 | 0.60 | Splits USB 5 V to both servos |
| PETG filament, 134 g of a 1 kg spool | 1 | 80 | 2.00 | Whole kit, one plate, no supports |
| Screws M2.5-M3 x 8-10 mm | 4 | - | - | Plus the screws from the servo bags |

Any ESP32-WROOM-32 DevKit works (developed on a keyestudio ESP32). Use an AI-Thinker ESP32-CAM with OV2640; working PSRAM gives 320x240 tracking, without it the camera falls back to 160x120. Recommended: a 470-1000 µF capacitor across 5 V and GND if your laptop's USB port sags when the servos move.

## 1. Print

Files: `hardware/print/` (Bambu Studio projects, sliced for P1S / X1C) or `hardware/stl/` for any slicer. Print `OKO-1_fit_test_PETG_P1S.gcode.3mf` first (about 1 h 46 min): it checks the lid clip, the webcam rib and the camera mask.

| Setting | Value |
|---|---|
| Material | PETG, any colour (black for the look) |
| Base profile | 0.20 mm Standard (Bambu P1S / X1C) |
| Walls / infill | 4 walls, 20 % gyroid |
| Nozzle | 245 °C, first layer 250 °C |
| Plate | Textured PEI, 4 mm brim, elephant foot 0.15 mm |
| Supports | None. Every part is already oriented. |
| Time / weight | 5 h 16 min, 134 g for the full kit |

| Part | On the bed | Note |
|---|---|---|
| Housing (`housing`) | Front wall down | Holds the main ESP32, the pan servo and the WAGO. Rails for the lid clip print on the bed. |
| Rear cover (`cover`) | Flat | Posts hold the ESP32 and the servo in place. |
| Laptop lid clip (`lid_clip`) | Standing on its end | Hook profile lies in the layer plane, so it is strong. 7.8 mm slot for a 7.3 mm lid. |
| Yoke (pan) (`yoke`) | On its back | Uprights are strong along the layers. |
| Head (tilt) (`head`) | Rib down | The pivot trunnion sits on its flat face, so it prints round. |
| Camera mask (`shroud`) | Face down | Front face gets the bed texture and the engraved reticle. |
| Tilt servo cap (`servo_cap`) | Bottom down | Press fit, optional. Wire slots on both ends. |
| Desk stand (optional) (`desk_foot`) | Flat | Turns the laptop mount into a desk unit. |
| Shims 0.2 / 0.4 / 0.6 mm (`shims`) | Flat | Only if the yoke has vertical play. |

Neon: press any 1.75 mm filament into the 1.8 x 1.4 mm grooves. The print stays single colour.

## 2. Flash

Arduino core **esp32 2.0.17** (the face-detection headers are gone in 3.x).

- Main board: `tools\flash.ps1 main` or Arduino IDE, board "ESP32 Dev Module", sketch `firmware/FT_main`.
- Camera: `tools\flash_cam_bridge.ps1` flashes the ESP32-CAM through the main board (bridge mode), no programmer needed. Put a jumper from the **camera** IO0 to GND and press RST on the camera when asked. With an ESP32-CAM-MB programmer instead: `tools\flash.ps1 cam`.
- Arduino IDE for the camera: board "ESP32 Dev Module", PSRAM: Enabled, Partition Scheme: Huge APP, sketch `firmware/FT_cam`.

```bash
arduino-cli core install esp32:esp32@2.0.17 --additional-urls https://espressif.github.io/arduino-esp32/package_esp32_index.json
arduino-cli compile --fqbn esp32:esp32:esp32 firmware/FT_main
arduino-cli upload  --fqbn esp32:esp32:esp32 -p /dev/ttyUSB0 firmware/FT_main
arduino-cli compile --fqbn esp32:esp32:esp32:PSRAM=enabled,PartitionScheme=huge_app --output-dir build/FT_cam firmware/FT_cam
```

## 3. Wire

All four camera wires sit on one pin row of the ESP32-CAM (3V3, IO16, IO0, **GND**, VCC, **U0R**, **U0T**, GND).

| ESP32-CAM | Main ESP32 | Wire |
|---|---|---|
| 3V3 | 3V3 | Dupont F-F 20 cm |
| GND (next to IO0) | GND | F-F |
| U0T | IO16 | F-F |
| U0R | IO17 | F-F |

| Servo | Orange (signal) | Brown (GND) | Red (+5 V) |
|---|---|---|---|
| Pan (in housing) | IO18 | GND | WAGO |
| Tilt (on yoke) | IO19 | GND | WAGO |

- 5 V comes from USB: the main board's 5V pin goes into the WAGO together with both red servo leads (pull the red lead out of the servo plug, or cut and strip it).
- Signal and ground: male-to-female Dupont jumpers.
- The camera runs from 3V3; its 5 V pin stays empty.
- Leave a 6-7 cm loop through the deck port so the head turns freely.

## 4. Assemble

Hardware: 2 servo-bag screws for the tilt servo tabs, the pan horn screw, 4 self-tapping screws M2.5-M3 x 8-10 mm, one WAGO 221-413.

1. **Flash both boards.** Flash the main ESP32 over its own USB, then flash the ESP32-CAM through it (bridge mode, no extra programmer). Power the main board with servos attached: both go to centre (1500 µs). Fit the horns only on centred servos.
2. **Pan servo into the housing.** Slide the pan servo in from the back, tabs into the slots, shaft up. Its lead leaves on the shaft side and drops down into the bay.
3. **Main ESP32 on its posts.** Lay the main board on 4 posts: USB into the right-hand window, the USB edge under two hooks, pins facing back.
4. **Yoke on the deck ring.** Put the yoke on the deck ring, uprights up, square to the housing. Drop the double horn into its pocket and onto the shaft, tighten the centre screw. It must turn by hand without vertical play. If it rattles, add a 0.2 / 0.4 / 0.6 mm shim.
5. **Head into the yoke.** Press the second horn into the pocket on the right cheek of the head. Put the head trunnion into the hole of the left upright.
6. **Tilt servo.** Insert the tilt servo from outside into the right upright window, shaft into the horn, lead up. Two screws into the tabs. The head rib must stand vertical. Press the servo cap on top.
7. **ESP32-CAM on the head.** Push the 4 wires onto the lower pin row, then place the board on the 4 rib posts with the camera forward. Seen from the front the lens is on the right. The upper pin row goes into the rib slot; wires leave backwards under the rib.
8. **Camera mask.** Slide the mask up along the cheek guides until the square lens head sits in its window. Two screws from below.
9. **Wires and power.** Route the wires through the deck port (rear left), leave a 6-7 cm loop so the head turns freely. Plug them per the wiring tables, all red servo leads and the 5 V lead into the WAGO. Close the cover, 2 screws.
10. **Lid clip.** Slide the clip onto the housing from below until it stops. The weight of the device locks it.
11. **Neon (optional).** Press any 1.75 mm filament into the 1.8 x 1.4 mm grooves for the neon lines. A drop of glue if loose. The print itself stays single colour.
12. **Mount and plug in.** Hang it on the laptop lid, clip your webcam onto the head rib like onto a monitor edge, plug in both USB cables. Sit in front of it: the head finds your face and centres it.

## 5. First run

Serial monitor on the main board at 921600 baud, type `status`: `LOCK` = face found, `SEARCH` = looking, `NOLINK` = no data from the camera. A desktop monitor with live picture: `python tools/ft_monitor.py` (needs `pyserial`).

| Symptom | Fix |
|---|---|
| NOLINK in the monitor | No data from the ESP32-CAM. Check the 4 camera wires: U0T to IO16, U0R to IO17. |
| “frame timeout” from the camera | The sensor stopped delivering frames. Unplug USB for 5 s. If it repeats, reseat the camera ribbon: lift the latch, push the ribbon fully in, close the latch. |
| A servo runs away from the face | Type `flip pan` or `flip tilt`, then `save`. |
| Face is off-centre in your webcam | The webcam sits beside the tracking camera. Shift the aim: `set aimx -4.8` / `set aimy 4` (degrees), then `save`. |
| USB drops while servos move | The laptop port sags. Add a 470-1000 µF capacitor across 5 V / GND, or use a powered hub. |
| Moves feel too soft or too sharp | `set smooth 500` sets the eased move time in ms (0 = direct). |

### Commands

| Command | What it does |
|---|---|
| `status` | Live state: LOCK / SEARCH / NOLINK, angles, fps |
| `track 0 / 1` | Tracking off / on |
| `center` | Both servos to the middle (for fitting the horns) |
| `pan <deg> / tilt <deg>` | Manual move |
| `flip pan | tilt` | Reverse an axis |
| `set kp | dead | speed | smooth | aimx | aimy …` | Tuning; `show` lists everything |
| `cam <rot | score | in | roi | perf …>` | ESP32-CAM settings, passed through |
| `bridge` | USB ↔ camera link for flashing the ESP32-CAM |
| `log` | Last 256 camera reports with servo angles |
| `save` | Store settings in flash |

Reference build settings: kp 0.85, dead 1.5°, speed 180°/s, lag 120 ms, smooth 500 ms, tilt min −65°; camera in 72, roi 2.4, score 0.2, xclk 20 MHz.

## FAQ

**Does it work with any webcam?**
Yes. OKO-1 does not use your webcam for tracking at all. A separate ESP32-CAM on the head finds your face, and your webcam just rides on top and stays plugged into the laptop as usual. Anything with a monitor-style clip fits the head rib; it was developed with a Logitech Brio 100.

**Is my video sent anywhere?**
No. Face detection runs on the ESP32-CAM chip itself. Wi-Fi and Bluetooth are never started in the firmware, the tracking camera only sends face coordinates over two wires to the main board, and your webcam picture never touches OKO-1.

**How fast does it track?**
About 7.2 face detections per second on the ESP32-CAM, measured on hardware. Between detections the servos move with critically damped easing, so motion stays smooth instead of jerky.

**What do I need to build one?**
A 3D printer (PETG), an ESP32 DevKit, an ESP32-CAM with OV2640, two MG90S servos, a few Dupont wires and a WAGO connector. About $21-24 in parts. No soldering and no separate programmer.

**Can I use it on a desk instead of a laptop?**
Yes. Print the optional desk stand and slide the housing into it.

**What is the licence?**
Firmware and code are MIT. 3D models, print files and documentation are CC BY 4.0. Build it, sell it, remix it; keep the credit to SDTech / Serhii Dovhyi.

**Can I hire SDTech to build something like this?**
Yes. SDTech designs AI-driven devices, firmware, 3D-printed enclosures and the websites that launch them. Write to sergey@sdtech.page.

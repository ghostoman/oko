"""FaceTracker: all dimensions in mm.

World frame (device mounted on the laptop lid, lid modelled vertical):
  X = sideways, Y = towards the user (camera looks +Y), Z = up.
  Origin = centre of the lid's top edge, front face of the lid at y = 0.
Measured by the user 2026-11-13 are marked MEASURED.
"""
# ---------------------------------------------------------------- laptop lid
LID_T = 7.3            # MEASURED lid thickness at the screen
BEZEL = 6.75           # MEASURED top bezel (lid edge -> active screen)
SLOT_CLR = 0.25        # clearance each side of the lid in the clip slot
LIP_T = 2.4            # front lip thickness
LIP_H = 6.0            # front lip height (< BEZEL so the screen is never covered)
BR_T = 4.0             # bridge thickness over the lid edge
CP_T = 3.0             # clip rear plate thickness
CP_Z = -44.0           # clip rear plate bottom

# ---------------------------------------------------------------- housing
WF = 4.2               # housing front wall (carries the dovetail slots)
WS = 2.4               # side / bottom walls
HWI = 28.0             # interior half width
DEPTH_I = 36.0         # interior depth (front wall -> cover)
COVER_T = 2.0
Z_TOP = 4.0            # deck = clip bridge top
Z_SLAB = -2.3          # underside of the deck slab
Z_BOT_I = -54.4        # interior floor

S0 = -(LID_T + SLOT_CLR)          # slot rear face  (-7.55)
S1 = SLOT_CLR                     # slot front face ( 0.25)
YF = S0 - CP_T                    # housing front face (-10.55)
YI0 = YF - WF                     # interior front (-14.75)
YI1 = YI0 - DEPTH_I               # interior rear  (-50.75)
YR = YI1 - COVER_T                # cover outer face
HWO = HWI + WS                    # outer half width (30.4)
Z_BOT = Z_BOT_I - WS

# ---------------------------------------------------------------- MG90S (values proven in H0-P v2)
MG = dict(L=22.8, W=12.2, H_body=22.7, tab_z0=15.7, tab_t=2.5, tab_L=32.5,
          hole_dx=27.6, shaft_off=5.9, boss_d=11.8, boss_h=4.0, spline_d=4.8, spline_h=3.0,
          horn_L=34.0, horn_w=6.2, horn_hub_d=7.2, horn_t=1.9, horn_extra=4.0,
          boss2_off=6.5, boss2_r=2.9)     # second, smaller bump on the case top (idler gear), next to the shaft boss towards the body
BOSS2_X1 = 10.5                    # housing: far wall of the passage for that bump (bump ends at about 9.4 from the shaft)
MG_TAB_TOP = MG['tab_z0'] + MG['tab_t']               # 18.2 bottom -> mount plane
MG_CASE = MG['H_body'] - MG_TAB_TOP                   # 4.5  mount plane -> case top
MG_BOSS = MG_CASE + MG['boss_h']                      # 8.5
MG_TIP = MG_BOSS + MG['spline_h']                     # 11.5
MG_HORN_FACE = MG_TIP + 0.6 + MG['horn_extra']        # 16.1 outer face of the horn arms
MG_HORN_ARM0 = MG_HORN_FACE - MG['horn_t']            # 14.2 inner face of the horn arms
MG_XC = MG['L'] / 2 - MG['shaft_off']                 # 5.5 body centre from the shaft

# ---------------------------------------------------------------- pan axis
YP = -24.0             # pan axis Y
ZM = -7.1              # pan servo mount plane (top of the tabs)
RING_R0, RING_R1, RING_H = 11.5, 16.5, 0.6
YOKE_Z0 = Z_TOP + RING_H          # yoke beam underside (4.6)
YOKE_FLOOR = ZM + MG_HORN_ARM0 - 0.5   # floor under the horn arms (6.6)
YOKE_Z1 = 9.3                     # beam top
YOKE_HW = 11.0                    # beam / arm half width (Y)
ARM_T = 3.2

# ---------------------------------------------------------------- tilt axis / head
ZA = 38.0              # tilt axis height
CHEEK_X0, CHEEK_X1 = 22.8, 26.8
HORN_POCKET = 2.2
ARM_R_OUT = CHEEK_X1 - HORN_POCKET + MG_HORN_FACE     # tilt servo mount plane = right arm outer face (40.7)
ARM_R_IN = ARM_R_OUT - ARM_T                          # 37.5
ARM_L_IN = -(CHEEK_X1 + 0.6)                          # -27.4
ARM_L_OUT = ARM_L_IN - ARM_T                          # -30.6
TRUN_R = 6.5           # > |FIN_Y0|: the trunnion is printed lying on the bed and gets a real flat there (v1.2)
TRUN_C = 0.3           # radial clearance of the pivot hole
FIN_Y0, FIN_Y1 = -5.0, 4.0
FIN_Z0, FIN_Z1 = -17.0, 18.0                          # fin = "monitor edge" for the webcam clip (35 mm tall)
FING_Z0 = -21.6                                       # two fingers under the fin (PCB pads + shroud screws)
FING_L, FING_R = -17.4, 13.0                          # between them: free passage for the 4 Dupont wires

# ESP32-CAM (AI-Thinker layout, 40.5 x 27), landscape, camera side forward, wired pin row (3V3..U0T) at the bottom
CB_L, CB_W, CB_T = 40.5, 27.0, 1.6
CB_Y0 = 9.0                        # PCB back face (head frame): 5 mm for the ESP-32S can
CB_Z0 = -21.2                      # PCB bottom edge
CB_Z1 = CB_Z0 + CB_W               # 5.8
CB_LENS_X = -(CB_L / 2 - 9.0)      # lens 9 mm from the camera end (-11.25)
CB_LENS_Z = (CB_Z0 + CB_Z1) / 2    # -7.7
CB_PIN0 = -CB_L / 2 + 4.9          # first pin of each row (camera end), 2.54 pitch, 8 pins
CB_ROW = 2.07                      # pin row from the board edge
CB_LED = (16.3, CB_Z0 + 3.5)       # flash LED

SH_HW = 22.5                       # camera pod half width
SH_Y0 = CB_Y0 + 0.2
SH_Y1 = CB_Y0 + CB_T + 5.1 + 1.6   # front face (17.3)
SH_Z0, SH_Z1 = CB_Z0 - 1.9, CB_Z1 + 1.9
FLANGE_Z0 = FING_Z0 - 2.5

# ---------------------------------------------------------------- ESP32 (keyestudio 38 pin)
ESP_L, ESP_W = 55.0, 25.8          # MEASURED
ESP_STACK = 24.0                   # MEASURED: board + pins + plugged Dupont housings
ESP_PAD = 6.0                      # stand-off from the front wall (component side)
ESP_ZC = -40.9
ESP_Y_TOP = YI0 - ESP_PAD          # PCB component face (-20.75)

# ---------------------------------------------------------------- webcam (Logitech Brio 100)
CAM_W, CAM_H, CAM_D = 72.9, 31.8, 18.7     # 31.8 / 18.7 MEASURED, width from the Logitech sheet
CLIP_W = 40.3                      # MEASURED top plate of the webcam clip
FLAP_W = 36.12                     # MEASURED rear flap
LIP_DROP = 2.17                    # MEASURED front lip
NEON_W, NEON_D = 1.8, 1.4          # channel for a 1.75 mm filament strand ("neon" inlay)

# ---------------------------------------------------------------- fasteners / fits
PILOT = 2.3            # self-tapping M2.5-M3 (same as H0-P v2)
CLEAR = 3.3
PILOT_SERVO = 1.7      # screws from the servo bag
CLR = 0.3

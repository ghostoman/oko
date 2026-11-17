# -*- coding: utf-8 -*-
"""OKO-1 monitor: picture from the ESP32-CAM, face box, servo angles and setup buttons. Needs pyserial + tkinter."""
import sys, threading, queue, json, time
import tkinter as tk
import serial, serial.tools.list_ports

BAUD = 921600
Z = 3


def find_port():
    for p in serial.tools.list_ports.comports():
        d = (p.description or '') + ' ' + (p.manufacturer or '')
        if any(k in d for k in ('CH340', 'CH910', 'CP210', 'USB Serial', 'USB-SERIAL', 'Silicon')):
            return p.device
    ps = list(serial.tools.list_ports.comports())
    return ps[0].device if ps else None


class App:
    def __init__(self, root, port):
        self.root = root; self.q = queue.Queue(); self.live = False; self.st = {}; self.img = None; self.wh = (160, 120)
        self.ser = serial.Serial(); self.ser.port = port; self.ser.baudrate = BAUD; self.ser.timeout = 0.3
        self.ser.dtr = False; self.ser.rts = False          # do not reset the ESP32 when the port opens
        self.ser.open()
        root.title('OKO-1 monitor  ' + port); root.configure(bg='#0f1012')
        self.cv = tk.Canvas(root, width=160 * Z, height=160 * Z, bg='#16181b', highlightthickness=0); self.cv.grid(row=0, column=0, rowspan=3, padx=10, pady=10)
        self.cv.create_text(240, 180, text='Press "Frame" or "Live view"', fill='#8b9099', tags='hint')
        self.lab = tk.Label(root, text='...', justify='left', font=('Consolas', 11), fg='#e9eaec', bg='#0f1012', width=30, anchor='nw'); self.lab.grid(row=0, column=1, sticky='nw', pady=10)
        bf = tk.Frame(root, bg='#0f1012'); bf.grid(row=1, column=1, sticky='nw')
        btns = [('Frame', lambda: self.cmd('frame')), ('Live view', self.toggle_live), ('Tracking ON', lambda: self.cmd('track 1')), ('Tracking OFF', lambda: self.cmd('track 0')),
                ('Centre (for assembly)', lambda: self.cmd('center')), ('Reverse pan', lambda: self.cmd('flip pan')), ('Reverse tilt', lambda: self.cmd('flip tilt')),
                ('Image: rotate 90°', self.rot90), ('Image: auto', lambda: self.cmd('cam rot 4')), ('Save settings', lambda: self.cmd('save'))]
        for i, (t, f) in enumerate(btns):
            tk.Button(bf, text=t, command=f, width=22, bg='#1f2226', fg='#e9eaec', activebackground='#ff3a26', relief='flat').grid(row=i // 2, column=i % 2, padx=3, pady=3)
        ef = tk.Frame(root, bg='#0f1012'); ef.grid(row=2, column=1, sticky='sw', pady=6)
        self.ent = tk.Entry(ef, width=34, bg='#16181b', fg='#e9eaec', insertbackground='#fff'); self.ent.grid(row=0, column=0, padx=3)
        self.ent.bind('<Return>', lambda e: (self.cmd(self.ent.get()), self.ent.delete(0, 'end')))
        tk.Label(ef, text='command + Enter (help)', fg='#8b9099', bg='#0f1012').grid(row=1, column=0, sticky='w')
        self.log = tk.Text(root, height=9, width=96, bg='#16181b', fg='#b9bdc4', font=('Consolas', 9), relief='flat'); self.log.grid(row=3, column=0, columnspan=2, padx=10, pady=(0, 10))
        threading.Thread(target=self.reader, daemon=True).start()
        self.cmd('stream 1'); self.root.after(40, self.pump)

    def cmd(self, s):
        try: self.ser.write((s.strip() + '\n').encode())
        except Exception as e: self.q.put(('log', 'serial: %s' % e))

    def rot90(self):
        self.rot = (getattr(self, 'rot', 0) + 1) % 4; self.cmd('cam rot %d' % self.rot)

    def toggle_live(self):
        self.live = not self.live
        if self.live: self.cmd('frame')

    def reader(self):
        buf = b''
        while True:
            try:
                line = self.ser.readline()
            except Exception as e:
                self.q.put(('log', 'serial: %s' % e)); time.sleep(1); continue
            if not line: continue
            if line.startswith(b'#IMG'):
                try:
                    _, w, h, n = line.split(); w, h, n = int(w), int(h), int(n)
                    data = b''
                    t0 = time.time()
                    while len(data) < n and time.time() - t0 < 3: data += self.ser.read(n - len(data))
                    if len(data) == n: self.q.put(('img', (w, h, data)))
                except Exception as e:
                    self.q.put(('log', 'bad frame: %s' % e))
            elif line.startswith(b'#S '):
                try: self.q.put(('st', json.loads(line[3:].decode('ascii', 'ignore'))))
                except Exception: pass
            else:
                t = line.decode('utf-8', 'ignore').rstrip()
                if t: self.q.put(('log', t))

    def show(self, w, h, d):
        out = bytearray(w * h * 3); j = 0
        for i in range(0, w * h * 2, 2):
            p = (d[i] << 8) | d[i + 1]
            out[j] = (p >> 8) & 0xF8; out[j + 1] = (p >> 3) & 0xFC; out[j + 2] = (p << 3) & 0xF8; j += 3
        self.img = tk.PhotoImage(data=b'P6 %d %d 255\n' % (w, h) + bytes(out)).zoom(Z); self.wh = (w, h)
        self.cv.delete('all'); self.cv.create_image(0, 0, anchor='nw', image=self.img); self.box()

    def box(self):
        self.cv.delete('ov'); w, h = self.wh
        self.cv.create_line(w * Z / 2 - 8, h * Z / 2, w * Z / 2 + 8, h * Z / 2, fill='#ffffff', tags='ov'); self.cv.create_line(w * Z / 2, h * Z / 2 - 8, w * Z / 2, h * Z / 2 + 8, fill='#ffffff', tags='ov')
        s = self.st
        if s.get('st') == 'LOCK':
            x, y, ww = s.get('x', 0) * w * Z, s.get('y', 0) * h * Z, s.get('w', 0) * w * Z
            self.cv.create_rectangle(x - ww / 2, y - ww * .6, x + ww / 2, y + ww * .6, outline='#ff3a26', width=2, tags='ov')

    def pump(self):
        try:
            while True:
                k, v = self.q.get_nowait()
                if k == 'img':
                    self.show(*v)
                    if self.live: self.cmd('frame')
                elif k == 'st':
                    self.st = v; self.box()
                    self.lab.config(text='state      %s\nfaces      %s\npan        %+.1f°\ntilt       %+.1f°\nframes/s   %.1f\ndetector   %s ms\nsigns      pan %s  tilt %s\n\nNOLINK = no data from the ESP32-CAM' % (
                        v.get('st'), v.get('n'), v.get('pan', 0), v.get('tilt', 0), v.get('fps', 0), v.get('ms'), v.get('pd'), v.get('td')))
                else:
                    self.log.insert('end', v + '\n'); self.log.see('end')
        except queue.Empty:
            pass
        self.root.after(40, self.pump)


if __name__ == '__main__':
    port = sys.argv[1] if len(sys.argv) > 1 else find_port()
    if not port:
        print('ESP32 not found: plug it in by USB'); sys.exit(1)
    r = tk.Tk(); App(r, port); r.mainloop()

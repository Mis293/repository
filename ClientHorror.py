"""
╔══════════════════════════════════════════════════════════════════════════╗
║  HORROR LAN — CLIENT  v4.0  ULTRA EDITION  (FIXED)                      ║
║                                                                          ║
║  Управление:                                                             ║
║  WASD / стрелки — движение                                               ║
║  SHIFT         — спринт (громко, быстро)                                 ║
║  CTRL          — тихий шаг (тихо, медленно)                              ║
║  P / ESC       — пауза                                                   ║
║  ENTER         — начать игру                                             ║
║  F11           — полноэкранный режим                                     ║
║  TAB           — статистика                                              ║
║  M             — развернуть мини-карту                                   ║
║                                                                          ║
║  pip install pygame                                                      ║
╚══════════════════════════════════════════════════════════════════════════╝
"""

import pygame
import socket
import threading
import json
import math
import time
import random
import sys
import os

# ══════════════════════════════════════════════════════════════
#  КОНФИГУРАЦИЯ
# ══════════════════════════════════════════════════════════════

PORT         = 5555
DEFAULT_HOST = "127.0.0.1"
FPS          = 60
WIN_W        = 1280
WIN_H        = 720

FLASHLIGHT_RADIUS   = 190
FLASHLIGHT_MONSTER  = 9999
DARKNESS_ALPHA      = 210
CAM_LERP            = 8.0
CAM_SHAKE_DECAY     = 6.0

# ── ЦВЕТОВАЯ ПАЛИТРА ────────────────────────────────────────
C_BG        = (6,   6,  12)
C_FLOOR_A   = (22,  22, 34)
C_FLOOR_B   = (18,  18, 28)
C_FLOOR_C   = (28,  28, 42)
C_WALL      = (38,  38, 56)
C_WALL_TOP  = (55,  55, 80)
C_WALL_EDGE = (70,  70, 100)

C_ME        = (80,  200, 255)
C_SURV      = (60,  195, 90)
C_MONSTER   = (210, 30,  30)
C_MONSTER_G = (255, 80,  80)
C_DEAD      = (75,  75,  90)
C_AI_MONSTER= (230, 20,  20)

C_KEY       = (255, 215, 0)
C_KEY_GLOW  = (255, 180, 0)
C_DOOR      = (0,   200, 210)
C_DOOR_OPEN = (0,   255, 180)
C_TRAP      = (200, 60,  180)
C_TRAP_ACT  = (255, 100, 220)
C_NOISE     = (255, 130, 20)

C_HUD_BG    = (8,   8,  16)
C_HUD_TEXT  = (195, 195, 215)
C_RED       = (220, 35,  35)
C_GREEN     = (60,  205, 75)
C_YELLOW    = (255, 195, 25)
C_CYAN      = (70,  195, 255)
C_WHITE     = (255, 255, 255)
C_GRAY      = (110, 110, 130)
C_DARK_GRAY = (50,  50,  65)
C_BLACK     = (0,   0,   0)
C_ORANGE    = (255, 140, 30)

MM_BG       = (10,  10,  20)
MM_WALL     = (55,  75,  140)
MM_SURV     = (60,  205, 85)
MM_ME       = (80,  200, 255)
MM_MONSTER  = (220, 40,  40)
MM_KEY      = (255, 215, 0)
MM_DOOR     = (0,   200, 210)
MM_TRAP     = (200, 60,  180)
MM_FOG      = (18,  18,  30)

# ══════════════════════════════════════════════════════════════
#  КЕШ ШРИФТОВ (FIX #1: prevent SysFont creation every frame)
# ══════════════════════════════════════════════════════════════

_font_cache = {}

def get_font(name, size, bold=False):
    key = (name, size, bold)
    if key not in _font_cache:
        _font_cache[key] = pygame.font.SysFont(name, size, bold=bold)
    return _font_cache[key]


# ══════════════════════════════════════════════════════════════
#  ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ══════════════════════════════════════════════════════════════

def dist(ax, ay, bx, by):
    return math.hypot(ax - bx, ay - by)

def lerp(a, b, t):
    return a + (b - a) * t

def clamp(v, lo, hi):
    return max(lo, min(hi, v))

def hsv_to_rgb(h, s, v):
    if s == 0:
        r = g = b = v
        return int(r*255), int(g*255), int(b*255)
    i = int(h * 6)
    f = h * 6 - i
    p = v * (1 - s)
    q = v * (1 - f * s)
    t_ = v * (1 - (1 - f) * s)
    i %= 6
    if i == 0: r, g, b = v, t_, p
    elif i == 1: r, g, b = q, v, p
    elif i == 2: r, g, b = p, v, t_
    elif i == 3: r, g, b = p, q, v
    elif i == 4: r, g, b = t_, p, v
    else: r, g, b = v, p, q
    return int(r*255), int(g*255), int(b*255)


def blend_color(c1, c2, t):
    return tuple(int(c1[i] * (1-t) + c2[i] * t) for i in range(3))


# ══════════════════════════════════════════════════════════════
#  СЕТЕВОЙ КЛИЕНТ
# ══════════════════════════════════════════════════════════════

class NetworkClient:
    def __init__(self, host):
        self.host     = host
        self.pid      = None
        self.map_w    = 2400
        self.map_h    = 1800
        self.ai_mode  = False
        self.version  = "?"
        self.alive    = False
        self._sock    = None
        self._state   = None
        self._lock    = threading.Lock()
        self._buf     = ""
        self._ping    = 0
        self._ping_ts = 0.0
        self._ping_interval = 2.0
        self._ping_timer = 0.0

    def connect(self):
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._sock.settimeout(6.0)
            self._sock.connect((self.host, PORT))
            self._sock.settimeout(None)
            self.alive = True
            threading.Thread(target=self._recv_loop, daemon=True).start()
            return True
        except Exception as e:
            print(f"[NET] Connection error: {e}")
            return False

    def _recv_loop(self):
        while self.alive:
            try:
                chunk = self._sock.recv(32768)
                if not chunk:
                    break
                self._buf += chunk.decode("utf-8", errors="ignore")
                while "\n" in self._buf:
                    line, self._buf = self._buf.split("\n", 1)
                    self._on_msg(line.strip())
            except Exception:
                break
        self.alive = False

    def _on_msg(self, raw):
        if not raw:
            return
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            return
        t = msg.get("type")
        if t == "hello":
            self.pid      = msg["pid"]
            self.map_w    = msg.get("map_w", 2400)
            self.map_h    = msg.get("map_h", 1800)
            self.ai_mode  = msg.get("ai_mode", False)
            self.version  = msg.get("version", "?")
            print(f"[NET] Connected as {self.pid} (server v{self.version})")
        elif t == "state":
            with self._lock:
                self._state = msg
        elif t == "pong":
            self._ping = int((time.time() - self._ping_ts) * 1000)

    def get_state(self):
        with self._lock:
            return self._state

    def send_input(self, mx, my, sprint, silent):
        self._send({"type": "input", "mx": mx, "my": my,
                    "sprint": sprint, "silent": silent})

    def send_start(self):
        self._send({"type": "start"})

    def update_ping(self, dt):
        self._ping_timer += dt
        if self._ping_timer >= self._ping_interval:
            self._ping_timer = 0
            self._ping_ts = time.time()
            self._send({"type": "ping", "ts": self._ping_ts})

    def get_ping(self):
        return self._ping

    def _send(self, obj):
        if not self.alive:
            return
        try:
            self._sock.sendall((json.dumps(obj) + "\n").encode())
        except Exception:
            self.alive = False

    def disconnect(self):
        self.alive = False
        try:
            self._sock.close()
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════
#  РЕНДЕРЕР КАРТЫ
# ══════════════════════════════════════════════════════════════

class MapRenderer:
    TILE = 64

    def __init__(self, map_w, map_h):
        self.map_w    = map_w
        self.map_h    = map_h
        self.walls    = []
        self.surface  = None
        self._built   = False

    def build(self, walls_data):
        if self._built:
            return
        self._built = True
        self.walls  = [pygame.Rect(*w) for w in walls_data]

        surf = pygame.Surface((self.map_w, self.map_h))

        ts   = self.TILE
        cols = self.map_w // ts + 1
        rows = self.map_h // ts + 1

        for r in range(rows):
            for c in range(cols):
                px, py = c*ts, r*ts
                idx    = (r * 7 + c * 3) % 16
                if idx < 8:
                    col = C_FLOOR_A
                elif idx < 14:
                    col = C_FLOOR_B
                else:
                    col = C_FLOOR_C
                pygame.draw.rect(surf, col, (px, py, ts, ts))
                pygame.draw.line(surf, (28, 28, 44), (px, py), (px+ts, py), 1)
                pygame.draw.line(surf, (28, 28, 44), (px, py), (px, py+ts), 1)

        for _ in range(cols * rows // 8):
            c2 = random.randint(0, cols-1)
            r2 = random.randint(0, rows-1)
            d_surf = pygame.Surface((ts, ts), pygame.SRCALPHA)
            d_surf.fill((0, 0, 0, random.randint(15, 40)))
            surf.blit(d_surf, (c2*ts, r2*ts))

        for w in self.walls:
            pygame.draw.rect(surf, C_WALL, w)
            pygame.draw.rect(surf, C_WALL_TOP, (w.x, w.y, w.width, min(6, w.height)))
            shadow = pygame.Surface((4, w.height), pygame.SRCALPHA)
            shadow.fill((0, 0, 0, 80))
            surf.blit(shadow, (w.right - 4, w.y))
            shadow2 = pygame.Surface((w.width, 4), pygame.SRCALPHA)
            shadow2.fill((0, 0, 0, 60))
            surf.blit(shadow2, (w.x, w.bottom - 4))
            pygame.draw.rect(surf, C_WALL_EDGE, w, 2)

        self.surface = surf
        print(f"[MAP] Built {self.map_w}x{self.map_h}, {len(self.walls)} walls")


# ══════════════════════════════════════════════════════════════
#  МИНИ-КАРТА
# ══════════════════════════════════════════════════════════════

class MiniMap:
    SIZE_NORMAL  = 200
    SIZE_EXPANDED= 380
    MARGIN       = 12
    HEADER_H     = 28

    def __init__(self, map_w, map_h):
        self.map_w    = map_w
        self.map_h    = map_h
        self.expanded = False
        self._base_n  = None
        self._base_e  = None
        self._walls   = []
        self._anim    = 0.0
        self._cur_size= float(self.SIZE_NORMAL)

    def _scale(self, expanded=False):
        s = self.SIZE_EXPANDED if expanded else self.SIZE_NORMAL
        return s / max(self.map_w, self.map_h)

    def build_base(self, walls):
        self._walls = walls
        for expanded in (False, True):
            s  = self.SIZE_EXPANDED if expanded else self.SIZE_NORMAL
            sc = self._scale(expanded)
            surf = pygame.Surface((s, s), pygame.SRCALPHA)
            surf.fill((*MM_BG, 230))

            step = max(2, int(64 * sc))
            for xx in range(0, s, step):
                pygame.draw.line(surf, (*MM_BG, 255), (xx, 0), (xx, s), 1)
            for yy in range(0, s, step):
                pygame.draw.line(surf, (*MM_BG, 255), (0, yy), (s, yy), 1)

            for w in walls:
                rx = int(w.x * sc)
                ry = int(w.y * sc)
                rw = max(2, int(w.width  * sc))
                rh = max(2, int(w.height * sc))
                pygame.draw.rect(surf, MM_WALL, (rx, ry, rw, rh))

            pygame.draw.rect(surf, (90, 90, 140), (0, 0, s, s), 2)

            if expanded:
                self._base_e = surf
            else:
                self._base_n = surf

    def toggle(self):
        self.expanded = not self.expanded

    def draw(self, surf, state, my_pid, screen_w, screen_h, dt):
        self._anim += dt
        target_size = float(self.SIZE_EXPANDED if self.expanded else self.SIZE_NORMAL)
        self._cur_size = lerp(self._cur_size, target_size, min(1.0, dt * 12))
        s  = int(self._cur_size)
        if s < 10:
            return
        sc = s / max(self.map_w, self.map_h)

        margin = self.MARGIN
        rx = screen_w - s - margin
        ry = margin

        panel_h = s + self.HEADER_H + margin
        panel   = pygame.Surface((s + margin*2, panel_h), pygame.SRCALPHA)
        panel.fill((0, 0, 0, 0))
        pygame.draw.rect(panel, (*C_HUD_BG, 200), (0, 0, s+margin*2, panel_h), border_radius=8)
        pygame.draw.rect(panel, (80, 80, 120, 180), (0, 0, s+margin*2, panel_h), 2, border_radius=8)
        surf.blit(panel, (rx - margin, ry - 4))

        f_title = get_font("monospace", 13, bold=True)
        title_text = "КАРТА [M]" if not self.expanded else "КАРТА [M] — развёрнута"
        tt = f_title.render(title_text, True, (160, 160, 210))
        surf.blit(tt, (rx, ry + 4))
        ry += self.HEADER_H

        base = self._base_e if self.expanded else self._base_n
        if base:
            base_scaled = pygame.transform.scale(base, (s, s))
            surf.blit(base_scaled, (rx, ry))
        else:
            pygame.draw.rect(surf, MM_BG, (rx, ry, s, s))

        me = state.get("players", {}).get(my_pid) if my_pid else None
        if me and not me.get("is_monster") and not self.expanded:
            fog = pygame.Surface((s, s), pygame.SRCALPHA)
            fog.fill((*MM_FOG, 180))
            if me:
                mx_sc = int(me["x"] * sc)
                my_sc = int(me["y"] * sc)
                fog_r = max(1, int(80 * sc * (self.map_w / 1000)))
                pygame.draw.circle(fog, (0, 0, 0, 0), (mx_sc, my_sc), fog_r)
            surf.blit(fog, (rx, ry))

        for trap in state.get("traps", []):
            if trap.get("visible") or not trap.get("active", True):
                tx_ = int(trap["x"] * sc)
                ty_ = int(trap["y"] * sc)
                col = MM_TRAP if trap.get("active") else (100, 30, 90)
                pygame.draw.rect(surf, col, (rx+tx_-3, ry+ty_-3, 7, 7))

        for key in state.get("keys", []):
            if key.get("on_map"):
                kx_ = int(key["x"] * sc)
                ky_ = int(key["y"] * sc)
                r2  = max(1, int(3 + 1.5 * abs(math.sin(self._anim * 3))))
                pygame.draw.circle(surf, MM_KEY, (rx+kx_, ry+ky_), r2)

        for door in state.get("doors", []):
            dx_ = int(door["x"] * sc)
            dy_ = int(door["y"] * sc)
            col = C_DOOR_OPEN if door.get("open") else MM_DOOR
            pygame.draw.rect(surf, col, (rx+dx_-4, ry+dy_-6, 9, 12))

        ai = state.get("ai_monster")
        if ai:
            ax_ = int(ai["x"] * sc)
            ay_ = int(ai["y"] * sc)
            r3  = max(1, int(5 + 2 * abs(math.sin(self._anim * 4))))
            glow_s = pygame.Surface((r3*4, r3*4), pygame.SRCALPHA)
            pygame.draw.circle(glow_s, (*MM_MONSTER, 60), (r3*2, r3*2), r3*2)
            surf.blit(glow_s, (rx+ax_-r3*2, ry+ay_-r3*2))
            pygame.draw.circle(surf, MM_MONSTER, (rx+ax_, ry+ay_), r3)

        f_small = get_font("monospace", 9)
        for pid, p in state.get("players", {}).items():
            px_ = int(p["x"] * sc)
            py_ = int(p["y"] * sc)
            is_me = (pid == my_pid)

            if p["is_monster"]:
                col = MM_MONSTER
                r4  = max(1, int(5 + 1.5 * abs(math.sin(self._anim * 4))))
                glow_s2 = pygame.Surface((r4*4, r4*4), pygame.SRCALPHA)
                pygame.draw.circle(glow_s2, (*MM_MONSTER, 60), (r4*2, r4*2), r4*2)
                surf.blit(glow_s2, (rx+px_-r4*2, ry+py_-r4*2))
                pygame.draw.circle(surf, col, (rx+px_, ry+py_), r4)
            elif is_me:
                col = MM_ME
                pygame.draw.circle(surf, (*col, 200), (rx+px_, ry+py_), 5)
                pygame.draw.circle(surf, C_WHITE, (rx+px_, ry+py_), 5, 2)
            elif p["alive"] and not p.get("escaped"):
                pygame.draw.circle(surf, MM_SURV, (rx+px_, ry+py_), 3)
                lbl = f_small.render(pid, True, MM_SURV)
                surf.blit(lbl, (rx+px_+4, ry+py_-4))
            elif p.get("escaped"):
                pygame.draw.circle(surf, (0, 255, 180), (rx+px_, ry+py_), 3)
            else:
                pygame.draw.circle(surf, C_DARK_GRAY, (rx+px_, ry+py_), 2)

        pygame.draw.rect(surf, (80, 80, 120), (rx, ry, s, s), 2)
        self._draw_legend(surf, rx - margin, ry + s + 4, s + margin*2, my_pid,
                          state, self.expanded)

    def _draw_legend(self, surf, lx, ly, width, my_pid, state, expanded):
        f = get_font("monospace", 10)
        items = [
            (MM_ME,      "Вы"),
            (MM_SURV,    "Союзники"),
            (MM_MONSTER, "Монстр"),
            (MM_KEY,     "Ключ"),
            (MM_DOOR,    "Выход"),
        ]
        per_row = 3 if not expanded else 5
        for i, (col, text) in enumerate(items):
            row = i // per_row
            col_idx = i % per_row
            cell_w = max(1, width // per_row)
            xx = lx + col_idx * cell_w + 4
            yy = ly + row * 14 + 2
            pygame.draw.circle(surf, col, (xx + 4, yy + 5), 3)
            t = f.render(text, True, (130, 130, 160))
            surf.blit(t, (xx + 10, yy))


# ══════════════════════════════════════════════════════════════
#  ФОНАРИК
# ══════════════════════════════════════════════════════════════

class Flashlight:
    def __init__(self):
        self._dark   = None
        self._sw     = self._sh = 0
        self._masks  = {}

    def _ensure(self, sw, sh):
        if sw != self._sw or sh != self._sh:
            self._sw, self._sh = sw, sh
            self._dark = pygame.Surface((sw, sh), pygame.SRCALPHA)

    def _mask(self, r):
        if r not in self._masks:
            r = max(1, r)
            d  = r * 2
            s  = pygame.Surface((d, d), pygame.SRCALPHA)
            for ri in range(r, 0, -3):
                ratio = ri / r
                a = int(DARKNESS_ALPHA * (ratio ** 1.5))
                pygame.draw.circle(s, (0, 0, 0, a), (r, r), ri)
            self._masks[r] = s
        return self._masks[r]

    def draw(self, surf, cx, cy, radius, is_dead=False, is_monster=False):
        if radius >= 9999:
            return
        sw, sh = surf.get_size()
        self._ensure(sw, sh)
        dark = self._dark
        dark.fill((0, 0, 0, DARKNESS_ALPHA))

        if not is_dead and 0 < cx < sw and 0 < cy < sh:
            m = self._mask(radius)
            dark.blit(m, (cx - radius, cy - radius),
                      special_flags=pygame.BLEND_RGBA_MIN)

            if is_monster:
                red_tint = pygame.Surface((sw, sh), pygame.SRCALPHA)
                red_tint.fill((30, 0, 0, 40))
                surf.blit(red_tint, (0, 0))

        surf.blit(dark, (0, 0))


# ══════════════════════════════════════════════════════════════
#  КРАСИВЫЕ СПРАЙТЫ ПЕРСОНАЖЕЙ
# ══════════════════════════════════════════════════════════════

class CharRenderer:
    SURVIVOR_COLORS = [
        ((70, 185, 100), (40, 120, 60),   "зеленый"),
        ((70, 130, 200), (40, 80, 150),   "синий"),
        ((200, 170, 50), (140, 110, 30),  "желтый"),
        ((180, 80, 200), (120, 40, 150),  "фиолетовый"),
        ((200, 100, 70), (150, 60, 40),   "красный"),
        ((70, 190, 190), (40, 130, 130),  "голубой"),
        ((190, 130, 70), (130, 85, 40),   "оранжевый"),
        ((155, 155, 60), (100, 100, 30),  "хаки"),
    ]

    @classmethod
    def get_survivor_colors(cls, pid_or_index):
        if isinstance(pid_or_index, str):
            try:
                idx = int(''.join(filter(str.isdigit, pid_or_index))) - 1
            except Exception:
                idx = 0
        else:
            idx = int(pid_or_index)
        return cls.SURVIVOR_COLORS[idx % len(cls.SURVIVOR_COLORS)]

    @classmethod
    def draw_survivor(cls, surf, cx, cy, size, body_col, shadow_col,
                      frame=0, is_me=False, sprinting=False, silent=False,
                      has_key=False, trap_slow=0.0):
        S = size
        hs= S // 2

        shadow = pygame.Surface((S, S//3 + 1), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0, 0, 0, 60), (0, 0, S, max(1, S//3)))
        surf.blit(shadow, (cx - hs, cy + S//3 + 4))

        leg_anim = [0, 6, 0, -6][frame % 4]

        leg_col = tuple(max(0, c - 30) for c in body_col[:3])
        pygame.draw.line(surf, leg_col,
                         (cx - 5, cy + hs - 2),
                         (cx - 8, cy + hs + 12 + leg_anim), 5)
        pygame.draw.line(surf, leg_col,
                         (cx + 5, cy + hs - 2),
                         (cx + 8, cy + hs + 12 - leg_anim), 5)
        pygame.draw.ellipse(surf, leg_col,
                            (cx - 14, cy + hs + 10 + leg_anim, 10, 5))
        pygame.draw.ellipse(surf, leg_col,
                            (cx + 4,  cy + hs + 10 - leg_anim, 10, 5))

        body_rect = pygame.Rect(cx - hs//2 + 2, cy - hs//4, hs - 2, hs + 2)
        pygame.draw.rect(surf, body_col, body_rect, border_radius=4)

        belt_col = tuple(max(0, c - 50) for c in body_col[:3])
        pygame.draw.rect(surf, belt_col,
                         (cx - hs//2 + 2, cy + hs//6, hs - 2, 4))

        arm_anim_l = [0, -4, 0, 4][frame % 4]
        arm_col = body_col
        pygame.draw.line(surf, arm_col,
                         (cx - hs//2 + 2, cy - hs//8),
                         (cx - hs//2 - 8, cy + arm_anim_l), 4)
        pygame.draw.line(surf, arm_col,
                         (cx + hs//2 - 4, cy - hs//8),
                         (cx + hs//2 + 6, cy - arm_anim_l), 4)

        skin = (210, 170, 130)
        pygame.draw.circle(surf, skin, (cx - hs//2 - 8, cy + arm_anim_l), 3)
        pygame.draw.circle(surf, skin, (cx + hs//2 + 6, cy - arm_anim_l), 3)

        head_r = hs // 2 + 2
        pygame.draw.rect(surf, skin, (cx - 4, cy - hs//2 - 2, 8, 6))
        pygame.draw.circle(surf, skin, (cx, cy - hs//2 - 4 - head_r//2), head_r)

        hair_col = tuple(max(0, c - 80) for c in body_col[:3])
        # FIX: ensure arc rect has positive height
        arc_h = max(1, head_r)
        pygame.draw.arc(surf, hair_col,
                        (cx - head_r, cy - hs//2 - 4 - head_r - head_r//2,
                         head_r*2, arc_h),
                        0, math.pi, 5)

        eye_y = cy - hs//2 - 4 - head_r//2
        pygame.draw.circle(surf, (30, 30, 50), (cx - 4, eye_y), 2)
        pygame.draw.circle(surf, (30, 30, 50), (cx + 4, eye_y), 2)
        pygame.draw.circle(surf, C_WHITE, (cx - 3, eye_y - 1), 1)
        pygame.draw.circle(surf, C_WHITE, (cx + 5, eye_y - 1), 1)

        if is_me:
            arc_h2 = max(1, head_r)
            pygame.draw.arc(surf, C_ME,
                            (cx - head_r - 1, cy - hs//2 - 5 - head_r - head_r//2,
                             head_r*2+2, arc_h2),
                            0, math.pi, 3)

        if not silent:
            flash_col = (255, 240, 150)
            flash_a   = int(180 + 60 * math.sin(pygame.time.get_ticks() * 0.003))
            flash_s   = pygame.Surface((30, 30), pygame.SRCALPHA)
            pygame.draw.circle(flash_s, (*flash_col, flash_a), (15, 15), 12)
            surf.blit(flash_s, (cx + hs//2 - 5, cy - hs//4 - 5))
            pygame.draw.circle(surf, flash_col, (cx + hs//2 + 6, cy - arm_anim_l), 4)

        if has_key:
            key_y = cy - hs//2 - head_r - 20
            key_pulse = int(200 + 55 * abs(math.sin(pygame.time.get_ticks() * 0.004)))
            kc = (key_pulse, 180, 0)
            pygame.draw.circle(surf, kc, (cx, key_y), 6)
            pygame.draw.line(surf, kc, (cx+3, key_y), (cx+8, key_y), 2)
            pygame.draw.rect(surf, kc, (cx+7, key_y-3, 3, 6))

        if trap_slow > 0:
            glow = pygame.Surface((S+12, S+12), pygame.SRCALPHA)
            a_g  = int(120 * (trap_slow / 3.0))
            pygame.draw.ellipse(glow, (*C_TRAP, a_g), (0, 0, S+12, S+12))
            surf.blit(glow, (cx - S//2 - 6, cy - S//2 - 6))

        if sprinting:
            for i in range(3):
                off_x = random.randint(-3, 3)
                off_y = random.randint(-3, 3)
                speed_col = (100, 150, 255, 80)
                speed_s   = pygame.Surface((20, 3), pygame.SRCALPHA)
                speed_s.fill(speed_col)
                surf.blit(speed_s, (cx - 25 + off_x, cy + off_y))

    @classmethod
    def draw_monster(cls, surf, cx, cy, size, frame=0, is_ai=False,
                     state_name="patrol", sprinting=False):
        S  = size
        hs = S // 2
        t  = pygame.time.get_ticks() * 0.001

        aura_r  = max(1, int(hs + 14 + 6 * math.sin(t * 3)))
        aura    = pygame.Surface((aura_r*2+4, aura_r*2+4), pygame.SRCALPHA)
        aura_a  = int(50 + 20 * math.sin(t * 2))
        pygame.draw.circle(aura, (*C_MONSTER, aura_a),
                           (aura_r+2, aura_r+2), aura_r)
        surf.blit(aura, (cx - aura_r - 2, cy - aura_r//2))

        shadow = pygame.Surface((S + 8, max(1, S//3 + 4)), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0, 0, 0, 80), (0, 0, S+8, max(1, S//3+4)))
        surf.blit(shadow, (cx - hs - 4, cy + hs//2 + 6))

        leg = [0, 5, 0, -5][frame % 4]
        arm = [-4, 0, 4, 0][frame % 4]

        cl = (170, 18, 18)
        for side, lleg in [(-1, leg), (1, -leg)]:
            bx = cx + side * 6
            by = cy + hs//2
            ex = cx + side * 10
            ey = cy + hs//2 + 14 + lleg
            pygame.draw.line(surf, C_MONSTER, (bx, by), (ex, ey), 5)
            pygame.draw.polygon(surf, cl, [
                (ex - 3, ey), (ex + 3, ey), (ex, ey + 8)
            ])

        body_pts = [
            (cx - hs//2, cy + hs//2),
            (cx + hs//2, cy + hs//2),
            (cx + hs//2 + 4, cy - hs//4),
            (cx - hs//2 - 4, cy - hs//4),
        ]
        pygame.draw.polygon(surf, C_MONSTER, body_pts)

        for i in range(3):
            rib_y = cy - hs//8 + i * (hs//4)
            rib_col = (170, 25, 25)
            pygame.draw.line(surf, rib_col,
                             (cx - hs//2 + 4, rib_y),
                             (cx + hs//2 - 4, rib_y), 2)

        for side, aarm in [(-1, -arm), (1, arm)]:
            bx = cx + side * (hs//2 + 4)
            by = cy - hs//8
            ex = cx + side * (hs//2 + 16)
            ey = cy + aarm
            pygame.draw.line(surf, C_MONSTER_G, (bx, by), (ex, ey), 4)
            for k in range(3):
                kx = ex + side * (k * 3)
                ky = ey + k * 3
                pygame.draw.line(surf, cl, (ex, ey), (kx + side*6, ky + 5), 2)

        head_r = hs//2 + 4
        head_y = cy - hs//2 - head_r//2
        pygame.draw.circle(surf, C_MONSTER, (cx, head_y), head_r)

        horn_pts_l = [(cx - head_r//2, head_y - head_r//2),
                      (cx - head_r - 4, head_y - head_r - 10),
                      (cx - head_r + 4, head_y - head_r//2 - 4)]
        horn_pts_r = [(cx + head_r//2, head_y - head_r//2),
                      (cx + head_r + 4, head_y - head_r - 10),
                      (cx + head_r - 4, head_y - head_r//2 - 4)]
        pygame.draw.polygon(surf, (150, 15, 15), horn_pts_l)
        pygame.draw.polygon(surf, (150, 15, 15), horn_pts_r)

        glow_eye = int(200 + 55 * abs(math.sin(t * 4)))
        eye_col  = (glow_eye, int(glow_eye * 0.7), 0)
        eye_y    = head_y - 2
        for ex_, ey_ in [(cx - 5, eye_y), (cx + 5, eye_y)]:
            eg = pygame.Surface((12, 12), pygame.SRCALPHA)
            pygame.draw.circle(eg, (*eye_col, 100), (6, 6), 6)
            surf.blit(eg, (ex_ - 6, ey_ - 6))
        pygame.draw.circle(surf, eye_col, (cx - 5, eye_y), 3)
        pygame.draw.circle(surf, eye_col, (cx + 5, eye_y), 3)
        pygame.draw.circle(surf, C_BLACK,  (cx - 5, eye_y), 1)
        pygame.draw.circle(surf, C_BLACK,  (cx + 5, eye_y), 1)

        mouth_y = head_y + head_r//2
        # FIX: ensure arc rect has positive height
        mouth_rect = (cx - head_r//2, mouth_y - 4, head_r, max(1, 8))
        pygame.draw.arc(surf, (80, 10, 10), mouth_rect, math.pi, 2*math.pi, 3)
        for ti in range(4):
            tx_ = cx - head_r//2 + 4 + ti * 6
            pygame.draw.polygon(surf, C_WHITE, [
                (tx_, mouth_y), (tx_+3, mouth_y), (tx_+1, mouth_y+5)
            ])

        if is_ai:
            scan = pygame.Surface((head_r*3, head_r*3), pygame.SRCALPHA)
            scan_a = int(40 + 20 * abs(math.sin(t * 5)))
            pygame.draw.circle(scan, (*C_RED, scan_a), (head_r, head_r), head_r)
            surf.blit(scan, (cx - head_r, head_y - head_r))

        if sprinting or state_name == "chase":
            for _ in range(4):
                sx_ = cx + random.randint(-hs, hs)
                sy_ = cy + random.randint(-hs//2, hs)
                sc_s = pygame.Surface((6, 6), pygame.SRCALPHA)
                pygame.draw.circle(sc_s, (*C_ORANGE, 150), (3, 3), 3)
                surf.blit(sc_s, (sx_ - 3, sy_ - 3))

    @classmethod
    def draw_dead(cls, surf, cx, cy, size):
        S  = size
        hs = S // 2
        pygame.draw.ellipse(surf, C_DEAD,
                            (cx - hs, cy - hs//3, S, max(1, hs//2 + 4)))
        pygame.draw.circle(surf, C_DEAD, (cx + hs//2, cy), max(1, hs//3))
        ey = cy
        ex2 = cx + hs//2
        for dx2, dy2 in [(-3,-3),(3,3)]:
            pygame.draw.line(surf, C_BLACK,
                             (ex2-4+dx2, ey-4+dy2), (ex2+4+dx2, ey+4+dy2), 2)
        for dx2, dy2 in [(3,-3),(-3,3)]:
            pygame.draw.line(surf, C_BLACK,
                             (ex2-4+dx2, ey-4+dy2), (ex2+4+dx2, ey+4+dy2), 2)
        blood = pygame.Surface((S, S), pygame.SRCALPHA)
        pygame.draw.circle(blood, (150, 10, 10, 100), (hs, hs), max(1, hs//2))
        surf.blit(blood, (cx - hs, cy - hs))


# ══════════════════════════════════════════════════════════════
#  ЧАСТИЦЫ
# ══════════════════════════════════════════════════════════════

class Particle:
    __slots__ = ("x","y","vx","vy","color","life","max_life","r","fade_type")

    def __init__(self, x, y, vx, vy, color, life, r=3, fade_type="linear"):
        self.x = float(x); self.y = float(y)
        self.vx = vx;      self.vy = vy
        self.color     = color
        self.life      = self.max_life = life
        self.r         = r
        self.fade_type = fade_type

    def update(self, dt):
        self.x  += self.vx * dt * 60
        self.y  += self.vy * dt * 60
        self.vx *= 0.90
        self.vy *= 0.90
        self.vy += 0.05
        self.life -= dt

    def draw(self, surf, ox, oy, sw, sh):
        sx, sy = int(self.x - ox), int(self.y - oy)
        if not (-20 < sx < sw+20 and -20 < sy < sh+20):
            return
        ratio = max(0.0, self.life / self.max_life)
        a = ratio
        col = tuple(clamp(int(c * a), 0, 255) for c in self.color[:3])
        r2  = max(1, int(self.r * a))
        pygame.draw.circle(surf, col, (sx, sy), r2)


class Particles:
    def __init__(self):
        self.pool = []

    def emit_death(self, x, y):
        for _ in range(30):
            a = random.uniform(0, math.tau)
            s = random.uniform(1.0, 4.5)
            self.pool.append(Particle(
                x, y, math.cos(a)*s, math.sin(a)*s,
                (random.randint(180, 220), random.randint(0, 20), random.randint(0, 20)),
                random.uniform(0.6, 1.5), r=random.randint(2, 6)))
        for _ in range(8):
            self.pool.append(Particle(
                x + random.uniform(-15, 15), y + random.uniform(-10, 10),
                random.uniform(-0.5, 0.5), random.uniform(-0.5, 0.5),
                (140, 5, 5), random.uniform(1.5, 3.0), r=random.randint(4, 10)))

    def emit_pickup(self, x, y):
        for _ in range(20):
            a = random.uniform(0, math.tau)
            s = random.uniform(0.5, 2.5)
            self.pool.append(Particle(
                x, y, math.cos(a)*s, math.sin(a)*s - 2,
                (255, random.randint(180, 230), 0),
                random.uniform(0.5, 1.2), r=random.randint(2, 5)))

    def emit_escape(self, x, y):
        for _ in range(40):
            a = random.uniform(0, math.tau)
            s = random.uniform(1.5, 5.0)
            self.pool.append(Particle(
                x, y, math.cos(a)*s, math.sin(a)*s,
                (random.randint(0, 80), random.randint(200, 255), random.randint(150, 255)),
                random.uniform(0.8, 2.0), r=random.randint(2, 7)))

    def emit_trap(self, x, y):
        for _ in range(18):
            a = random.uniform(0, math.tau)
            s = random.uniform(0.5, 2.0)
            self.pool.append(Particle(
                x, y, math.cos(a)*s, math.sin(a)*s - 1,
                (random.randint(180, 220), 0, random.randint(180, 220)),
                random.uniform(0.4, 1.0), r=random.randint(2, 5)))

    def emit_step(self, x, y):
        for _ in range(3):
            a = random.uniform(math.pi, 2*math.pi)
            s = random.uniform(0.1, 0.5)
            self.pool.append(Particle(
                x + random.uniform(-8, 8), y + 10,
                math.cos(a)*s, math.sin(a)*s,
                (80, 80, 100), random.uniform(0.2, 0.5), r=2))

    def update(self, dt):
        self.pool = [p for p in self.pool if p.life > 0]
        for p in self.pool:
            p.update(dt)

    def draw(self, surf, ox, oy, sw, sh):
        for p in self.pool:
            p.draw(surf, ox, oy, sw, sh)


# ══════════════════════════════════════════════════════════════
#  КАМЕРА
# ══════════════════════════════════════════════════════════════

class Camera:
    def __init__(self, map_w, map_h):
        self.x = self.y = 0.0
        self.map_w = map_w
        self.map_h = map_h
        self._shake_x = self._shake_y = 0.0
        self._shake_power = 0.0

    def shake(self, power):
        self._shake_power = max(self._shake_power, power)

    def update(self, wx, wy, sw, sh, dt):
        tx = clamp(wx - sw/2, 0, max(0, self.map_w - sw))
        ty = clamp(wy - sh/2, 0, max(0, self.map_h - sh))
        t  = 1.0 - math.exp(-CAM_LERP * dt)
        self.x = lerp(self.x, tx, t)
        self.y = lerp(self.y, ty, t)

        if self._shake_power > 0.1:
            self._shake_x = random.uniform(-self._shake_power, self._shake_power)
            self._shake_y = random.uniform(-self._shake_power, self._shake_power)
            self._shake_power -= CAM_SHAKE_DECAY * dt
        else:
            self._shake_x = self._shake_y = 0.0
            self._shake_power = 0.0

    def to_screen(self, wx, wy):
        return (int(wx - self.x + self._shake_x),
                int(wy - self.y + self._shake_y))


# ══════════════════════════════════════════════════════════════
#  UI ВИДЖЕТЫ
# ══════════════════════════════════════════════════════════════

class Button:
    def __init__(self, x, y, w, h, text, color=(55, 18, 18), font=None,
                 border_color=None, hover_scale=True):
        self.rect         = pygame.Rect(x, y, w, h)
        self.text         = text
        self.color        = color
        self.border_color = border_color or (120, 50, 50)
        self.hcolor       = tuple(min(255, c+55) for c in color)
        self.font         = font
        self._hover       = False
        self._hover_scale = hover_scale
        self._anim        = 0.0

    def handle(self, event):
        if event.type == pygame.MOUSEMOTION:
            self._hover = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            return self.rect.collidepoint(event.pos)
        return False

    def update(self, dt):
        self._anim += dt

    def draw(self, surf):
        col = self.hcolor if self._hover else self.color
        r   = self.rect

        if self._hover and self._hover_scale:
            er = r.inflate(4, 4)
        else:
            er = r

        pygame.draw.rect(surf, col, er, border_radius=10)
        pygame.draw.rect(surf, self.border_color, er, 2, border_radius=10)

        shine = pygame.Surface((er.width, max(1, er.height//3)), pygame.SRCALPHA)
        shine.fill((255, 255, 255, 20 if self._hover else 10))
        surf.blit(shine, (er.x, er.y))

        if self.font:
            t = self.font.render(self.text, True, C_WHITE)
            surf.blit(t, t.get_rect(center=er.center))


class InputField:
    def __init__(self, x, y, w, h, default="", label=""):
        self.rect    = pygame.Rect(x, y, w, h)
        self.text    = default
        self.label   = label
        self.active  = False
        self._blink  = True
        self._btimer = 0.0

    def handle(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.active = self.rect.collidepoint(event.pos)
        elif event.type == pygame.KEYDOWN and self.active:
            if event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            elif len(self.text) < 40 and event.unicode.isprintable():
                self.text += event.unicode

    def update(self, dt):
        self._btimer += dt
        if self._btimer > 0.5:
            self._blink  = not self._blink
            self._btimer = 0.0

    def draw(self, surf, f_label, f_text):
        if self.label:
            surf.blit(f_label.render(self.label, True, C_GRAY),
                      (self.rect.x, self.rect.y - 22))
        bc = (90, 42, 42) if self.active else (44, 20, 20)
        pygame.draw.rect(surf, bc, self.rect, border_radius=6)
        pygame.draw.rect(surf, (150, 65, 65), self.rect, 2, border_radius=6)

        blink_s = pygame.Surface((self.rect.width, max(1, self.rect.height//2)), pygame.SRCALPHA)
        blink_s.fill((255, 255, 255, 8))
        surf.blit(blink_s, (self.rect.x, self.rect.y))

        cur = "|" if (self.active and self._blink) else ""
        t   = f_text.render(self.text + cur, True, C_WHITE)
        surf.blit(t, (self.rect.x + 10,
                      self.rect.centery - t.get_height()//2))


# ══════════════════════════════════════════════════════════════
#  БАЗОВЫЙ ЭКРАН
# ══════════════════════════════════════════════════════════════

class BaseScreen:
    def __init__(self, app):
        self.app = app

    def on_enter(self):
        pass

    def handle_event(self, event):
        pass

    def update(self, dt):
        pass

    def draw(self, surf):
        pass

    def _bg(self, surf):
        surf.fill(C_BG)
        sw, sh = surf.get_size()
        for x in range(0, sw, 64):
            pygame.draw.line(surf, (14, 14, 22), (x, 0), (x, sh))
        for y in range(0, sh, 64):
            pygame.draw.line(surf, (14, 14, 22), (0, y), (sw, y))


# ══════════════════════════════════════════════════════════════
#  ГЛАВНОЕ МЕНЮ
# ══════════════════════════════════════════════════════════════

class MenuScreen(BaseScreen):
    def __init__(self, app):
        super().__init__(app)
        fn = pygame.font.SysFont
        self.f_title = fn("monospace", 52, bold=True)
        self.f_sub   = fn("monospace", 16)
        self.f_btn   = fn("monospace", 22, bold=True)
        self.f_hint  = fn("monospace", 13)
        self.f_lbl   = fn("monospace", 16)
        self.f_inp   = fn("monospace", 20)
        self._anim   = 0.0
        self._frame  = 0
        self._ftimer = 0.0
        self._lw     = 0
        self._stars  = []
        self.ip_field = None
        self.btn_connect = None
        self.btn_quit    = None
        self._error_msg  = ""
        self._error_timer= 0.0

    def _make_stars(self, sw, sh):
        self._stars = [(random.randint(0, sw), random.randint(0, sh),
                        random.uniform(0.3, 2.0),
                        random.uniform(0, math.tau))
                       for _ in range(120)]

    def _layout(self, sw, sh):
        if self._lw == sw:
            return
        self._lw = sw
        BW, BH   = 360, 54
        bx       = sw//2 - BW//2
        self.ip_field    = InputField(bx, sh//2 - 30, BW, 46,
                                      DEFAULT_HOST, "IP-адрес сервера:")
        self.btn_connect = Button(bx, sh//2 + 32, BW, BH, "▶  ПОДКЛЮЧИТЬСЯ",
                                  (18, 50, 18), self.f_btn,
                                  border_color=(40, 120, 40))
        self.btn_quit    = Button(bx, sh//2 + 100, BW, BH//2 + 10, "✕  Выход",
                                  (45, 12, 12), self.f_hint,
                                  border_color=(100, 30, 30))
        self._make_stars(sw, sh)

    def on_enter(self):
        self._anim     = 0.0
        self._error_msg= ""
        self._lw = 0

    def handle_event(self, event):
        sw, sh = self.app.screen.get_size()
        self._layout(sw, sh)
        self.ip_field.handle(event)
        if self.btn_connect.handle(event):
            self._do_connect()
        if self.btn_quit.handle(event):
            self.app.running = False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.app.running = False
            elif event.key == pygame.K_RETURN:
                self._do_connect()

    def _do_connect(self):
        host = self.ip_field.text.strip() or DEFAULT_HOST
        success = self.app.connect_and_play(host)
        if not success:
            self._error_msg   = f"Не удалось подключиться к {host}:{PORT}"
            self._error_timer = 3.0

    def update(self, dt):
        self._anim   += dt
        self._ftimer += dt
        if self.ip_field:
            self.ip_field.update(dt)
        if self._ftimer > 0.18:
            self._ftimer = 0
            self._frame  = (self._frame + 1) % 4
        if self._error_timer > 0:
            self._error_timer -= dt

    def draw(self, surf):
        sw, sh = surf.get_size()
        self._layout(sw, sh)
        self._bg(surf)

        for i, (sx, sy, bright, phase) in enumerate(self._stars):
            a = 0.4 + 0.6 * abs(math.sin(self._anim * 0.8 + phase))
            r = max(1, int(bright * 0.8))
            col = (int(a * 100), int(a * 100), int(a * 160))
            pygame.draw.circle(surf, col, (sx, sy), r)

        title_text = "☠  HORROR LAN"
        pulse = int(140 + 115 * abs(math.sin(self._anim * 1.8)))
        shadow_t = self.f_title.render(title_text, True, (40, 5, 5))
        surf.blit(shadow_t, shadow_t.get_rect(centerx=sw//2 + 3, y=sh//4 + 3))
        main_t = self.f_title.render(title_text, True, (pulse, 20, 20))
        surf.blit(main_t, main_t.get_rect(centerx=sw//2, y=sh//4))

        sub_text = self.f_sub.render(
            "Найди ключ · Открой дверь · Сбеги от монстра", True, C_GRAY)
        surf.blit(sub_text, sub_text.get_rect(centerx=sw//2, y=sh//4 + 65))

        ver_t = self.f_hint.render("v4.0 ULTRA EDITION (FIXED)", True, (55, 55, 75))
        surf.blit(ver_t, ver_t.get_rect(centerx=sw//2, y=sh//4 + 88))

        char_surf = pygame.Surface((300, 80), pygame.SRCALPHA)
        for i, (role, lbl, col) in enumerate([
            ("monster", "МОНСТР", C_MONSTER),
            ("survivor", "ВЫЖИВШИЙ", C_SURV),
            ("me", "ВЫ", C_ME),
        ]):
            cx2 = 40 + i * 100
            cy2 = 44
            f2  = self._frame
            if role == "monster":
                CharRenderer.draw_monster(char_surf, cx2, cy2, 48, frame=f2)
            elif role == "me":
                body_col = CharRenderer.SURVIVOR_COLORS[0][0]
                shadow_col = CharRenderer.SURVIVOR_COLORS[0][1]
                CharRenderer.draw_survivor(char_surf, cx2, cy2, 48,
                                           body_col, shadow_col, frame=f2, is_me=True)
            else:
                body_col = CharRenderer.SURVIVOR_COLORS[1][0]
                shadow_col = CharRenderer.SURVIVOR_COLORS[1][1]
                CharRenderer.draw_survivor(char_surf, cx2, cy2, 48,
                                           body_col, shadow_col, frame=f2)
            lt = self.f_hint.render(lbl, True, col)
            char_surf.blit(lt, (cx2 - lt.get_width()//2, cy2 + 28))

        surf.blit(char_surf, (sw//2 - 150, sh//2 - 145))

        self.ip_field.draw(surf, self.f_lbl, self.f_inp)
        self.btn_connect.draw(surf)
        self.btn_quit.draw(surf)

        if self._error_msg and self._error_timer > 0:
            a = min(1.0, self._error_timer)
            err_s = pygame.Surface((sw, 36), pygame.SRCALPHA)
            err_s.fill((100, 0, 0, int(a * 180)))
            surf.blit(err_s, (0, sh//2 + 165))
            et = self.f_hint.render(self._error_msg, True,
                                    (255, int(100 * a), int(100 * a)))
            surf.blit(et, et.get_rect(centerx=sw//2, y=sh//2 + 173))

        hints = [
            "WASD — движение  |  SHIFT — спринт  |  CTRL — тихий шаг",
            "P/ESC — пауза  |  TAB — статистика  |  M — мини-карта  |  F11 — полный экран",
        ]
        for i, h in enumerate(hints):
            hs2 = self.f_hint.render(h, True, (50, 50, 70))
            surf.blit(hs2, hs2.get_rect(centerx=sw//2, y=sh - 46 + i*16))


# ══════════════════════════════════════════════════════════════
#  ЭКРАН ПАУЗЫ
# ══════════════════════════════════════════════════════════════

class PauseScreen(BaseScreen):
    def __init__(self, app):
        super().__init__(app)
        fn = pygame.font.SysFont
        self.f_t = fn("monospace", 44, bold=True)
        self.f_b = fn("monospace", 22, bold=True)
        self.f_h = fn("monospace", 14)
        self.btn_resume = None
        self.btn_menu   = None

    def _layout(self, sw, sh):
        BW, BH = 300, 54
        bx = sw//2 - BW//2
        self.btn_resume = Button(bx, sh//2,      BW, BH,
                                 "▶  Продолжить", (16, 50, 16), self.f_b,
                                 border_color=(40, 120, 40))
        self.btn_menu   = Button(bx, sh//2 + 70, BW, BH,
                                 "⌂  Главное меню", (50, 16, 16), self.f_b)

    def handle_event(self, event):
        sw, sh = self.app.screen.get_size()
        self._layout(sw, sh)
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_p):
                self.app.set_screen("game")
        if self.btn_resume.handle(event):
            self.app.set_screen("game")
        if self.btn_menu.handle(event):
            self.app.disconnect()
            self.app.set_screen("menu")

    def draw(self, surf):
        sw, sh = surf.get_size()
        self._layout(sw, sh)
        ov = pygame.Surface((sw, sh), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 190))
        surf.blit(ov, (0, 0))

        panel_w, panel_h = 380, 260
        panel = pygame.Rect(sw//2 - panel_w//2, sh//2 - 130, panel_w, panel_h)
        pygame.draw.rect(surf, (15, 15, 25), panel, border_radius=14)
        pygame.draw.rect(surf, (80, 80, 120), panel, 2, border_radius=14)

        t = self.f_t.render("⏸ ПАУЗА", True, C_YELLOW)
        surf.blit(t, t.get_rect(centerx=sw//2, y=sh//2 - 110))
        self.btn_resume.draw(surf)
        self.btn_menu.draw(surf)
        h = self.f_h.render("[P / ESC] — продолжить", True, C_GRAY)
        surf.blit(h, h.get_rect(centerx=sw//2, y=sh//2 + 140))


# ══════════════════════════════════════════════════════════════
#  ЭКРАН СМЕРТИ
# ══════════════════════════════════════════════════════════════

class DeathScreen(BaseScreen):
    DELAY = 5.0

    def __init__(self, app):
        super().__init__(app)
        fn = pygame.font.SysFont
        self.f_big  = fn("monospace", 52, bold=True)
        self.f_med  = fn("monospace", 22)
        self.f_hint = fn("monospace", 15)
        self._timer = 0.0
        self._ptcls = Particles()

    def on_enter(self):
        self._timer = 0.0
        sw, sh = self.app.screen.get_size()
        for _ in range(5):
            self._ptcls.emit_death(
                sw//2 + random.randint(-100, 100),
                sh//2 + random.randint(-80, 80))

    def handle_event(self, event):
        if event.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
            self._exit()

    def update(self, dt):
        self._timer += dt
        self._ptcls.update(dt)
        if self._timer >= self.DELAY:
            self._exit()

    def _exit(self):
        self.app.disconnect()
        self.app.set_screen("menu")

    def draw(self, surf):
        sw, sh = surf.get_size()
        ov = pygame.Surface((sw, sh), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 220))
        surf.blit(ov, (0, 0))

        pulse_a = int(30 + 20 * abs(math.sin(self._timer * 3)))
        pulse_s = pygame.Surface((sw, sh), pygame.SRCALPHA)
        pulse_s.fill((100, 0, 0, pulse_a))
        surf.blit(pulse_s, (0, 0))

        self._ptcls.draw(surf, 0, 0, sw, sh)

        a2   = min(1.0, self._timer / 0.6)
        size = max(10, int(80 * a2))
        char_s = pygame.Surface((size, size), pygame.SRCALPHA)
        CharRenderer.draw_dead(char_s, size//2, size//2, size)
        surf.blit(char_s, (sw//2 - size//2, sh//2 - 140))

        a3   = min(1.0, max(0, self._timer - 0.5) / 0.5)
        t1   = self.f_big.render("ВЫ МЕРТВЫ", True,
                                  (int(220*a3), int(30*a3), int(30*a3)))
        t2   = self.f_med.render("Тьма поглотила вас...", True,
                                  (int(110*a3), int(110*a3), int(110*a3)))
        rem  = max(0.0, self.DELAY - self._timer)
        t3   = self.f_hint.render(
            f"Меню через {rem:.1f}с  [любая клавиша]",
            True, (60, 60, 80))
        surf.blit(t1, t1.get_rect(centerx=sw//2, y=sh//2 - 50))
        surf.blit(t2, t2.get_rect(centerx=sw//2, y=sh//2 + 20))
        surf.blit(t3, t3.get_rect(centerx=sw//2, y=sh//2 + 70))


# ══════════════════════════════════════════════════════════════
#  ЭКРАН КОНЦА ИГРЫ
# ══════════════════════════════════════════════════════════════

class EndScreen(BaseScreen):
    def __init__(self, app):
        super().__init__(app)
        fn = pygame.font.SysFont
        self.f_t    = fn("monospace", 52, bold=True)
        self.f_sub  = fn("monospace", 24)
        self.f_stat = fn("monospace", 16)
        self.f_hint = fn("monospace", 15)
        self.winner       = None
        self.i_am_monster = False
        self._anim        = 0.0
        self._ptcls       = Particles()

    def on_enter(self):
        self._anim = 0.0
        sw, sh = self.app.screen.get_size()
        won = (self.winner == "survivors" and not self.i_am_monster) or \
              (self.winner == "monster"   and self.i_am_monster)
        if won:
            for _ in range(8):
                self._ptcls.emit_escape(
                    sw//2 + random.randint(-200, 200), sh//2 - 100)

    def handle_event(self, event):
        if event.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
            self.app.disconnect()
            self.app.set_screen("menu")

    def update(self, dt):
        self._anim  += dt
        self._ptcls.update(dt)

    def draw(self, surf):
        sw, sh = surf.get_size()
        ov = pygame.Surface((sw, sh), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 200))
        surf.blit(ov, (0, 0))

        won = (self.winner == "survivors" and not self.i_am_monster) or \
              (self.winner == "monster"   and self.i_am_monster)

        p   = int(155 + 100 * abs(math.sin(self._anim * 2.5)))
        if won:
            bg_col = (0, int(p * 0.3), 0)
            tc     = (int(p * 0.6), p, int(p * 0.4))
            title  = "🏆 ПОБЕДА!"
            sub    = "Вы пережили эту ночь." if self.winner == "survivors" \
                     else "Монстр уничтожил всех!"
        else:
            bg_col = (int(p * 0.3), 0, 0)
            tc     = (p, int(p * 0.2), int(p * 0.2))
            title  = "💀 ПОРАЖЕНИЕ"
            sub    = "Тьма победила..." if self.winner == "monster" \
                     else "Выжившие сбежали!"

        bg_s = pygame.Surface((sw, sh), pygame.SRCALPHA)
        bg_s.fill((*bg_col, 60))
        surf.blit(bg_s, (0, 0))

        self._ptcls.draw(surf, 0, 0, sw, sh)

        t1 = self.f_t.render(title,    True, tc)
        t2 = self.f_sub.render(sub,    True, C_GRAY)
        t3 = self.f_hint.render("Нажмите любую клавишу — вернуться в меню",
                                True, (60, 60, 80))
        surf.blit(t1, t1.get_rect(centerx=sw//2, y=sh//2 - 100))
        surf.blit(t2, t2.get_rect(centerx=sw//2, y=sh//2 - 30))
        surf.blit(t3, t3.get_rect(centerx=sw//2, y=sh//2 + 60))


# ══════════════════════════════════════════════════════════════
#  ТАБЛИЦА СТАТИСТИКИ
# ══════════════════════════════════════════════════════════════

class StatsOverlay:
    def __init__(self):
        fn = pygame.font.SysFont
        self.f_title = fn("monospace", 18, bold=True)
        self.f_row   = fn("monospace", 15)
        self.f_hdr   = fn("monospace", 13)
        self.visible = False

    def toggle(self):
        self.visible = not self.visible

    def draw(self, surf, state, my_pid):
        if not self.visible or not state:
            return
        sw, sh = surf.get_size()
        players = state.get("players", {})
        n_rows  = max(2, len(players))
        W, H    = 520, 60 + n_rows * 28 + 20

        panel = pygame.Surface((W, H), pygame.SRCALPHA)
        panel.fill((8, 8, 18, 230))
        pygame.draw.rect(panel, (80, 80, 130), (0, 0, W, H), 2, border_radius=10)

        px = sw//2 - W//2
        py = sh//2 - H//2

        t = self.f_title.render("  СТАТИСТИКА ИГРОКОВ  [TAB]", True, C_CYAN)
        panel.blit(t, (W//2 - t.get_width()//2, 10))

        headers = ["Игрок", "Статус", "Очки", "Убийства", "Сбежал"]
        col_x   = [10, 120, 230, 320, 420]
        for i, h in enumerate(headers):
            ht = self.f_hdr.render(h, True, (130, 130, 170))
            panel.blit(ht, (col_x[i], 38))

        pygame.draw.line(panel, (60, 60, 100), (10, 52), (W - 10, 52), 1)

        for row_i, (pid, p) in enumerate(sorted(players.items())):
            y2   = 56 + row_i * 28
            is_me = (pid == my_pid)

            if p["is_monster"]:
                row_col = (220, 60, 60)
            elif is_me:
                row_col = C_ME
            elif p["alive"] and not p.get("escaped"):
                row_col = C_SURV
            else:
                row_col = C_DARK_GRAY

            if is_me:
                hl = pygame.Surface((W - 20, 24), pygame.SRCALPHA)
                hl.fill((80, 120, 200, 30))
                panel.blit(hl, (10, y2 - 2))

            cells = [
                pid + (" ★" if is_me else ""),
                "МОНСТР" if p["is_monster"] else
                ("СБЕЖАЛ" if p.get("escaped") else
                 ("ЖИВОЙ" if p["alive"] else "МЁРТВЫЙ")),
                str(p.get("score", 0)),
                str(p.get("kills", 0)),
                "Да" if p.get("escaped") else "Нет",
            ]
            for ci, cell in enumerate(cells):
                ct = self.f_row.render(cell, True, row_col)
                panel.blit(ct, (col_x[ci], y2))

        surf.blit(panel, (px, py))

        ai = state.get("ai_monster")
        if ai:
            at = self.f_hdr.render("  AI-монстр активен", True, (200, 50, 50))
            surf.blit(at, (px + 10, py + H + 4))


# ══════════════════════════════════════════════════════════════
#  ИГРОВОЙ ЭКРАН (ГЛАВНЫЙ)
# ══════════════════════════════════════════════════════════════

class GameScreen(BaseScreen):
    SPRITE_SIZE = 52

    def __init__(self, app):
        super().__init__(app)
        self.net       = None
        self.map_rend  = None
        self.minimap   = None
        self.camera    = Camera(2400, 1800)
        self.flash     = Flashlight()
        self.ptcls     = Particles()
        self.stats_ov  = StatsOverlay()
        fn = pygame.font.SysFont
        self.f_big   = fn("monospace", 34, bold=True)
        self.f_med   = fn("monospace", 20, bold=True)
        self.f_sm    = fn("monospace", 15)
        self.f_tiny  = fn("monospace", 12)
        self._frame       = 0
        self._ftimer      = 0.0
        self._prev_state  = None
        self._death_fired = False
        self._end_fired   = False
        self._map_built   = False
        self._anim        = 0.0
        self._roar_flash  = 0.0
        self._trap_flash  = 0.0
        self._msg_queue   = []
        self._show_tab    = False

    def setup(self, net):
        self.net          = net
        self.map_rend     = MapRenderer(net.map_w, net.map_h)
        self.minimap      = MiniMap(net.map_w, net.map_h)
        self.camera       = Camera(net.map_w, net.map_h)
        self.ptcls        = Particles()
        self.stats_ov     = StatsOverlay()
        self._prev_state  = None
        self._map_built   = False
        self._death_fired = False
        self._end_fired   = False
        self._frame       = 0
        self._anim        = 0.0
        self._roar_flash  = 0.0
        self._trap_flash  = 0.0
        self._msg_queue   = []
        self._show_tab    = False

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_p):
                self.app.set_screen("pause")
            elif event.key == pygame.K_RETURN and self.net:
                self.net.send_start()
            elif event.key == pygame.K_m and self.minimap:
                self.minimap.toggle()
            elif event.key == pygame.K_TAB:
                self.stats_ov.visible = True
        if event.type == pygame.KEYUP:
            if event.key == pygame.K_TAB:
                self.stats_ov.visible = False

    def _read_keys(self):
        k = pygame.key.get_pressed()
        mx = float((k[pygame.K_d] or k[pygame.K_RIGHT]) -
                   (k[pygame.K_a] or k[pygame.K_LEFT]))
        my = float((k[pygame.K_s] or k[pygame.K_DOWN]) -
                   (k[pygame.K_w] or k[pygame.K_UP]))
        if mx and my:
            mx *= 0.7071; my *= 0.7071
        sprint = bool(k[pygame.K_LSHIFT] or k[pygame.K_RSHIFT])
        silent = bool(k[pygame.K_LCTRL]  or k[pygame.K_RCTRL])
        return mx, my, sprint, silent

    def update(self, dt):
        if not self.net:
            return
        self._anim += dt

        state = self.net.get_state()
        if state and not self._map_built and state.get("walls"):
            self.map_rend.build(state["walls"])
            self.minimap.build_base(self.map_rend.walls)
            self._map_built = True

        me = self._get_me(state)
        mx, my, sprint, silent = self._read_keys()

        if me and me.get("alive", True) and not me.get("escaped", False):
            self.net.send_input(mx, my, sprint, silent)
        else:
            self.net.send_input(0, 0, False, False)

        self.net.update_ping(dt)

        self._ftimer += dt
        if self._ftimer >= 0.15 and (mx or my):
            self._ftimer = 0
            self._frame  = (self._frame + 1) % 4

        if me:
            sw, sh = self.app.screen.get_size()
            self.camera.update(me["x"], me["y"], sw, sh, dt)

        self.ptcls.update(dt)

        if me and me.get("alive") and (mx or my) and not me.get("is_monster"):
            if random.random() < 0.15:
                self.ptcls.emit_step(me["x"], me["y"])

        if state:
            self._process_events(state, me)
            self._check_particles(state)
            self._check_render_events(state, me)

        if self._roar_flash > 0:
            self._roar_flash = max(0.0, self._roar_flash - dt * 2.5)
        if self._trap_flash > 0:
            self._trap_flash = max(0.0, self._trap_flash - dt * 3.0)

        # FIX: use anim_t variable to avoid shadow conflicts in list comprehension
        self._msg_queue = [(msg, ttl - dt, col) for msg, ttl, col in self._msg_queue
                           if ttl - dt > 0]

        self._prev_state = state

    def _get_me(self, state):
        if not state or not self.net:
            return None
        return state.get("players", {}).get(self.net.pid)

    def _process_events(self, state, me):
        for ev in state.get("events", []):
            ev_type = ev.get("type")
            if ev_type == "killed":
                ev_pid = ev.get("pid")
                by  = ev.get("by", "??")
                self._msg_queue.append(
                    (f"{ev_pid} убит {by}!", 3.0, C_RED))
                if self.net and ev_pid == self.net.pid:
                    self.camera.shake(12)
                    self._roar_flash = 1.0
                else:
                    self.camera.shake(4)

            elif ev_type == "escaped":
                ev_pid = ev.get("pid")
                self._msg_queue.append(
                    (f"{ev_pid} сбежал!", 3.0, C_CYAN))
                if self.net and ev_pid == self.net.pid:
                    self.camera.shake(8)

            elif ev_type == "key_picked":
                ev_pid = ev.get("pid")
                self._msg_queue.append(
                    (f"{ev_pid} подобрал ключ!", 2.5, C_KEY))

            elif ev_type == "door_opened":
                self._msg_queue.append(
                    ("Дверь открыта! Бегите!", 4.0, C_DOOR_OPEN))

            elif ev_type == "trap_triggered":
                ev_pid = ev.get("pid")
                self._msg_queue.append(
                    (f"{ev_pid} попал в ловушку!", 2.0, C_TRAP))
                if self.net and ev_pid == self.net.pid:
                    self.camera.shake(8)
                    self._trap_flash = 1.0

    def _check_particles(self, state):
        if not state or not self._prev_state:
            return
        prev_players = self._prev_state.get("players", {})

        for pid, p in state.get("players", {}).items():
            prev = prev_players.get(pid, {})
            if prev.get("alive", True) and not p.get("alive", True):
                self.ptcls.emit_death(p["x"], p["y"])
                self.camera.shake(8)
            if not prev.get("escaped", False) and p.get("escaped", False):
                self.ptcls.emit_escape(p["x"], p["y"])

        prev_keys = {k["kid"]: k for k in self._prev_state.get("keys", [])}
        for key in state.get("keys", []):
            pk = prev_keys.get(key["kid"])
            if pk and pk.get("on_map") and not key.get("on_map"):
                self.ptcls.emit_pickup(pk["x"], pk["y"])

        prev_traps = {tr["tid"]: tr for tr in self._prev_state.get("traps", [])}
        for trap in state.get("traps", []):
            pt = prev_traps.get(trap["tid"])
            if pt and pt.get("active") and not trap.get("active"):
                self.ptcls.emit_trap(trap["x"], trap["y"])

    def _check_render_events(self, state, me):
        if not state or not me:
            return
        if not me.get("alive", True) and not self._death_fired:
            self._death_fired  = True
            self.app.death_pending = True
            self.app.death_timer   = 0.0

        if state.get("game_over") and not self._end_fired:
            self._end_fired = True
            end = self.app.screens["end"]
            end.winner       = state.get("winner")
            end.i_am_monster = me.get("is_monster", False)
            self.app.end_pending = True
            self.app.end_timer   = 0.0

        ai = state.get("ai_monster")
        if ai and ai.get("roar_event"):
            self._roar_flash = 0.5
            self.camera.shake(6)
            self._msg_queue.append(("МОНСТР ПОЧУЯЛ ВАС!", 2.0, C_RED))

    def draw(self, surf):
        try:
            self._draw_internal(surf)
        except Exception as e:
            # FIX: catch render errors so game doesn't crash, show error overlay
            print(f"[DRAW ERROR] {e}")
            import traceback
            traceback.print_exc()
            f_err = get_font("monospace", 16, bold=True)
            sw, sh = surf.get_size()
            t = f_err.render(f"Render error: {e}", True, C_RED)
            surf.blit(t, (10, sh//2))

    def _draw_internal(self, surf):
        state  = self.net.get_state() if self.net else None
        me     = self._get_me(state)
        sw, sh = surf.get_size()

        surf.fill(C_BG)

        # FIX: clamp blit area to prevent Rect-extends-outside-surface crash
        if self.map_rend and self.map_rend.surface:
            cam_x = int(self.camera.x)
            cam_y = int(self.camera.y)
            map_w = self.map_rend.map_w
            map_h = self.map_rend.map_h
            # Clamp so the src rect never goes out of the map surface bounds
            src_x = clamp(cam_x, 0, max(0, map_w - 1))
            src_y = clamp(cam_y, 0, max(0, map_h - 1))
            src_w = min(sw, map_w - src_x)
            src_h = min(sh, map_h - src_y)
            if src_w > 0 and src_h > 0:
                surf.blit(self.map_rend.surface, (0, 0),
                          pygame.Rect(src_x, src_y, src_w, src_h))

        if state:
            self._draw_traps(surf, state, me)
            self._draw_items(surf, state)
            is_monster = me and me.get("is_monster", False)
            if is_monster:
                self._draw_noise(surf, state)
            self._draw_characters(surf, state, me)

        self.ptcls.draw(surf, self.camera.x, self.camera.y, sw, sh)

        if me:
            sx, sy = self.camera.to_screen(me["x"], me["y"])
            radius = FLASHLIGHT_MONSTER if me.get("is_monster") else FLASHLIGHT_RADIUS
            is_dead = not me.get("alive", True)
            self.flash.draw(surf, sx, sy, radius,
                            is_dead=is_dead,
                            is_monster=me.get("is_monster", False))

        if self._roar_flash > 0:
            fs = pygame.Surface((sw, sh), pygame.SRCALPHA)
            fa = int(80 * self._roar_flash)
            fs.fill((150, 0, 0, fa))
            surf.blit(fs, (0, 0))

        if self._trap_flash > 0:
            fs2 = pygame.Surface((sw, sh), pygame.SRCALPHA)
            fa2 = int(70 * self._trap_flash)
            fs2.fill((120, 0, 120, fa2))
            surf.blit(fs2, (0, 0))

        self._draw_hud(surf, state, me, sw, sh)

        if state and self.minimap:
            self.minimap.draw(surf, state,
                              self.net.pid if self.net else None,
                              sw, sh, self.app._dt)

        self._draw_messages(surf, sw, sh)
        self.stats_ov.draw(surf, state, self.net.pid if self.net else None)

    def _draw_traps(self, surf, state, me):
        cam = self.camera
        is_monster = me and me.get("is_monster", False)

        for trap in state.get("traps", []):
            if not trap.get("visible") and trap.get("active", True):
                continue
            sx, sy = cam.to_screen(trap["x"], trap["y"])

            if not (-20 < sx < surf.get_width()+20 and -20 < sy < surf.get_height()+20):
                continue

            if trap.get("active"):
                t_anim = int(100 + 80 * abs(math.sin(self._anim * 3 + trap["tid"])))
                col    = (t_anim, 0, t_anim)
                pygame.draw.rect(surf, (50, 20, 50), (sx-10, sy-4, 20, 8))
                for i in range(5):
                    tx_ = sx - 8 + i * 4
                    pygame.draw.polygon(surf, col, [
                        (tx_, sy-4), (tx_+2, sy-4), (tx_+1, sy-9)
                    ])
                glow = pygame.Surface((40, 40), pygame.SRCALPHA)
                pygame.draw.circle(glow, (*col, 60), (20, 20), 18)
                surf.blit(glow, (sx-20, sy-20))

                if is_monster:
                    f = get_font("monospace", 11)
                    lt = f.render("ЛОВУШКА", True, C_TRAP)
                    surf.blit(lt, (sx - lt.get_width()//2, sy - 22))
            else:
                pygame.draw.circle(surf, (50, 30, 50), (sx, sy), 8)
                pygame.draw.circle(surf, (80, 40, 80), (sx, sy), 8, 2)

    def _draw_items(self, surf, state):
        cam = self.camera
        t   = self._anim

        for key in state.get("keys", []):
            if not key.get("on_map"):
                continue
            sx, sy = cam.to_screen(key["x"], key["y"])
            if not (-30 < sx < surf.get_width()+30 and -30 < sy < surf.get_height()+30):
                continue

            bob    = int(6 * math.sin(t * 2.2 + key["kid"] * 1.2))
            pulse  = int(180 + 75 * abs(math.sin(t * 2.8 + key["kid"])))

            glow_r = max(1, int(22 + 8 * abs(math.sin(t * 2.5))))
            glow   = pygame.Surface((glow_r*2+4, glow_r*2+4), pygame.SRCALPHA)
            pygame.draw.circle(glow, (255, 200, 0, 70), (glow_r+2, glow_r+2), glow_r)
            surf.blit(glow, (sx - glow_r - 2, sy + bob - glow_r - 2))

            key_col = (pulse, int(pulse * 0.85), 0)
            pygame.draw.circle(surf, key_col, (sx, sy + bob), 9)
            pygame.draw.circle(surf, (50, 35, 0), (sx, sy + bob), 9, 2)
            pygame.draw.line(surf, key_col, (sx + 5, sy + bob), (sx + 16, sy + bob), 4)
            pygame.draw.line(surf, key_col, (sx + 12, sy + bob), (sx + 12, sy + bob + 5), 3)
            pygame.draw.line(surf, key_col, (sx + 16, sy + bob), (sx + 16, sy + bob + 5), 3)

            f = get_font("monospace", 11)
            lbl = f.render(f"КЛЮЧ {key['kid']+1}", True, key_col)
            surf.blit(lbl, (sx - lbl.get_width()//2, sy + bob - 28))

        for door in state.get("doors", []):
            sx, sy = cam.to_screen(door["x"], door["y"])
            if not (-30 < sx < surf.get_width()+30 and -30 < sy < surf.get_height()+30):
                continue

            is_open = door.get("open", False)
            col     = C_DOOR_OPEN if is_open else C_DOOR

            pygame.draw.rect(surf, (25, 55, 60), (sx - 20, sy - 36, 40, 72))
            door_col = (0, int(60 + 80 * (1 if is_open else 0)),
                        int(80 + 80 * (1 if is_open else 0)))
            pygame.draw.rect(surf, door_col, (sx - 17, sy - 33, 34, 66), border_radius=2)
            pygame.draw.rect(surf, col, (sx - 20, sy - 36, 40, 72), 3, border_radius=3)
            pygame.draw.circle(surf, (200, 200, 200), (sx + 10, sy), 4)

            if is_open:
                arr_pulse = int(200 + 55 * abs(math.sin(t * 4)))
                arr_col   = (0, arr_pulse, int(arr_pulse * 0.7))
                pygame.draw.polygon(surf, arr_col, [
                    (sx, sy - 20), (sx + 14, sy), (sx, sy + 20)
                ])
                door_glow = pygame.Surface((60, 60), pygame.SRCALPHA)
                pygame.draw.circle(door_glow, (*arr_col, 50), (30, 30), 28)
                surf.blit(door_glow, (sx - 30, sy - 30))

            f = get_font("monospace", 12)
            status = "ОТКРЫТА!" if is_open else "ЗАПЕРТА"
            lbl = f.render(status, True, col)
            surf.blit(lbl, (sx - lbl.get_width()//2, sy - 52))

            if not is_open:
                kn = door.get("keys_needed", 1)
                kl = f.render(f"Нужно ключей: {kn}", True, C_YELLOW)
                surf.blit(kl, (sx - kl.get_width()//2, sy - 66))

    def _draw_noise(self, surf, state):
        for ev in state.get("noise_events", []):
            r  = max(1, int(ev["radius"]))
            sx = int(ev["x"] - self.camera.x)
            sy = int(ev["y"] - self.camera.y)
            ttl = ev.get("ttl", 0)
            a   = clamp(int(180 * ttl / 2.0), 0, 200)

            ring = pygame.Surface((r*2 + 8, r*2 + 8), pygame.SRCALPHA)
            pygame.draw.circle(ring, (*C_NOISE, a//3), (r+4, r+4), r)
            pygame.draw.circle(ring, (*C_NOISE, a),    (r+4, r+4), r, 2)
            surf.blit(ring, (sx - r - 4, sy - r - 4))

            center_s = pygame.Surface((12, 12), pygame.SRCALPHA)
            pygame.draw.circle(center_s, (*C_NOISE, a), (6, 6), 5)
            surf.blit(center_s, (sx - 6, sy - 6))

    def _draw_characters(self, surf, state, me):
        cam    = self.camera
        my_pid = self.net.pid if self.net else None
        S      = self.SPRITE_SIZE
        hs     = S // 2

        ai = state.get("ai_monster")
        if ai:
            sx, sy = cam.to_screen(ai["x"], ai["y"])
            if -60 < sx < surf.get_width()+60 and -60 < sy < surf.get_height()+60:
                char_s = pygame.Surface((S, S), pygame.SRCALPHA)
                CharRenderer.draw_monster(
                    char_s, S//2, S//2, S,
                    frame=ai.get("anim_frame", 0),
                    is_ai=True,
                    state_name=ai.get("ai_state", "patrol"),
                    sprinting=ai.get("sprinting", False))
                surf.blit(char_s, (sx - hs, sy - hs))
                self._draw_label(surf, sx, sy - hs + 2, "AI МОНСТР", C_MONSTER, big=True)

        for pid, p in state.get("players", {}).items():
            sx, sy = cam.to_screen(p["x"], p["y"])
            if not (-80 < sx < surf.get_width()+80 and -80 < sy < surf.get_height()+80):
                continue

            is_me   = (pid == my_pid)
            alive   = p.get("alive", True)
            escaped = p.get("escaped", False)

            char_s = pygame.Surface((S + 16, S + 16), pygame.SRCALPHA)

            if not alive:
                CharRenderer.draw_dead(char_s, (S+16)//2, (S+16)//2, S)
            elif p["is_monster"]:
                CharRenderer.draw_monster(
                    char_s, (S+16)//2, (S+16)//2, S,
                    frame=self._frame,
                    state_name="chase" if p.get("sprinting") else "patrol",
                    sprinting=p.get("sprinting", False))
            else:
                try:
                    idx = int(''.join(filter(str.isdigit, pid))) - 1
                except Exception:
                    idx = 0
                colors = CharRenderer.SURVIVOR_COLORS[idx % len(CharRenderer.SURVIVOR_COLORS)]
                body_col, shadow_col = colors[0], colors[1]

                if is_me:
                    body_col   = C_ME
                    shadow_col = (40, 130, 200)

                CharRenderer.draw_survivor(
                    char_s, (S+16)//2, (S+16)//2, S,
                    body_col=body_col,
                    shadow_col=shadow_col,
                    frame=self._frame,
                    is_me=is_me,
                    sprinting=p.get("sprinting", False),
                    silent=p.get("silent", False),
                    has_key=p.get("has_key", False),
                    trap_slow=p.get("trap_slow", 0.0))

            surf.blit(char_s, (sx - (S+16)//2, sy - (S+16)//2))

            if p["is_monster"] and alive:
                self._draw_label(surf, sx, sy - hs - 10, "МОНСТР", C_MONSTER, big=True)
            elif escaped:
                self._draw_label(surf, sx, sy - hs - 10, f"{pid} ✓ СПАСЁН", C_CYAN)
            elif is_me:
                self._draw_label(surf, sx, sy - hs - 10, "ВЫ", C_ME)
            elif alive:
                self._draw_label(surf, sx, sy - hs - 10, pid, C_SURV)
            else:
                self._draw_label(surf, sx, sy - hs - 10, f"{pid} ✝", C_DARK_GRAY)

    def _draw_label(self, surf, sx, sy, text, col, big=False):
        # FIX: use cached fonts instead of creating new SysFont every frame
        f = get_font("monospace", 13 if big else 11, bold=big)
        t = f.render(text, True, col)
        ts = f.render(text, True, (0, 0, 0))
        surf.blit(ts, (sx - t.get_width()//2 + 1, sy + 1))
        surf.blit(t, (sx - t.get_width()//2, sy))

    def _draw_hud(self, surf, state, me, sw, sh):
        if not state:
            return

        hud_h = 56
        panel = pygame.Surface((sw, hud_h), pygame.SRCALPHA)
        panel.fill((5, 5, 12, 220))
        pygame.draw.line(panel, (60, 60, 100), (0, hud_h-1), (sw, hud_h-1), 1)
        surf.blit(panel, (0, 0))

        tl      = state.get("time_left", 0)
        tc      = C_GREEN if tl > 90 else (C_YELLOW if tl > 30 else C_RED)
        mm, ss  = divmod(int(tl), 60)
        timer_t = self.f_big.render(f"⏱ {mm:02d}:{ss:02d}", True, tc)
        surf.blit(timer_t, timer_t.get_rect(centerx=sw//2, y=8))

        if me:
            if me["is_monster"]:
                status, sc = "👹 МОНСТР", C_MONSTER
            elif me.get("escaped"):
                status, sc = "✈ СПАСЁН", C_CYAN
            elif me["alive"]:
                status, sc = "♥ ЖИВОЙ", C_GREEN
            else:
                status, sc = "✝ МЁРТВЫЙ", C_DEAD
            surf.blit(self.f_med.render(status, True, sc), (14, 8))

            keys_held = me.get("keys_held", 0)
            if keys_held > 0:
                kl = self.f_sm.render(f"🔑 x{keys_held}", True, C_KEY)
                surf.blit(kl, (14, 30))

            if me.get("trap_slow", 0) > 0:
                sl = self.f_sm.render(f"⚠ ЗАМЕДЛЕН {me['trap_slow']:.1f}с", True, C_TRAP)
                surf.blit(sl, (180, 30))

        players    = state.get("players", {})
        alive_n    = sum(1 for p in players.values()
                         if not p["is_monster"] and p["alive"] and not p.get("escaped"))
        escaped_n  = sum(1 for p in players.values() if p.get("escaped"))
        total_n    = sum(1 for p in players.values() if not p["is_monster"])
        info       = f"Живых: {alive_n}/{total_n}  Сбежало: {escaped_n}"
        info_surf  = self.f_sm.render(info, True, C_HUD_TEXT)
        surf.blit(info_surf, (sw - info_surf.get_width() - 14, 10))

        ping = self.net.get_ping() if self.net else 0
        ping_col = C_GREEN if ping < 50 else (C_YELLOW if ping < 120 else C_RED)
        pt = self.f_tiny.render(f"PING: {ping}ms", True, ping_col)
        surf.blit(pt, (sw - pt.get_width() - 14, 30))

        if state.get("ai_mode"):
            at = self.f_tiny.render("⚡ AI MODE", True, (180, 40, 40))
            surf.blit(at, (14, 42))

        if state.get("started") and me and me.get("alive") and not me.get("is_monster"):
            hint_s = pygame.Surface((sw, 22), pygame.SRCALPHA)
            hint_s.fill((5, 5, 12, 160))
            surf.blit(hint_s, (0, sh - 22))
            h = self.f_tiny.render(
                "SHIFT — спринт  |  CTRL — тихо  |  P — пауза  |  TAB — стат  |  M — карта  |  Найди ключ 🔑 → дверь 🚪",
                True, (50, 50, 75))
            surf.blit(h, (8, sh - 18))

        if not state.get("started"):
            self._draw_waiting(surf, state, sw, sh)

    def _draw_waiting(self, surf, state, sw, sh):
        ov = pygame.Surface((sw, sh), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 150))
        surf.blit(ov, (0, 0))

        W, H = 500, 300
        px   = sw//2 - W//2
        py   = sh//2 - H//2
        panel = pygame.Surface((W, H), pygame.SRCALPHA)
        panel.fill((10, 10, 20, 240))
        pygame.draw.rect(panel, (70, 70, 110), (0, 0, W, H), 2, border_radius=12)
        surf.blit(panel, (px, py))

        wt = self.f_big.render("Ожидание игроков...", True, C_HUD_TEXT)
        st = self.f_med.render("[ENTER] — начать игру", True, C_YELLOW)
        surf.blit(wt, wt.get_rect(centerx=sw//2, y=py + 14))
        surf.blit(st, st.get_rect(centerx=sw//2, y=py + 52))

        players = state.get("players", {})
        pygame.draw.line(surf, (50, 50, 80),
                         (px + 20, py + 85), (px + W - 20, py + 85), 1)
        for i, (pid, p) in enumerate(players.items()):
            col  = C_MONSTER if p["is_monster"] else C_SURV
            role = "МОНСТР" if p["is_monster"] else "выживший"
            is_me = (self.net and pid == self.net.pid)
            ls = self.f_sm.render(
                f"  {'→' if is_me else '·'} {pid} — {role}" +
                (" (ВЫ)" if is_me else ""), True, col)
            surf.blit(ls, (px + 20, py + 94 + i * 26))

        goal = self.f_sm.render(
            "Цель: собрать все 🔑 и сбежать через 🚪", True, C_GRAY)
        surf.blit(goal, goal.get_rect(centerx=sw//2, y=py + H - 34))

    def _draw_messages(self, surf, sw, sh):
        y_offset = 70
        for msg, ttl, col in reversed(self._msg_queue[-6:]):
            a   = min(1.0, ttl * 2)
            msg_w = max(1, len(msg)*9 + 20)
            bg  = pygame.Surface((msg_w, 28), pygame.SRCALPHA)
            bg.fill((0, 0, 0, int(160 * a)))
            bx  = sw//2 - bg.get_width()//2
            surf.blit(bg, (bx, y_offset))
            t   = self.f_sm.render(msg, True,
                                   tuple(clamp(int(c * a), 0, 255) for c in col[:3]))
            surf.blit(t, (sw//2 - t.get_width()//2, y_offset + 4))
            y_offset += 32


# ══════════════════════════════════════════════════════════════
#  ПРИЛОЖЕНИЕ
# ══════════════════════════════════════════════════════════════

class App:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("HORROR LAN v4.0 ULTRA")

        try:
            icon = pygame.Surface((32, 32))
            icon.fill((10, 10, 20))
            pygame.draw.circle(icon, (220, 30, 30), (16, 16), 12)
            pygame.draw.circle(icon, (0, 0, 0), (16, 16), 4)
            pygame.display.set_icon(icon)
        except Exception:
            pass

        self.screen     = pygame.display.set_mode((WIN_W, WIN_H), pygame.RESIZABLE)
        self.clock      = pygame.time.Clock()
        self.running    = True
        self.fullscreen = False
        self.net        = None
        self._dt        = 0.016

        self.death_pending = False
        self.death_timer   = 0.0
        self.end_pending   = False
        self.end_timer     = 0.0

        self.screens = {
            "menu":  MenuScreen(self),
            "game":  GameScreen(self),
            "pause": PauseScreen(self),
            "death": DeathScreen(self),
            "end":   EndScreen(self),
        }
        self._name   = "menu"
        self.current = self.screens["menu"]
        self.current.on_enter()

    def set_screen(self, name):
        self._name   = name
        self.current = self.screens[name]
        self.current.on_enter()

    def connect_and_play(self, host):
        self.disconnect()
        net = NetworkClient(host)
        print(f"[APP] Connecting to {host}:{PORT} ...")
        if not net.connect():
            return False
        deadline = time.time() + 8.0
        while not net.pid and time.time() < deadline:
            time.sleep(0.05)
        if not net.pid:
            print("[APP] Server did not respond (hello).")
            net.disconnect()
            return False
        self.net = net
        game = self.screens["game"]
        game.setup(net)
        self.set_screen("game")
        return True

    def disconnect(self):
        if self.net:
            self.net.disconnect()
            self.net = None
        self.death_pending = False
        self.end_pending   = False

    def toggle_fullscreen(self):
        self.fullscreen = not self.fullscreen
        if self.fullscreen:
            info = pygame.display.Info()
            self.screen = pygame.display.set_mode(
                (info.current_w, info.current_h), pygame.FULLSCREEN)
        else:
            self.screen = pygame.display.set_mode((WIN_W, WIN_H), pygame.RESIZABLE)

    def run(self):
        while self.running:
            self._dt = self.clock.tick(FPS) / 1000.0
            dt = min(self._dt, 0.05)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_F11:
                    self.toggle_fullscreen()
                elif event.type == pygame.VIDEORESIZE and not self.fullscreen:
                    self.screen = pygame.display.set_mode(event.size, pygame.RESIZABLE)
                try:
                    self.current.handle_event(event)
                except Exception as e:
                    print(f"[EVENT ERROR] {e}")

            try:
                self.current.update(dt)
            except Exception as e:
                print(f"[UPDATE ERROR] {e}")
                import traceback
                traceback.print_exc()

            if self.death_pending and self._name == "game":
                self.death_timer += dt
                if self.death_timer >= 2.0:
                    self.death_pending = False
                    self.set_screen("death")

            if self.end_pending and self._name == "game":
                self.end_timer += dt
                if self.end_timer >= 3.0:
                    self.end_pending = False
                    self.set_screen("end")

            if self._name == "pause":
                self.screens["game"].draw(self.screen)

            try:
                self.current.draw(self.screen)
            except Exception as e:
                print(f"[DRAW ERROR] {e}")
                import traceback
                traceback.print_exc()

            pygame.display.flip()

        self.disconnect()
        pygame.quit()


# ══════════════════════════════════════════════════════════════
#  ТОЧКА ВХОДА
# ══════════════════════════════════════════════════════════════

def main():
    print("=" * 62)
    print("  HORROR LAN — CLIENT v4.0 ULTRA EDITION (FIXED)")
    print("=" * 62)
    print(f"  Подключение к серверу на порту {PORT}")
    print("  Управление: WASD, SHIFT/CTRL, P, TAB, M, F11")
    print("=" * 62)
    app = App()
    app.run()
    

if __name__ == "__main__":
    main()

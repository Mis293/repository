"""
╔══════════════════════════════════════════════════════════════════╗
║  HORROR LAN — CLIENT v3.0                                      ║
║                                                                  ║
║  Управление:                                                     ║
║  WASD / стрелки — движение                                       ║
║  SHIFT — бег (громко, быстро)                                    ║
║  CTRL — тихо (тихо, медленно)                                    ║
║  P / ESC — пауза                                                 ║
║  ENTER — начать игру (любой игрок)                               ║
║  F11 — полноэкранный режим                                       ║
║                                                                  ║
║  Установка: pip install pygame                                    ║
╚══════════════════════════════════════════════════════════════════╝
"""

import pygame
import socket
import threading
import json
import math
import time
import random
import sys

# ══════════════════════════════════════════════════════════════
#  КОНФИГУРАЦИЯ
# ══════════════════════════════════════════════════════════════

PORT       = 5555
DEFAULT_HOST = "127.0.0.1"
FPS        = 60
WIN_W, WIN_H = 1280, 720

FLASHLIGHT_SURVIVOR = 150
FLASHLIGHT_MONSTER  = 9999
DARKNESS_ALPHA      = 220
CAM_LERP            = 7.0

MINIMAP_BG     = (15, 15, 25)
MINIMAP_WALL   = (60, 80, 140)
MINIMAP_SURV   = (60, 210, 80)
MINIMAP_MONSTER= (220, 40, 40)
MINIMAP_KEY    = (255, 220, 0)
MINIMAP_DOOR   = (0, 200, 200)
MINIMAP_ME     = (100, 200, 255)

BG      = (10, 10, 16)
FLOOR_A = (26, 26, 38)
FLOOR_B = (22, 22, 34)
WALL_C  = (50, 50, 68)
WALL_E  = (65, 65, 85)
SURV_C  = (70, 185, 100)
MONST_C = (215, 35, 35)
MONST_G = (255, 85, 85)
DEAD_C  = (85, 85, 95)
ME_C    = (100, 195, 255)
KEY_C   = (255, 215, 0)
DOOR_C  = (0, 200, 200)
DOOR_OC = (0, 255, 180)
NOISE_C = (255, 135, 25)
HUD_TEXT= (200, 200, 215)
RED     = (215, 35, 35)
GREEN   = (65, 205, 75)
YELLOW  = (255, 195, 25)
CYAN    = (75, 195, 255)
WHITE   = (255, 255, 255)
GRAY    = (115, 115, 130)
BLACK   = (0, 0, 0)

# ══════════════════════════════════════════════════════════════
#  УТИЛИТЫ
# ══════════════════════════════════════════════════════════════

def dist(ax, ay, bx, by) -> float:
    return math.hypot(ax - bx, ay - by)

def lerp(a, b, t) -> float:
    return a + (b - a) * t

def clamp(v, lo, hi):
    return max(lo, min(hi, v))

# ══════════════════════════════════════════════════════════════
#  ЗВУКОВОЙ МЕНЕДЖЕР (ЗАГЛУШКА — БЕЗ ЗВУКА)
# ══════════════════════════════════════════════════════════════

class SoundManager:
    """Заглушка: все методы ничего не делают."""
    def play(self, name: str, loops: int = 0):
        pass
    def stop(self, name: str):
        pass

# ══════════════════════════════════════════════════════════════
#  СЕТЕВОЙ КЛИЕНТ
# ══════════════════════════════════════════════════════════════

class NetworkClient:
    def __init__(self, host: str):
        self.host    = host
        self.pid     = None
        self.map_w   = 1600
        self.map_h   = 1200
        self.ai_mode = False
        self.alive   = False
        self._sock   = None
        self._state  = None
        self._lock   = threading.Lock()
        self._buf    = ""

    def connect(self) -> bool:
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._sock.settimeout(5.0)
            self._sock.connect((self.host, PORT))
            self._sock.settimeout(None)
            self.alive = True
            threading.Thread(target=self._recv_loop, daemon=True).start()
            return True
        except Exception as e:
            print(f"[NET] Ошибка: {e}")
            return False

    def _recv_loop(self):
        while self.alive:
            try:
                chunk = self._sock.recv(16384)
                if not chunk:
                    break
                self._buf += chunk.decode("utf-8", errors="ignore")
                while "\n" in self._buf:
                    line, self._buf = self._buf.split("\n", 1)
                    self._on_msg(line.strip())
            except Exception:
                break
        self.alive = False

    def _on_msg(self, raw: str):
        if not raw:
            return
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            return
        t = msg.get("type")
        if t == "hello":
            self.pid     = msg["pid"]
            self.map_w   = msg.get("map_w", 1600)
            self.map_h   = msg.get("map_h", 1200)
            self.ai_mode = msg.get("ai_mode", False)
        elif t == "state":
            with self._lock:
                self._state = msg

    def get_state(self) -> dict | None:
        with self._lock:
            return self._state

    def send_input(self, mx, my, sprint, silent):
        self._send({"type": "input", "mx": mx, "my": my,
                    "sprint": sprint, "silent": silent})

    def send_start(self):
        self._send({"type": "start"})

    def _send(self, obj: dict):
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
#  ОТРИСОВКА КАРТЫ
# ══════════════════════════════════════════════════════════════

class MapRenderer:
    TILE = 64

    def __init__(self, map_w, map_h):
        self.map_w   = map_w
        self.map_h   = map_h
        self.walls   : list[pygame.Rect] = []
        self.surface : pygame.Surface | None = None

    def build(self, walls_data):
        self.walls = [pygame.Rect(*w) for w in walls_data]
        ts   = self.TILE
        cols = self.map_w // ts + 1
        rows = self.map_h // ts + 1
        surf = pygame.Surface((self.map_w, self.map_h))
        surf.fill(BG)
        for r in range(rows):
            for c in range(cols):
                col = FLOOR_A if (r + c) % 2 == 0 else FLOOR_B
                pygame.draw.rect(surf, col, (c*ts, r*ts, ts, ts))
        for w in self.walls:
            pygame.draw.rect(surf, WALL_C, w)
            pygame.draw.line(surf, WALL_E, (w.right, w.top+2),  (w.right, w.bottom), 2)
            pygame.draw.line(surf, WALL_E, (w.left+2, w.bottom),(w.right, w.bottom), 2)
        self.surface = surf

# ══════════════════════════════════════════════════════════════
#  ФОНАРИК
# ══════════════════════════════════════════════════════════════

class Flashlight:
    def __init__(self):
        self._dark  : pygame.Surface | None = None
        self._sw = self._sh = 0
        self._masks : dict[int, pygame.Surface] = {}

    def _ensure(self, sw, sh):
        if sw != self._sw or sh != self._sh:
            self._sw, self._sh = sw, sh
            self._dark = pygame.Surface((sw, sh), pygame.SRCALPHA)

    def _mask(self, r):
        if r not in self._masks:
            d = r * 2
            s = pygame.Surface((d, d), pygame.SRCALPHA)
            for ri in range(r, 0, -4):
                a = int(DARKNESS_ALPHA * (ri / r) ** 1.7)
                pygame.draw.circle(s, (0,0,0,a), (r,r), ri)
            self._masks[r] = s
        return self._masks[r]

    def draw(self, surf, cx, cy, radius, is_dead=False):
        if radius >= 9999:
            return
        sw, sh = surf.get_size()
        self._ensure(sw, sh)
        dark = self._dark
        dark.fill((0, 0, 0, DARKNESS_ALPHA))
        if not is_dead and 0 < cx < sw and 0 < cy < sh:
            m = self._mask(radius)
            dark.blit(m, (cx-radius, cy-radius),
                      special_flags=pygame.BLEND_RGBA_MIN)
        surf.blit(dark, (0, 0))

# ══════════════════════════════════════════════════════════════
#  МИНИ-КАРТА
# ══════════════════════════════════════════════════════════════

class MiniMap:
    SIZE = 150

    def __init__(self, map_w, map_h):
        self.map_w = map_w
        self.map_h = map_h
        self.scale = self.SIZE / max(map_w, map_h)
        self._base : pygame.Surface | None = None

    def build_base(self, walls):
        s  = self.SIZE
        sc = self.scale
        surf = pygame.Surface((s, s), pygame.SRCALPHA)
        surf.fill((*MINIMAP_BG, 210))
        pygame.draw.rect(surf, (60,60,90), (0,0,s,s), 1)
        for w in walls:
            pygame.draw.rect(surf, MINIMAP_WALL,
                (int(w.x*sc), int(w.y*sc),
                 max(2, int(w.width*sc)), max(2, int(w.height*sc))))
        self._base = surf

    def draw(self, surf, state, my_pid, screen_w, margin=10):
        if self._base is None:
            return
        s  = self.SIZE
        sc = self.scale
        mm = self._base.copy()
        rx = screen_w - s - margin
        ry = margin + 50

        key = state.get("key")
        if key and key.get("on_map"):
            pygame.draw.circle(mm, MINIMAP_KEY,
                (int(key["x"]*sc), int(key["y"]*sc)), 4)

        door = state.get("door")
        if door:
            dx, dy = int(door["x"]*sc), int(door["y"]*sc)
            color  = MINIMAP_DOOR if not door.get("open") else (0,255,180)
            pygame.draw.rect(mm, color, (dx-3, dy-3, 7, 7))

        ai = state.get("ai_monster")
        if ai:
            pygame.draw.circle(mm, MINIMAP_MONSTER,
                (int(ai["x"]*sc), int(ai["y"]*sc)), 5)

        for pid, p in state.get("players", {}).items():
            px, py = int(p["x"]*sc), int(p["y"]*sc)
            if p["is_monster"]:      col = MINIMAP_MONSTER
            elif pid == my_pid:      col = MINIMAP_ME
            elif p["alive"]:         col = MINIMAP_SURV
            else:                    col = (80,80,80)
            r = 5 if p["is_monster"] else 3
            pygame.draw.circle(mm, col, (px, py), r)

        surf.blit(mm, (rx, ry))

        font = pygame.font.SysFont("monospace", 10)
        items = [("● Вы", MINIMAP_ME), ("● Игроки", MINIMAP_SURV),
                 ("● Монстр", MINIMAP_MONSTER), ("■ Ключ", MINIMAP_KEY),
                 ("■ Дверь", MINIMAP_DOOR)]
        for i, (label, col) in enumerate(items):
            t = font.render(label, True, col)
            surf.blit(t, (rx, ry + s + 2 + i*12))

# ══════════════════════════════════════════════════════════════
#  СПРАЙТЫ
# ══════════════════════════════════════════════════════════════

class Sprites:
    SIZE = 48
    _cache: dict[tuple, pygame.Surface] = {}

    @classmethod
    def get(cls, role, is_me=False, alive=True, frame=0):
        key = (role, is_me, alive, frame % 4)
        if key not in cls._cache:
            cls._cache[key] = cls._draw(*key)
        return cls._cache[key]

    @classmethod
    def _draw(cls, role, is_me, alive, frame):
        S = cls.SIZE
        surf = pygame.Surface((S, S), pygame.SRCALPHA)
        if not alive:
            cls._dead(surf, S)
        elif role == "monster":
            cls._monster(surf, S, frame)
        else:
            cls._survivor(surf, S, ME_C if is_me else SURV_C, frame)
        return surf

    @staticmethod
    def _survivor(surf, S, color, frame):
        cx, cy = S//2, S//2
        leg = [0,5,0,-5][frame]
        pygame.draw.rect(surf, color, (cx-6, cy-2, 12, 14), border_radius=3)
        pygame.draw.circle(surf, color, (cx, cy-10), 8)
        pygame.draw.circle(surf, BLACK, (cx-3, cy-11), 1)
        pygame.draw.circle(surf, BLACK, (cx+3, cy-11), 1)
        pygame.draw.line(surf, color, (cx-6, cy+1), (cx-12, cy+7), 3)
        pygame.draw.line(surf, color, (cx+6, cy+1), (cx+12, cy+7), 3)
        fl = pygame.Surface((16,16), pygame.SRCALPHA)
        pygame.draw.circle(fl, (255,240,150,200), (8,8), 8)
        surf.blit(fl, (cx+5, cy+0))
        pygame.draw.circle(surf, (255,240,150), (cx+13, cy+8), 4)
        pygame.draw.line(surf, color, (cx-3, cy+12), (cx-4, cy+22+leg), 3)
        pygame.draw.line(surf, color, (cx+3, cy+12), (cx+4, cy+22-leg), 3)

    @staticmethod
    def _monster(surf, S, frame):
        cx, cy = S//2, S//2
        leg = [0,3,0,-3][frame]
        glow = pygame.Surface((S,S), pygame.SRCALPHA)
        pygame.draw.circle(glow, (200,0,0,45), (cx,cy), 22)
        surf.blit(glow, (0,0))
        body = [(cx-9,cy+13),(cx+9,cy+13),(cx+11,cy-5),(cx-11,cy-5)]
        pygame.draw.polygon(surf, MONST_C, body)
        pygame.draw.circle(surf, MONST_C, (cx, cy-11), 9)
        pygame.draw.line(surf, (170,18,18), (cx-6,cy-18), (cx-11,cy-30), 3)
        pygame.draw.line(surf, (170,18,18), (cx+6,cy-18), (cx+11,cy-30), 3)
        pygame.draw.circle(surf, (255,215,0), (cx-4,cy-13), 3)
        pygame.draw.circle(surf, (255,215,0), (cx+4,cy-13), 3)
        pygame.draw.circle(surf, BLACK, (cx-4,cy-13), 1)
        pygame.draw.circle(surf, BLACK, (cx+4,cy-13), 1)
        pygame.draw.line(surf, MONST_G, (cx-11,cy-3), (cx-17,cy+5+leg), 3)
        pygame.draw.line(surf, MONST_G, (cx+11,cy-3), (cx+17,cy+5-leg), 3)
        for dx in (-2,0,2):
            pygame.draw.line(surf, (255,75,75),
                (cx-17+dx,cy+5+leg),(cx-19+dx,cy+10+leg), 2)
        pygame.draw.line(surf, MONST_C, (cx-4,cy+13),(cx-5,cy+23+leg), 3)
        pygame.draw.line(surf, MONST_C, (cx+4,cy+13),(cx+5,cy+23-leg), 3)

    @staticmethod
    def _dead(surf, S):
        cx, cy = S//2, S//2
        pygame.draw.ellipse(surf, DEAD_C, (cx-15,cy-4,30,11))
        pygame.draw.circle(surf, DEAD_C, (cx+15,cy+1), 7)
        pygame.draw.line(surf, BLACK, (cx+11,cy-3),(cx+18,cy+4), 2)
        pygame.draw.line(surf, BLACK, (cx+18,cy-3),(cx+11,cy+4), 2)
        pygame.draw.circle(surf, (150,18,18), (cx-2,cy+8), 5)
        pygame.draw.circle(surf, (130,12,12), (cx-9,cy+7), 3)

# ══════════════════════════════════════════════════════════════
#  ЧАСТИЦЫ
# ══════════════════════════════════════════════════════════════

class Particle:
    __slots__ = ("x","y","vx","vy","color","life","max_life","r")
    def __init__(self, x, y, vx, vy, color, life):
        self.x, self.y = float(x), float(y)
        self.vx, self.vy = vx, vy
        self.color = color
        self.life = self.max_life = life
        self.r = random.randint(2, 5)
    def update(self, dt):
        self.x += self.vx * dt * 60
        self.y += self.vy * dt * 60
        self.vx *= 0.92; self.vy *= 0.92
        self.life -= dt
    def draw(self, surf, cx, cy, sw, sh):
        sx, sy = int(self.x-cx), int(self.y-cy)
        if not (-8 < sx < sw+8 and -8 < sy < sh+8):
            return
        a = self.life / self.max_life
        col = tuple(int(c*a) for c in self.color)
        pygame.draw.circle(surf, col, (sx,sy), max(1, int(self.r*a)))

class Particles:
    def __init__(self):
        self.pool: list[Particle] = []
    def emit_death(self, x, y):
        for _ in range(22):
            a = random.uniform(0, math.tau)
            s = random.uniform(0.8, 3.5)
            self.pool.append(Particle(x,y,math.cos(a)*s,math.sin(a)*s,
                                      (210,25,25), random.uniform(0.5,1.3)))
    def emit_pickup(self, x, y):
        for _ in range(12):
            a = random.uniform(0, math.tau)
            self.pool.append(Particle(x,y,math.cos(a)*2,math.sin(a)*2,
                                      (255,215,0), random.uniform(0.4,0.9)))
    def update(self, dt):
        self.pool = [p for p in self.pool if p.life > 0]
        for p in self.pool:
            p.update(dt)
    def draw(self, surf, cx, cy, sw, sh):
        for p in self.pool:
            p.draw(surf, cx, cy, sw, sh)

# ══════════════════════════════════════════════════════════════
#  КАМЕРА
# ══════════════════════════════════════════════════════════════

class Camera:
    def __init__(self, map_w, map_h):
        self.x, self.y = 0.0, 0.0
        self.map_w = map_w
        self.map_h = map_h
    def update(self, wx, wy, sw, sh, dt):
        tx = clamp(wx - sw/2, 0, max(0, self.map_w-sw))
        ty = clamp(wy - sh/2, 0, max(0, self.map_h-sh))
        t  = 1.0 - math.exp(-CAM_LERP * dt)
        self.x = lerp(self.x, tx, t)
        self.y = lerp(self.y, ty, t)
    def to_screen(self, wx, wy):
        return int(wx - self.x), int(wy - self.y)

# ══════════════════════════════════════════════════════════════
#  UI ВИДЖЕТЫ
# ══════════════════════════════════════════════════════════════

class Button:
    def __init__(self, x, y, w, h, text, color=(55,18,18), font=None):
        self.rect   = pygame.Rect(x, y, w, h)
        self.text   = text
        self.color  = color
        self.hcolor = tuple(min(255, c+45) for c in color)
        self.font   = font
        self._hover = False
    def handle(self, event) -> bool:
        if event.type == pygame.MOUSEMOTION:
            self._hover = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            return self.rect.collidepoint(event.pos)
        return False
    def draw(self, surf):
        col = self.hcolor if self._hover else self.color
        pygame.draw.rect(surf, col,            self.rect, border_radius=8)
        pygame.draw.rect(surf, (115,45,45),    self.rect, 2, border_radius=8)
        if self.font:
            t = self.font.render(self.text, True, WHITE)
            surf.blit(t, t.get_rect(center=self.rect.center))

class InputField:
    def __init__(self, x, y, w, h, default="", label=""):
        self.rect   = pygame.Rect(x, y, w, h)
        self.text   = default
        self.label  = label
        self.active = False
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
            surf.blit(f_label.render(self.label, True, GRAY),
                      (self.rect.x, self.rect.y-22))
        bc = (90,42,42) if self.active else (44,20,20)
        pygame.draw.rect(surf, bc,          self.rect, border_radius=6)
        pygame.draw.rect(surf, (140,58,58), self.rect, 2, border_radius=6)
        cur = "|" if (self.active and self._blink) else ""
        t = f_text.render(self.text + cur, True, WHITE)
        surf.blit(t, (self.rect.x+10, self.rect.centery - t.get_height()//2))

# ══════════════════════════════════════════════════════════════
#  БАЗОВЫЙ ЭКРАН
# ══════════════════════════════════════════════════════════════

class BaseScreen:
    def __init__(self, app):
        self.app = app
    def on_enter(self): pass
    def handle_event(self, event): pass
    def update(self, dt): pass
    def draw(self, surf): pass
    def _bg(self, surf):
        surf.fill(BG)
        sw, sh = surf.get_size()
        for x in range(0, sw, 64):
            pygame.draw.line(surf, (16,16,24), (x,0), (x,sh))
        for y in range(0, sh, 64):
            pygame.draw.line(surf, (16,16,24), (0,y), (sw,y))

# ══════════════════════════════════════════════════════════════
#  ГЛАВНОЕ МЕНЮ
# ══════════════════════════════════════════════════════════════

class MenuScreen(BaseScreen):
    def __init__(self, app):
        super().__init__(app)
        fn = pygame.font.SysFont
        self.f_title = fn("monospace", 50, bold=True)
        self.f_sub   = fn("monospace", 15)
        self.f_btn   = fn("monospace", 22, bold=True)
        self.f_hint  = fn("monospace", 13)
        self.f_lbl   = fn("monospace", 16)
        self.f_inp   = fn("monospace", 20)
        self._anim   = 0.0
        self._frame  = 0
        self._ftimer = 0.0
        self._lw     = 0
        self.ip_field : InputField | None = None
        self.btn_mp   : Button | None = None
        self.btn_ai   : Button | None = None
        self.btn_quit : Button | None = None

    def _layout(self, sw, sh):
        if self._lw == sw:
            return
        self._lw = sw
        BW, BH = 340, 52
        bx = sw//2 - BW//2
        self.ip_field = InputField(bx, 285, BW, 44, DEFAULT_HOST, "IP сервера:")
        self.btn_mp   = Button(bx, 365, BW, BH, "🎮 Мультиплеер", (52,16,16), self.f_btn)
        self.btn_ai   = Button(bx, 430, BW, BH, "🤖 Против AI",   (16,16,55), self.f_btn)
        self.btn_quit = Button(bx, 516, BW, BH, "✕ Выход",        (28,10,10), self.f_btn)

    def on_enter(self):
        self._anim = 0.0

    def handle_event(self, event):
        sw, sh = self.app.screen.get_size()
        self._layout(sw, sh)
        self.ip_field.handle(event)
        if self.btn_mp.handle(event):
            self.app.connect_and_play(self.ip_field.text.strip() or DEFAULT_HOST)
        if self.btn_ai.handle(event):
            self.app.connect_and_play(self.ip_field.text.strip() or DEFAULT_HOST)
        if self.btn_quit.handle(event):
            self.app.running = False
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.app.running = False

    def update(self, dt):
        self._anim  += dt
        self._ftimer += dt
        if self.ip_field:
            self.ip_field.update(dt)
        if self._ftimer > 0.18:
            self._ftimer = 0
            self._frame  = (self._frame + 1) % 4

    def draw(self, surf):
        sw, sh = surf.get_size()
        self._layout(sw, sh)
        self._bg(surf)
        p = int(160 + 95 * math.sin(self._anim * 2.4))
        t = self.f_title.render("☠ HORROR LAN", True, (p, 22, 22))
        surf.blit(t, t.get_rect(centerx=sw//2, y=65))
        sub = self.f_sub.render(
            "Найди ключ · Открой дверь · Сбеги от монстра", True, GRAY)
        surf.blit(sub, sub.get_rect(centerx=sw//2, y=132))
        f = self._frame
        for i, (role, is_me, lbl, col) in enumerate([
            ("monster",  False, "Монстр",    RED),
            ("survivor", False, "Выживший",  GREEN),
            ("survivor", True,  "Вы",        CYAN),
        ]):
            spr = Sprites.get(role, is_me=is_me, frame=f)
            ox  = sw//2 - 75 + i*65
            surf.blit(spr, (ox, 162))
            ls  = self.f_hint.render(lbl, True, col)
            surf.blit(ls, (ox + 24 - ls.get_width()//2, 215))
        self.ip_field.draw(surf, self.f_lbl, self.f_inp)
        self.btn_mp.draw(surf)
        self.btn_ai.draw(surf)
        self.btn_quit.draw(surf)
        hints = [
            "WASD — движение | SHIFT — бег | CTRL — тихо",
            "P / ESC — пауза | F11 — полный экран",
            "Цель: подобрать ключ 🔑, добраться до двери 🚪",
        ]
        for i, h in enumerate(hints):
            hs = self.f_hint.render(h, True, (60,60,80))
            surf.blit(hs, hs.get_rect(centerx=sw//2, y=sh-55+i*16))

# ══════════════════════════════════════════════════════════════
#  ПАУЗА
# ══════════════════════════════════════════════════════════════

class PauseScreen(BaseScreen):
    def __init__(self, app):
        super().__init__(app)
        fn = pygame.font.SysFont
        self.f_t = fn("monospace", 40, bold=True)
        self.f_b = fn("monospace", 22, bold=True)
        self.f_h = fn("monospace", 14)
        self.btn_resume : Button | None = None
        self.btn_menu   : Button | None = None

    def _layout(self, sw, sh):
        BW, BH = 280, 52
        bx = sw//2 - BW//2
        self.btn_resume = Button(bx, sh//2,    BW, BH, "▶ Продолжить",  (16,50,16), self.f_b)
        self.btn_menu   = Button(bx, sh//2+68, BW, BH, "🏠 Главное меню",(50,16,16), self.f_b)

    def handle_event(self, event):
        sw, sh = self.app.screen.get_size()
        self._layout(sw, sh)
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_p):
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
        ov.fill((0,0,0,178))
        surf.blit(ov, (0,0))
        t = self.f_t.render("⏸ ПАУЗА", True, YELLOW)
        surf.blit(t, t.get_rect(centerx=sw//2, y=sh//2-95))
        self.btn_resume.draw(surf)
        self.btn_menu.draw(surf)
        h = self.f_h.render("[P / ESC] — продолжить", True, GRAY)
        surf.blit(h, h.get_rect(centerx=sw//2, y=sh//2+132))

# ══════════════════════════════════════════════════════════════
#  ЭКРАН СМЕРТИ
# ══════════════════════════════════════════════════════════════

class DeathScreen(BaseScreen):
    DELAY = 4.0

    def __init__(self, app):
        super().__init__(app)
        fn = pygame.font.SysFont
        self.f_big  = fn("monospace", 46, bold=True)
        self.f_med  = fn("monospace", 20)
        self.f_hint = fn("monospace", 15)
        self._timer = 0.0

    def on_enter(self):
        self._timer = 0.0

    def handle_event(self, event):
        if event.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
            self._exit()

    def update(self, dt):
        self._timer += dt
        if self._timer >= self.DELAY:
            self._exit()

    def _exit(self):
        self.app.disconnect()
        self.app.set_screen("menu")

    def draw(self, surf):
        sw, sh = surf.get_size()
        ov = pygame.Surface((sw, sh), pygame.SRCALPHA)
        ov.fill((0,0,0,215))
        surf.blit(ov, (0,0))
        a    = min(1.0, self._timer / 0.5)
        size = int(72 * a)
        if size > 0:
            spr = Sprites.get("survivor", alive=False)
            s   = pygame.transform.scale(spr, (size, size))
            surf.blit(s, s.get_rect(centerx=sw//2, centery=sh//2-110))
        t1 = self.f_big.render("ВЫ МЕРТВЫ", True, RED)
        t2 = self.f_med.render("Тьма поглотила вас...", True, GRAY)
        t3 = self.f_hint.render(
            f"Меню через {max(0.0, self.DELAY-self._timer):.1f}с [любая клавиша]",
            True, (65,65,82))
        surf.blit(t1, t1.get_rect(centerx=sw//2, y=sh//2-55))
        surf.blit(t2, t2.get_rect(centerx=sw//2, y=sh//2+10))
        surf.blit(t3, t3.get_rect(centerx=sw//2, y=sh//2+60))

# ══════════════════════════════════════════════════════════════
#  ЭКРАН КОНЦА ИГРЫ
# ══════════════════════════════════════════════════════════════

class EndScreen(BaseScreen):
    def __init__(self, app):
        super().__init__(app)
        fn = pygame.font.SysFont
        self.f_t    = fn("monospace", 46, bold=True)
        self.f_sub  = fn("monospace", 22)
        self.f_hint = fn("monospace", 15)
        self.winner       = None
        self.i_am_monster = False
        self._anim = 0.0

    def on_enter(self):
        self._anim = 0.0

    def handle_event(self, event):
        if event.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
            self.app.disconnect()
            self.app.set_screen("menu")

    def update(self, dt):
        self._anim += dt

    def draw(self, surf):
        ov = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
        ov.fill((0,0,0,215))
        surf.blit(ov, (0,0))
        sw, sh = surf.get_size()
        won = (self.winner == "survivors" and not self.i_am_monster) or \
              (self.winner == "monster"   and self.i_am_monster)
        p     = int(180 + 75 * math.sin(self._anim * 3))
        color = (p, p, 25) if won else (p, 25, 25)
        title = "ПОБЕДА!" if won else "ПОРАЖЕНИЕ"
        sub   = "Вы пережили эту ночь." if won else "Тьма победила..."
        t1 = self.f_t.render(title, True, color)
        t2 = self.f_sub.render(sub,  True, GRAY)
        t3 = self.f_hint.render("Нажмите любую клавишу — вернуться в меню",
                                True, (60,60,78))
        surf.blit(t1, t1.get_rect(centerx=sw//2, y=sh//2-80))
        surf.blit(t2, t2.get_rect(centerx=sw//2, y=sh//2-12))
        surf.blit(t3, t3.get_rect(centerx=sw//2, y=sh//2+55))

# ══════════════════════════════════════════════════════════════
#  ИГРОВОЙ ЭКРАН
# ══════════════════════════════════════════════════════════════

class GameScreen(BaseScreen):
    def __init__(self, app):
        super().__init__(app)
        self.net      : NetworkClient | None = None
        self.map_rend : MapRenderer   | None = None
        self.minimap  : MiniMap       | None = None
        self.camera   = Camera(1600, 1200)
        self.flash    = Flashlight()
        self.ptcls    = Particles()
        fn = pygame.font.SysFont
        self.f_big  = fn("monospace", 34, bold=True)
        self.f_med  = fn("monospace", 20, bold=True)
        self.f_sm   = fn("monospace", 15)
        self.f_tiny = fn("monospace", 12)
        self._frame       = 0
        self._ftimer      = 0.0
        self._prev_state  : dict | None = None
        self._death_fired = False
        self._end_fired   = False
        self._map_built   = False

    def setup(self, net: NetworkClient):
        self.net          = net
        self.map_rend     = MapRenderer(net.map_w, net.map_h)
        self.minimap      = MiniMap(net.map_w, net.map_h)
        self.camera       = Camera(net.map_w, net.map_h)
        self.ptcls        = Particles()
        self._prev_state  = None
        self._map_built   = False
        self._death_fired = False
        self._end_fired   = False
        self._frame       = 0

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_p):
                self.app.set_screen("pause")
            elif event.key == pygame.K_RETURN and self.net:
                self.net.send_start()

    def _read_keys(self):
        k  = pygame.key.get_pressed()
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
        state = self.net.get_state()
        if state and not self._map_built and state.get("walls"):
            self.map_rend.build(state["walls"])
            self.minimap.build_base(self.map_rend.walls)
            self._map_built = True

        me = self._get_me(state)
        mx, my, sprint, silent = self._read_keys()

        if me and me.get("alive", True):
            self.net.send_input(mx, my, sprint, silent)
        else:
            self.net.send_input(0, 0, False, False)

        self._ftimer += dt
        if self._ftimer >= 0.15 and (mx or my):
            self._ftimer = 0
            self._frame  = (self._frame + 1) % 4

        if me:
            sw, sh = self.app.screen.get_size()
            self.camera.update(me["x"], me["y"], sw, sh, dt)

        self.ptcls.update(dt)
        if state:
            self._check_particles(state)
        self._check_events(state, me)
        self._prev_state = state

    def _get_me(self, state) -> dict | None:
        if not state or not self.net:
            return None
        return state.get("players", {}).get(self.net.pid)

    def _check_particles(self, state):
        prev_players = (self._prev_state or {}).get("players", {})
        for pid, p in state.get("players", {}).items():
            prev     = prev_players.get(pid, {})
            was_alive = prev.get("alive", True)
            is_alive  = p.get("alive", True)
            if was_alive and not is_alive:
                self.ptcls.emit_death(p["x"], p["y"])

        prev_key = (self._prev_state or {}).get("key")
        cur_key  = state.get("key")
        if (prev_key is not None and cur_key is not None and
                prev_key.get("on_map", False) and not cur_key.get("on_map", True)):
            self.ptcls.emit_pickup(prev_key["x"], prev_key["y"])

    def _check_events(self, state, me):
        if not state or not me:
            return
        if not me.get("alive", True) and not self._death_fired:
            self._death_fired    = True
            self.app.death_pending = True
            self.app.death_timer   = 0.0
        if state.get("game_over") and not self._end_fired:
            self._end_fired = True
            end : EndScreen = self.app.screens["end"]
            end.winner       = state.get("winner")
            end.i_am_monster = me.get("is_monster", False)
            self.app.end_pending = True
            self.app.end_timer   = 0.0

    def draw(self, surf):
        state = self.net.get_state() if self.net else None
        me    = self._get_me(state)
        sw, sh = surf.get_size()

        surf.fill(BG)
        if self.map_rend and self.map_rend.surface:
            src = pygame.Rect(int(self.camera.x), int(self.camera.y), sw, sh)
            surf.blit(self.map_rend.surface, (0,0), src)

        if state:
            self._draw_items(surf, state)
            if me and me.get("is_monster"):
                self._draw_noise(surf, state)
            self._draw_characters(surf, state, me)

        self.ptcls.draw(surf, self.camera.x, self.camera.y, sw, sh)

        if me:
            sx, sy = self.camera.to_screen(me["x"], me["y"])
            radius = FLASHLIGHT_MONSTER if me.get("is_monster") else FLASHLIGHT_SURVIVOR
            self.flash.draw(surf, sx, sy, radius, is_dead=not me.get("alive", True))

        self._draw_hud(surf, state, me, sw, sh)
        if state and self.minimap:
            self.minimap.draw(surf, state, self.net.pid if self.net else None, sw)

    def _draw_items(self, surf, state):
        cam = self.camera
        key = state.get("key")
        if key and key.get("on_map"):
            sx, sy = cam.to_screen(key["x"], key["y"])
            t      = time.time()
            bob    = int(5 * math.sin(t * 2.5))
            glow   = pygame.Surface((48,48), pygame.SRCALPHA)
            pygame.draw.circle(glow, (*KEY_C,60), (24,24),
                               int(18 + 4*math.sin(t*3)))
            surf.blit(glow, (sx-24, sy-24+bob))
            pygame.draw.circle(surf, KEY_C, (sx, sy+bob), 10)
            pygame.draw.circle(surf, (200,160,0), (sx, sy+bob), 10, 2)
            pygame.draw.rect(surf, KEY_C, (sx+4, sy+bob-3, 12, 6))
            pygame.draw.rect(surf, KEY_C, (sx+12,sy+bob-3,  3, 9))
            pygame.draw.rect(surf, KEY_C, (sx+8, sy+bob-3,  3, 6))
            f   = pygame.font.SysFont("monospace", 11)
            lbl = f.render("КЛЮЧ", True, KEY_C)
            surf.blit(lbl, (sx - lbl.get_width()//2, sy+bob-26))

        door = state.get("door")
        if door:
            sx, sy  = cam.to_screen(door["x"], door["y"])
            is_open = door.get("open", False)
            color   = DOOR_OC if is_open else DOOR_C
            pygame.draw.rect(surf, color, (sx-16, sy-24, 32, 48), 0, 4)
            pygame.draw.rect(surf, WHITE, (sx-16, sy-24, 32, 48), 2, 4)
            pygame.draw.circle(surf, (200,200,200), (sx+8, sy), 4)
            if is_open:
                pygame.draw.line(surf, GREEN, (sx-8,sy),(sx+8,sy), 3)
                pygame.draw.line(surf, GREEN, (sx+4,sy-4),(sx+8,sy), 2)
                pygame.draw.line(surf, GREEN, (sx+4,sy+4),(sx+8,sy), 2)
            f   = pygame.font.SysFont("monospace", 11)
            lbl = f.render("ОТКРЫТА" if is_open else "ЗАКРЫТА", True, color)
            surf.blit(lbl, (sx - lbl.get_width()//2, sy-40))

    def _draw_noise(self, surf, state):
        for ev in state.get("noise_events", []):
            r  = int(ev["radius"])
            sx = int(ev["x"] - self.camera.x)
            sy = int(ev["y"] - self.camera.y)
            ttl = ev.get("ttl", 0)
            a   = clamp(int(200 * ttl / 1.8), 0, 200)
            ring = pygame.Surface((r*2+4, r*2+4), pygame.SRCALPHA)
            pygame.draw.circle(ring, (*NOISE_C, a), (r+2,r+2), r, 2)
            surf.blit(ring, (sx-r-2, sy-r-2))
            pygame.draw.circle(surf, NOISE_C, (sx,sy), 4)

    def _draw_characters(self, surf, state, me):
        frame  = self._frame
        cam    = self.camera
        my_pid = self.net.pid if self.net else None

        ai = state.get("ai_monster")
        if ai:
            sx, sy = cam.to_screen(ai["x"], ai["y"])
            surf.blit(Sprites.get("monster", frame=frame), (sx-24, sy-24))
            self._glow(surf, sx, sy)
            self._label(surf, sx, sy, "МОНСТР", RED)

        for pid, p in state.get("players", {}).items():
            sx, sy = cam.to_screen(p["x"], p["y"])
            is_me  = (pid == my_pid)
            alive  = p["alive"]
            role   = "monster" if p["is_monster"] else "survivor"
            surf.blit(Sprites.get(role, is_me=is_me, alive=alive, frame=frame),
                      (sx-24, sy-24))
            if p["is_monster"] and alive:
                self._glow(surf, sx, sy)
            if p.get("has_key") and alive:
                f = pygame.font.SysFont("monospace", 14)
                k = f.render("🔑", True, KEY_C)
                surf.blit(k, (sx - k.get_width()//2, sy-45))
            if p["is_monster"]:
                self._label(surf, sx, sy, "МОНСТР", RED)
            elif is_me:
                self._label(surf, sx, sy, "ВЫ", CYAN)
            elif alive:
                self._label(surf, sx, sy, pid, SURV_C)

    def _glow(self, surf, sx, sy):
        r    = int(28 + 10 * math.sin(time.time() * 4))
        glow = pygame.Surface((r*2, r*2), pygame.SRCALPHA)
        pygame.draw.circle(glow, (210,0,0,58), (r,r), r)
        surf.blit(glow, (sx-r, sy-r))

    def _label(self, surf, sx, sy, text, col):
        t = self.f_tiny.render(text, True, col)
        surf.blit(t, (sx - t.get_width()//2, sy-42))

    def _draw_hud(self, surf, state, me, sw, sh):
        if not state:
            return
        panel = pygame.Surface((sw, 50), pygame.SRCALPHA)
        panel.fill((8,8,14,218))
        surf.blit(panel, (0,0))

        tl = state.get("time_left", 0)
        tc = GREEN if tl > 60 else (YELLOW if tl > 20 else RED)
        mm, ss = divmod(int(tl), 60)
        timer_t = self.f_big.render(f"⏱ {mm:02d}:{ss:02d}", True, tc)
        surf.blit(timer_t, timer_t.get_rect(centerx=sw//2, y=6))

        if me:
            if me["is_monster"]:          status, sc = "👹 МОНСТР", RED
            elif me.get("escaped"):        status, sc = "✈ СПАСЁН",  CYAN
            elif me["alive"]:              status, sc = "✔ ЖИВОЙ",   GREEN
            else:                          status, sc = "✖ МЁРТВЫЙ", DEAD_C
            surf.blit(self.f_med.render(status, True, sc), (14, 13))
            if me.get("has_key"):
                surf.blit(self.f_sm.render("🔑 Ключ есть!", True, KEY_C), (14, 35))

        alive_n   = sum(1 for p in state["players"].values()
                        if not p["is_monster"] and p["alive"] and not p.get("escaped"))
        escaped_n = sum(1 for p in state["players"].values() if p.get("escaped"))
        total_n   = sum(1 for p in state["players"].values() if not p["is_monster"])
        info = f"Живых: {alive_n}/{total_n} Сбежало: {escaped_n}"
        surf.blit(self.f_sm.render(info, True, HUD_TEXT),
                  (sw - self.f_sm.size(info)[0] - 14, 16))

        if state.get("started") and me and me.get("alive") and not me.get("is_monster"):
            h = self.f_tiny.render(
                "SHIFT — бег | CTRL — тихо | P — пауза | Найди 🔑 → 🚪",
                True, (55,55,75))
            surf.blit(h, (8, sh-18))

        if state.get("ai_mode"):
            a = self.f_tiny.render("⚡ AI MODE", True, (168,50,50))
            surf.blit(a, (sw - a.get_width() - 8, sh-18))

        if not state.get("started"):
            self._draw_waiting(surf, state, sw, sh)

    def _draw_waiting(self, surf, state, sw, sh):
        ov = pygame.Surface((sw, sh), pygame.SRCALPHA)
        ov.fill((0,0,0,138))
        surf.blit(ov, (0,0))
        wt   = self.f_big.render("Ожидание игроков...",   True, HUD_TEXT)
        st   = self.f_med.render("[ENTER] — начать игру", True, YELLOW)
        goal = self.f_sm.render("Цель: подобрать 🔑 и сбежать через 🚪", True, GRAY)
        surf.blit(wt,   wt.get_rect(centerx=sw//2, y=sh//2-55))
        surf.blit(st,   st.get_rect(centerx=sw//2, y=sh//2-5))
        surf.blit(goal, goal.get_rect(centerx=sw//2, y=sh//2+32))
        for i, (pid, p) in enumerate(state.get("players", {}).items()):
            col  = RED if p["is_monster"] else SURV_C
            role = "МОНСТР" if p["is_monster"] else "выживший"
            ls   = self.f_sm.render(f" {pid} — {role}", True, col)
            surf.blit(ls, ls.get_rect(centerx=sw//2, y=sh//2+65+i*24))

# ══════════════════════════════════════════════════════════════
#  ПРИЛОЖЕНИЕ
# ══════════════════════════════════════════════════════════════

class App:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("HORROR LAN")
        self.screen     = pygame.display.set_mode((WIN_W, WIN_H), pygame.RESIZABLE)
        self.clock      = pygame.time.Clock()
        self.running    = True
        self.fullscreen = False
        self.snd        = SoundManager()   # заглушка — без звука
        self.net : NetworkClient | None = None

        self.death_pending = False
        self.death_timer   = 0.0
        self.end_pending   = False
        self.end_timer     = 0.0

        self.screens: dict[str, BaseScreen] = {
            "menu"  : MenuScreen(self),
            "game"  : GameScreen(self),
            "pause" : PauseScreen(self),
            "death" : DeathScreen(self),
            "end"   : EndScreen(self),
        }
        self._name   = "menu"
        self.current = self.screens["menu"]
        self.current.on_enter()

    def set_screen(self, name: str):
        self._name   = name
        self.current = self.screens[name]
        self.current.on_enter()

    def connect_and_play(self, host: str):
        self.disconnect()
        net = NetworkClient(host)
        if not net.connect():
            print(f"[APP] Не удалось подключиться к {host}:{PORT}")
            return
        self.net = net
        deadline = time.time() + 7.0
        while not net.pid and time.time() < deadline:
            time.sleep(0.05)
        if not net.pid:
            print("[APP] Сервер не ответил.")
            net.disconnect()
            return
        game : GameScreen = self.screens["game"]
        game.setup(net)
        self.set_screen("game")

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
            dt = self.clock.tick(FPS) / 1000.0

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_F11:
                    self.toggle_fullscreen()
                elif event.type == pygame.VIDEORESIZE and not self.fullscreen:
                    self.screen = pygame.display.set_mode(event.size, pygame.RESIZABLE)
                self.current.handle_event(event)

            self.current.update(dt)

            if self.death_pending and self._name == "game":
                self.death_timer += dt
                if self.death_timer >= 1.8:
                    self.death_pending = False
                    self.set_screen("death")

            if self.end_pending and self._name == "game":
                self.end_timer += dt
                if self.end_timer >= 2.5:
                    self.end_pending = False
                    self.set_screen("end")

            if self._name == "pause":
                self.screens["game"].draw(self.screen)
            self.current.draw(self.screen)
            pygame.display.flip()

        self.disconnect()
        pygame.quit()

# ══════════════════════════════════════════════════════════════
#  ТОЧКА ВХОДА
# ══════════════════════════════════════════════════════════════

def main():
    app = App()
    app.run()

if __name__ == "__main__":
    main()

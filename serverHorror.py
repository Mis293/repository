"""
╔══════════════════════════════════════════════════════════════════════════╗
║  HORROR LAN — SERVER  v4.0  ULTRA EDITION  (FIXED)                      ║
║                                                                          ║
║  Запуск: python server.py                                                ║
║  Порт: 5555  |  Игроков: до 8                                            ║
╚══════════════════════════════════════════════════════════════════════════╝
"""

import socket
import threading
import json
import time
import random
import math
import sys
import os

# ══════════════════════════════════════════════════════════════
#  КОНФИГУРАЦИЯ
# ══════════════════════════════════════════════════════════════

HOST        = "0.0.0.0"
PORT        = 5555
MAX_PLAYERS = 8
TICK_RATE   = 30
BROADCAST_RATE = 20

MAP_W = 2400
MAP_H = 1800

GAME_DURATION    = 360
MONSTER_SPEED    = 2.9
SURVIVOR_SPEED   = 2.1
SPRINT_MULT      = 1.7
SILENT_MULT      = 0.55
KILL_RADIUS      = 30
KEY_PICKUP_RADIUS= 40
DOOR_USE_RADIUS  = 45
TRAP_RADIUS      = 35
TRAP_SLOW_FACTOR = 0.4
TRAP_SLOW_TIME   = 3.0

AI_SIGHT_RADIUS       = 320
AI_SIGHT_RADIUS_ALERT = 500
AI_PATROL_SPEED       = 1.5
AI_ALERT_SPEED        = 3.5
AI_HEARING_RADIUS     = 280

NOISE_WALK   = 200
NOISE_RUN    = 360
NOISE_SILENT = 50
NOISE_TTL    = 2.0

NUM_KEYS  = 2
NUM_DOORS = 1
NUM_TRAPS = 6


# ══════════════════════════════════════════════════════════════
#  СТЕНЫ
# ══════════════════════════════════════════════════════════════

def build_walls():
    walls = []
    T = 24

    walls += [
        _R(0,       0,       MAP_W, T),
        _R(0,       MAP_H-T, MAP_W, T),
        _R(0,       0,       T,     MAP_H),
        _R(MAP_W-T, 0,       T,     MAP_H),
    ]

    walls += [
        _R(120,  80,   80,  280),
        _R(280,  80,   80,  120),
        _R(280,  280,  80,  120),
        _R(120,  440,  240, 60),
        _R(500,  80,   60,  200),
        _R(500,  360,  60,  160),
        _R(440,  600,  180, 60),
    ]

    walls += [
        _R(680,  80,   60,  340),
        _R(820,  80,   200, 60),
        _R(820,  200,  60,  180),
        _R(960,  200,  60,  200),
        _R(820,  460,  200, 60),
        _R(680,  520,  60,  200),
        _R(680,  800,  60,  160),
        _R(820,  600,  200, 60),
        _R(960,  540,  60,  200),
        _R(820,  820,  200, 60),
    ]

    walls += [
        _R(1100, 200,  400, 60),
        _R(1100, 200,  60,  380),
        _R(1440, 200,  60,  380),
        _R(1100, 520,  140, 60),
        _R(1360, 520,  140, 60),
        _R(1180, 320,  80,  80),
        _R(1360, 320,  80,  80),
        _R(1270, 260,  60,  60),
        _R(1270, 440,  60,  60),
    ]

    walls += [
        _R(1600, 80,   60,  240),
        _R(1740, 80,   60,  180),
        _R(1600, 240,  200, 60),
        _R(1880, 80,   340, 60),
        _R(2100, 80,   60,  300),
        _R(1880, 300,  280, 60),
        _R(2100, 400,  60,  200),
        _R(1880, 540,  60,  180),
        _R(1600, 380,  180, 60),
        _R(2220, 80,   140, 60),
        _R(2220, 80,   60,  300),
        _R(2160, 280,  120, 60),
    ]

    walls += [
        _R(80,   880,  160, 60),
        _R(80,   1020, 160, 60),
        _R(80,   1160, 160, 60),
        _R(80,   1300, 160, 60),
        _R(320,  900,  60,  280),
        _R(320,  1280, 60,  200),
        _R(460,  880,  60,  160),
        _R(460,  1140, 60,  160),
        _R(200,  1160, 120, 60),
        _R(600,  900,  180, 60),
        _R(600,  1060, 60,  180),
        _R(740,  900,  60,  340),
        _R(600,  1320, 200, 60),
        _R(600,  1460, 200, 60),
    ]

    walls += [
        _R(960,  880,  70,  70),
        _R(1100, 960,  70,  70),
        _R(1220, 880,  70,  70),
        _R(1060, 1080, 70,  70),
        _R(1180, 1080, 70,  70),
        _R(1340, 960,  70,  70),
        _R(1060, 1200, 70,  70),
        _R(1220, 1200, 70,  70),
    ]

    walls += [
        _R(1600, 620,  80,  360),
        _R(1760, 620,  80,  160),
        _R(1600, 860,  240, 60),
        _R(1920, 620,  80,  500),
        _R(2000, 620,  320, 60),
        _R(2240, 620,  80,  280),
        _R(2000, 800,  160, 60),
        _R(2080, 680,  80,  120),
        _R(2000, 960,  320, 60),
        _R(2160, 820,  80,  140),
        _R(2080, 900,  80,  60),
    ]

    walls += [
        _R(900,  1200, 60,  400),
        _R(1060, 1360, 60,  200),
        _R(900,  1500, 300, 60),
        _R(1220, 1200, 60,  400),
        _R(1380, 1200, 60,  400),
        _R(1220, 1460, 220, 60),
        _R(1540, 1200, 60,  260),
        _R(1380, 1360, 220, 60),
        _R(1540, 1520, 60,  200),
        _R(1380, 1600, 220, 60),
    ]

    walls += [
        _R(1700, 1100, 360, 60),
        _R(1700, 1100, 60,  300),
        _R(1700, 1480, 60,  200),
        _R(2000, 1100, 60,  300),
        _R(1840, 1480, 220, 60),
        _R(2000, 1400, 60,  280),
        _R(2140, 1100, 60,  200),
        _R(2140, 1380, 60,  200),
        _R(2140, 1200, 260, 60),
        _R(2140, 1480, 260, 60),
        _R(2260, 1340, 80,  140),
        _R(2300, 1260, 60,  80),
    ]

    walls += [
        _R(600,  600,  80,  100),
        _R(750,  540,  80,  80),
        _R(1480, 640,  80,  80),
        _R(1480, 800,  80,  80),
        _R(1760, 820,  80,  60),
        _R(1120, 620,  60,  160),
        _R(1340, 640,  60,  120),
        _R(400,  680,  120, 60),
        _R(400,  760,  60,  120),
        _R(820,  1080, 80,  80),
        _R(1460, 1060, 80,  80),
        _R(1460, 1160, 80,  80),
        _R(700,  1400, 80,  100),
        _R(800,  1350, 60,  60),
        _R(540,  1400, 60,  120),
    ]

    return walls


def _R(x, y, w, h):
    return {"x": x, "y": y, "w": w, "h": h, "r": (x, y, w, h)}


# ══════════════════════════════════════════════════════════════
#  ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ══════════════════════════════════════════════════════════════

def dist(ax, ay, bx, by):
    return math.hypot(ax - bx, ay - by)


def normalize(dx, dy):
    length = math.hypot(dx, dy)
    if length == 0:
        return 0.0, 0.0
    return dx / length, dy / length


def rect_collides_circle_raw(rx, ry, rw, rh, cx, cy, r):
    nearest_x = max(rx, min(cx, rx + rw))
    nearest_y = max(ry, min(cy, ry + rh))
    return math.hypot(cx - nearest_x, cy - nearest_y) < r


def rect_collides_circle(wall_dict, cx, cy, r):
    x, y, w, h = wall_dict["r"]
    return rect_collides_circle_raw(x, y, w, h, cx, cy, r)


def point_in_rect(wall_dict, px, py):
    x, y, w, h = wall_dict["r"]
    return x <= px <= x+w and y <= py <= y+h


def line_of_sight(walls, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    length = math.hypot(dx, dy)
    if length == 0:
        return True
    steps  = int(length / 14) + 1
    sx, sy = dx / steps, dy / steps
    for i in range(1, steps):
        px, py = ax + sx*i, ay + sy*i
        for w in walls:
            if point_in_rect(w, px, py):
                return False
    return True


def move_with_collision(x, y, dx, dy, radius, walls):
    nx = x + dx
    if not any(rect_collides_circle(w, nx, y, radius) for w in walls):
        x = nx
    ny = y + dy
    if not any(rect_collides_circle(w, x, ny, radius) for w in walls):
        y = ny
    x = max(radius, min(MAP_W - radius, x))
    y = max(radius, min(MAP_H - radius, y))
    return x, y


def find_free_pos(walls, radius=30, zone=None):
    for _ in range(2000):
        if zone:
            x = random.uniform(zone[0], zone[2])
            y = random.uniform(zone[1], zone[3])
        else:
            x = random.uniform(60, MAP_W - 60)
            y = random.uniform(60, MAP_H - 60)
        if not any(rect_collides_circle(w, x, y, radius) for w in walls):
            return x, y
    return MAP_W / 2, MAP_H / 2


# ══════════════════════════════════════════════════════════════
#  КЛАССЫ ИГРОВЫХ ОБЪЕКТОВ
# ══════════════════════════════════════════════════════════════

class ServerPlayer:
    RADIUS = 16

    def __init__(self, pid, x, y):
        self.pid        = pid
        self.x          = x
        self.y          = y
        self.alive      = True
        self.escaped    = False
        self.is_monster = False
        self.has_key    = False
        self.keys_held  = 0
        self.move_x     = 0.0
        self.move_y     = 0.0
        self.sprinting  = False
        self.silent     = False
        self.noise_timer= 0.0
        self.trap_slow  = 0.0
        self.score      = 0
        self.kills      = 0
        self.steps      = 0
        self.ping       = 0

    def to_dict(self):
        return {
            "pid":        self.pid,
            "x":          round(self.x, 1),
            "y":          round(self.y, 1),
            "alive":      self.alive,
            "escaped":    self.escaped,
            "is_monster": self.is_monster,
            "has_key":    self.has_key,
            "keys_held":  self.keys_held,
            "sprinting":  self.sprinting,
            "silent":     self.silent,
            "trap_slow":  round(self.trap_slow, 2),
            "score":      self.score,
            "kills":      self.kills,
        }


class ServerAIMonster:
    RADIUS = 20

    STATE_PATROL = "patrol"
    STATE_ALERT  = "alert"
    STATE_CHASE  = "chase"
    STATE_SEARCH = "search"

    def __init__(self, x, y):
        self.x      = x
        self.y      = y
        self.target = None
        self.state  = self.STATE_PATROL
        self.state_timer = 0.0
        self._patrol_x    = x
        self._patrol_y    = y
        self._patrol_timer= 0.0
        self._noise_x = x
        self._noise_y = y
        self.anim_frame = 0
        self.anim_timer = 0.0
        self.current_speed = AI_PATROL_SPEED
        self.roar_event = False

    def update(self, players, walls, dt, noise_events):
        self.anim_timer += dt
        if self.anim_timer > 0.15:
            self.anim_timer = 0
            self.anim_frame = (self.anim_frame + 1) % 4

        self.state_timer -= dt
        self._update_state(players, walls, dt, noise_events)
        self._move(walls, dt)

    def _update_state(self, players, walls, dt, noise_events):
        visible_target = self._find_visible_target(players, walls)

        if visible_target:
            if self.state != self.STATE_CHASE:
                self.roar_event = True
                self.state_timer = 0.3
            self.state  = self.STATE_CHASE
            self.target = visible_target
            self.current_speed = AI_ALERT_SPEED
            return

        if noise_events and self.state in (self.STATE_PATROL, self.STATE_ALERT):
            loudest = None
            for ev in noise_events:
                d = dist(self.x, self.y, ev["x"], ev["y"])
                if d < AI_HEARING_RADIUS:
                    if loudest is None or ev["radius"] > loudest["radius"]:
                        loudest = ev
            if loudest:
                self._noise_x  = loudest["x"]
                self._noise_y  = loudest["y"]
                self.state     = self.STATE_ALERT
                self.state_timer = 4.0
                self.current_speed = AI_PATROL_SPEED * 1.8

        if self.state == self.STATE_CHASE:
            if self.target:
                self._noise_x = self.target.x
                self._noise_y = self.target.y
            self.state = self.STATE_SEARCH
            self.state_timer = 5.0
            self.target = None
            self.current_speed = AI_PATROL_SPEED * 1.6

        if self.state == self.STATE_SEARCH and self.state_timer <= 0:
            self.state = self.STATE_PATROL
            self.current_speed = AI_PATROL_SPEED

        if self.state == self.STATE_ALERT and self.state_timer <= 0:
            self.state = self.STATE_PATROL
            self.current_speed = AI_PATROL_SPEED

    def _find_visible_target(self, players, walls):
        best = None
        best_dist = float("inf")
        radius = AI_SIGHT_RADIUS_ALERT if self.state == self.STATE_CHASE \
                 else AI_SIGHT_RADIUS
        for p in players.values():
            if not p.alive or p.is_monster or p.escaped:
                continue
            bonus = 80 if p.sprinting else (30 if not p.silent else 0)
            d = dist(self.x, self.y, p.x, p.y)
            if d > radius + bonus:
                continue
            if not line_of_sight(walls, self.x, self.y, p.x, p.y):
                continue
            if d < best_dist:
                best_dist = d
                best = p
        return best

    def _move(self, walls, dt):
        if self.state == self.STATE_CHASE and self.target:
            dx, dy = normalize(self.target.x - self.x, self.target.y - self.y)
            speed  = self.current_speed
        elif self.state in (self.STATE_SEARCH, self.STATE_ALERT):
            dx, dy = normalize(self._noise_x - self.x, self._noise_y - self.y)
            if math.hypot(self._noise_x - self.x, self._noise_y - self.y) < 30:
                self.state = self.STATE_PATROL
                self.current_speed = AI_PATROL_SPEED
                dx, dy = 0, 0
            speed = self.current_speed
        else:
            self._patrol_timer -= dt
            tdx = self._patrol_x - self.x
            tdy = self._patrol_y - self.y
            if math.hypot(tdx, tdy) < 25 or self._patrol_timer <= 0:
                self._patrol_x, self._patrol_y = find_free_pos(walls, self.RADIUS)
                self._patrol_timer = random.uniform(4, 10)
            dx, dy = normalize(tdx, tdy)
            speed  = AI_PATROL_SPEED

        step = speed * dt * TICK_RATE
        self.x, self.y = move_with_collision(
            self.x, self.y, dx*step, dy*step, self.RADIUS, walls)

    def to_dict(self):
        d = {
            "pid":        "AI",
            "x":          round(self.x, 1),
            "y":          round(self.y, 1),
            "alive":      True,
            "escaped":    False,
            "is_monster": True,
            "has_key":    False,
            "keys_held":  0,
            "sprinting":  self.state == self.STATE_CHASE,
            "silent":     False,
            "trap_slow":  0.0,
            "score":      0,
            "kills":      0,
            "ai_state":   self.state,
            "anim_frame": self.anim_frame,
            "roar_event": self.roar_event,
        }
        self.roar_event = False
        return d


class KeyObject:
    def __init__(self, x, y, kid):
        self.x      = x
        self.y      = y
        self.kid    = kid
        self.on_map = True

    def to_dict(self):
        return {
            "x":      round(self.x),
            "y":      round(self.y),
            "on_map": self.on_map,
            "kid":    self.kid,
        }


class DoorObject:
    def __init__(self, x, y, did, keys_needed=1):
        self.x           = x
        self.y           = y
        self.did         = did
        self.open        = False
        self.keys_needed = keys_needed

    def to_dict(self):
        return {
            "x":           round(self.x),
            "y":           round(self.y),
            "open":        self.open,
            "did":         self.did,
            "keys_needed": self.keys_needed,
        }


class TrapObject:
    def __init__(self, x, y, tid):
        self.x       = x
        self.y       = y
        self.tid     = tid
        self.active  = True
        self.visible = False

    def to_dict(self, for_monster=False):
        return {
            "x":      round(self.x),
            "y":      round(self.y),
            "tid":    self.tid,
            "active": self.active,
            "visible": self.visible or for_monster,
        }


# ══════════════════════════════════════════════════════════════
#  ИГРОВАЯ СЕССИЯ
# ══════════════════════════════════════════════════════════════

class GameSession:
    def __init__(self, ai_mode):
        self.ai_mode  = ai_mode
        self.walls    = build_walls()
        self.players  = {}
        self.ai       = None

        self.keys     = []
        self.doors    = []
        self.traps    = []

        self.started   = False
        self.game_over = False
        self.winner    = None
        self.time_left = float(GAME_DURATION)

        self.noise_events = []
        # FIX: events_per_client stores events per-client so all clients get them
        self._pending_events = []  # accumulated events not yet sent
        self._events_lock    = threading.Lock()

        self.lock      = threading.Lock()
        self._last_tick= time.time()

        self.kills_total   = 0
        self.escaped_total = 0

    def _add_event(self, ev):
        """Thread-safe event append."""
        with self._events_lock:
            self._pending_events.append(ev)

    def _consume_events(self):
        """Get and clear pending events (call inside self.lock)."""
        with self._events_lock:
            evs = list(self._pending_events)
            self._pending_events = []
        return evs

    def add_player(self, pid):
        with self.lock:
            x, y = find_free_pos(self.walls, ServerPlayer.RADIUS)
            self.players[pid] = ServerPlayer(pid, x, y)
            print(f"[SESSION] +Player {pid}")

    def remove_player(self, pid):
        with self.lock:
            self.players.pop(pid, None)
            print(f"[SESSION] -Player {pid}")

    def apply_input(self, pid, data):
        with self.lock:
            p = self.players.get(pid)
            if not p or not p.alive:
                return
            p.move_x   = float(data.get("mx", 0))
            p.move_y   = float(data.get("my", 0))
            p.sprinting= bool(data.get("sprint", False))
            p.silent   = bool(data.get("silent", False))

    def start(self):
        with self.lock:
            if self.started or not self.players:
                return
            self.started = True
            print(f"[SESSION] Starting! AI={self.ai_mode}, Players={len(self.players)}")

            spawn_zones = [
                (100, 100, 500, 500),
                (100, 900, 500, 1400),
                (1800, 100, 2300, 500),
                (1800, 1200, 2300, 1700),
                (600, 100, 1000, 500),
                (600, 1200, 1000, 1600),
                (1200, 800, 1600, 1200),
                (1200, 100, 1600, 500),
            ]
            for i, p in enumerate(self.players.values()):
                zone = spawn_zones[i % len(spawn_zones)]
                p.x, p.y = find_free_pos(self.walls, ServerPlayer.RADIUS, zone)
                p.is_monster = False
                p.alive      = True

            if self.ai_mode:
                mx, my = find_free_pos(self.walls, ServerAIMonster.RADIUS,
                                       (1100, 800, 1400, 1100))
                self.ai = ServerAIMonster(mx, my)
            else:
                monster_pid = random.choice(list(self.players.keys()))
                self.players[monster_pid].is_monster = True
                mz = (1900, 1500, 2300, 1750)
                self.players[monster_pid].x, self.players[monster_pid].y = \
                    find_free_pos(self.walls, ServerPlayer.RADIUS, mz)
                print(f"[SESSION] Monster: {monster_pid}")

            key_zones = [
                (1100, 200, 1500, 550),
                (600,  900, 900,  1200),
            ]
            for i in range(NUM_KEYS):
                zone = key_zones[i % len(key_zones)]
                kx, ky = find_free_pos(self.walls, 20, zone)
                self.keys.append(KeyObject(kx, ky, i))

            dx, dy = find_free_pos(self.walls, 25, (1050, 850, 1350, 1050))
            self.doors.append(DoorObject(dx, dy, 0, keys_needed=NUM_KEYS))

            trap_zones = [
                (400, 400, 900, 800),
                (800, 900, 1200, 1300),
                (1400, 400, 1800, 800),
                (1400, 1200, 1900, 1600),
                (200, 1200, 600, 1600),
                (1600, 600, 2000, 1000),
            ]
            for i in range(NUM_TRAPS):
                zone = trap_zones[i % len(trap_zones)]
                tx, ty = find_free_pos(self.walls, 20, zone)
                self.traps.append(TrapObject(tx, ty, i))

    def tick(self):
        now = time.time()
        dt  = min(0.1, now - self._last_tick)
        self._last_tick = now

        if not self.started or self.game_over:
            return

        with self.lock:
            self.time_left -= dt
            if self.time_left <= 0:
                self.time_left = 0
                self._end_game("survivors")
                return

            # FIX: only move players AFTER game has started
            for p in self.players.values():
                self._update_player(p, dt)

            if self.ai:
                self.ai.update(self.players, self.walls, dt, self.noise_events)

            self._check_key_pickup()
            self._check_door_escape()
            self._check_kills()
            self._check_traps()
            self._update_noise(dt)
            self._check_win_conditions()

    def _update_player(self, p, dt):
        if not p.alive or p.escaped:
            return

        if p.trap_slow > 0:
            p.trap_slow -= dt

        if p.is_monster:
            speed = MONSTER_SPEED
        elif p.trap_slow > 0:
            speed = SURVIVOR_SPEED * TRAP_SLOW_FACTOR
        elif p.sprinting:
            speed = SURVIVOR_SPEED * SPRINT_MULT
        elif p.silent:
            speed = SURVIVOR_SPEED * SILENT_MULT
        else:
            speed = SURVIVOR_SPEED

        length = math.hypot(p.move_x, p.move_y)
        if length > 0:
            nx, ny = p.move_x / length, p.move_y / length
            step   = speed * dt * TICK_RATE
            p.x, p.y = move_with_collision(
                p.x, p.y, nx*step, ny*step, ServerPlayer.RADIUS, self.walls)
            p.steps += 1

            if not p.is_monster:
                p.noise_timer -= dt
                if p.noise_timer <= 0:
                    if p.silent:
                        radius, interval = NOISE_SILENT, 1.0
                    elif p.sprinting:
                        radius, interval = NOISE_RUN, 0.25
                    else:
                        radius, interval = NOISE_WALK, 0.45
                    self.noise_events.append({
                        "x": p.x, "y": p.y,
                        "radius": radius,
                        "ttl": NOISE_TTL,
                        "owner": p.pid,
                    })
                    p.noise_timer = interval

    def _check_key_pickup(self):
        for key in self.keys:
            if not key.on_map:
                continue
            for p in self.players.values():
                if p.is_monster or not p.alive:
                    continue
                if dist(p.x, p.y, key.x, key.y) < KEY_PICKUP_RADIUS:
                    key.on_map   = False
                    p.has_key    = True
                    p.keys_held += 1
                    p.score     += 200
                    self._add_event({"type": "key_picked", "pid": p.pid, "kid": key.kid})
                    print(f"[SESSION] {p.pid} picked up key {key.kid}")

                    all_picked = all(not k.on_map for k in self.keys)
                    if all_picked:
                        for door in self.doors:
                            door.open = True
                        self._add_event({"type": "door_opened"})
                    break

    def _check_door_escape(self):
        all_picked = all(not k.on_map for k in self.keys)
        if not all_picked:
            return
        for door in self.doors:
            if not door.open:
                continue
            for p in self.players.values():
                if p.is_monster or not p.alive or p.escaped:
                    continue
                if dist(p.x, p.y, door.x, door.y) < DOOR_USE_RADIUS:
                    p.escaped = True
                    p.score  += 500
                    self.escaped_total += 1
                    self._add_event({"type": "escaped", "pid": p.pid})
                    print(f"[SESSION] {p.pid} escaped!")

    def _check_kills(self):
        monsters = []
        if self.ai:
            monsters.append(("AI", self.ai.x, self.ai.y))
        for p in self.players.values():
            if p.is_monster and p.alive:
                monsters.append((p.pid, p.x, p.y))

        for mpid, monster_x, monster_y in monsters:
            for p in list(self.players.values()):
                if p.is_monster or not p.alive or p.escaped:
                    continue
                if dist(monster_x, monster_y, p.x, p.y) < KILL_RADIUS + ServerPlayer.RADIUS:
                    p.alive = False
                    p.score = max(0, p.score - 100)
                    self.kills_total += 1
                    self._add_event({"type": "killed", "pid": p.pid, "by": mpid})
                    print(f"[SESSION] {p.pid} killed by {mpid}")
                    if mpid != "AI":
                        killer = self.players.get(mpid)
                        if killer:
                            killer.kills += 1
                            killer.score += 300

    def _check_traps(self):
        for trap in self.traps:
            if not trap.active:
                continue
            for p in self.players.values():
                if p.is_monster or not p.alive or p.escaped:
                    continue
                if dist(p.x, p.y, trap.x, trap.y) < TRAP_RADIUS:
                    p.trap_slow = TRAP_SLOW_TIME
                    trap.active = False
                    self._add_event({"type": "trap_triggered", "pid": p.pid, "tid": trap.tid})
                    print(f"[SESSION] {p.pid} triggered trap {trap.tid}")

    def _update_noise(self, dt):
        for e in self.noise_events:
            e["ttl"] -= dt
        self.noise_events = [e for e in self.noise_events if e["ttl"] > 0]

    def _check_win_conditions(self):
        survivors = [p for p in self.players.values() if not p.is_monster]
        alive_sv  = [p for p in survivors if p.alive and not p.escaped]
        escaped   = [p for p in survivors if p.escaped]

        if survivors and not alive_sv and not escaped:
            self._end_game("monster")
            return
        if escaped and not alive_sv:
            self._end_game("survivors")

    def _end_game(self, winner):
        if self.game_over:
            return
        self.game_over = True
        self.winner    = winner
        self._add_event({"type": "game_over", "winner": winner})
        print(f"[SESSION] Game over! Winner: {winner}")

    def get_state(self, is_monster=False):
        """
        FIX: events are accumulated in _pending_events and consumed once per tick-broadcast
        so ALL clients get the same events in the same broadcast cycle.
        get_state() now takes events as a parameter to avoid clearing them per-client.
        """
        with self.lock:
            walls_data = [[w["r"][0], w["r"][1], w["r"][2], w["r"][3]]
                          for w in self.walls]

            # FIX: Fixed trap visibility logic
            # Monsters see all traps; survivors only see triggered (inactive) traps
            traps_data = []
            for trap_obj in self.traps:
                td = trap_obj.to_dict(for_monster=is_monster)
                if is_monster:
                    traps_data.append(td)
                elif not trap_obj.active:
                    # Survivors can see triggered traps
                    traps_data.append(td)
                # Active traps are hidden from survivors (invisible until triggered)

            st = {
                "type":       "state",
                "players":    {pid: p.to_dict() for pid, p in self.players.items()},
                "ai_monster": self.ai.to_dict() if self.ai else None,
                "keys":       [k.to_dict() for k in self.keys],
                "doors":      [d.to_dict() for d in self.doors],
                "traps":      traps_data,
                "walls":      walls_data,
                "time_left":  round(self.time_left, 1),
                "game_over":  self.game_over,
                "winner":     self.winner,
                "started":    self.started,
                "ai_mode":    self.ai_mode,
                "noise_events": list(self.noise_events),
                "map_w":      MAP_W,
                "map_h":      MAP_H,
                "stats": {
                    "kills_total":   self.kills_total,
                    "escaped_total": self.escaped_total,
                },
            }
            return st

    def get_and_clear_events(self):
        """FIX: Separate method to consume events once per broadcast cycle."""
        return self._consume_events()


# ══════════════════════════════════════════════════════════════
#  ОБРАБОТЧИК КЛИЕНТА
# ══════════════════════════════════════════════════════════════

class ClientHandler(threading.Thread):
    def __init__(self, conn, addr, pid, session):
        super().__init__(daemon=True)
        self.conn    = conn
        self.addr    = addr
        self.pid     = pid
        self.session = session
        self.running = True
        self._buf    = ""

    def run(self):
        try:
            while self.running:
                chunk = self.conn.recv(8192)
                if not chunk:
                    break
                self._buf += chunk.decode("utf-8", errors="ignore")
                while "\n" in self._buf:
                    line, self._buf = self._buf.split("\n", 1)
                    self._handle(line.strip())
        except Exception as e:
            print(f"[CLIENT {self.addr}] Error: {e}")
        finally:
            self.running = False
            self.session.remove_player(self.pid)
            try:
                self.conn.close()
            except Exception:
                pass
            print(f"[CLIENT {self.addr}] Disconnected.")

    def _handle(self, raw):
        if not raw:
            return
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            return
        t = msg.get("type")
        if t == "input":
            self.session.apply_input(self.pid, msg)
        elif t == "start":
            self.session.start()
        elif t == "ping":
            self.send({"type": "pong", "ts": msg.get("ts", 0)})

    def send(self, obj):
        try:
            self.conn.sendall((json.dumps(obj) + "\n").encode())
        except Exception:
            self.running = False

    def is_monster(self):
        with self.session.lock:
            p = self.session.players.get(self.pid)
            if p:
                return p.is_monster
            return self.session.ai_mode


# ══════════════════════════════════════════════════════════════
#  СЕРВЕР
# ══════════════════════════════════════════════════════════════

class GameServer:
    def __init__(self, ai_mode):
        self.session = GameSession(ai_mode)
        self.clients = {}
        self._lock   = threading.Lock()
        self._pid_n  = 0
        self.running = True

    def start(self):
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((HOST, PORT))
        srv.listen(MAX_PLAYERS)
        srv.settimeout(1.0)
        print(f"[SERVER] Listening on {HOST}:{PORT} (max {MAX_PLAYERS} players)")
        print(f"[SERVER] Map: {MAP_W}x{MAP_H}  Keys: {NUM_KEYS}  Traps: {NUM_TRAPS}")

        threading.Thread(target=self._accept_loop, args=(srv,), daemon=True).start()
        self._game_loop()

    def _accept_loop(self, srv):
        while self.running:
            try:
                conn, addr = srv.accept()
            except socket.timeout:
                continue
            except Exception:
                break

            with self._lock:
                if len(self.clients) >= MAX_PLAYERS:
                    conn.close()
                    print(f"[SERVER] Rejected {addr} (full)")
                    continue
                self._pid_n += 1
                pid     = f"P{self._pid_n}"
                self.session.add_player(pid)
                handler = ClientHandler(conn, addr, pid, self.session)
                self.clients[pid] = handler
                handler.start()
                handler.send({
                    "type":    "hello",
                    "pid":     pid,
                    "map_w":   MAP_W,
                    "map_h":   MAP_H,
                    "ai_mode": self.session.ai_mode,
                    "max_players": MAX_PLAYERS,
                    "version": "4.0",
                })
                print(f"[SERVER] +{addr} → {pid}  ({len(self.clients)}/{MAX_PLAYERS})")

    def _game_loop(self):
        tick_dt      = 1.0 / TICK_RATE
        broadcast_dt = 1.0 / BROADCAST_RATE
        last_bcast   = time.time()

        while self.running:
            t0 = time.time()
            self.session.tick()

            now = time.time()
            if now - last_bcast >= broadcast_dt:
                last_bcast = now

                # FIX: Consume events ONCE per broadcast cycle, then include
                # in every client's state packet so all clients get the events.
                current_events = self.session.get_and_clear_events()

                dead = []
                with self._lock:
                    for pid, h in self.clients.items():
                        if h.running:
                            state = self.session.get_state(is_monster=h.is_monster())
                            # Attach the shared events to this state packet
                            state["events"] = current_events
                            h.send(state)
                        else:
                            dead.append(pid)
                    for pid in dead:
                        del self.clients[pid]

            elapsed = time.time() - t0
            sleep   = tick_dt - elapsed
            if sleep > 0:
                time.sleep(sleep)


# ══════════════════════════════════════════════════════════════
#  GUI ВЫБОРА РЕЖИМА
# ══════════════════════════════════════════════════════════════

class ModeSelectGUI:
    def run(self):
        try:
            import pygame
            pygame.init()
        except ImportError:
            print("pygame не установлен. Запустите: pip install pygame")
            return self._console_mode()

        screen = pygame.display.set_mode((560, 420))
        pygame.display.set_caption("HORROR LAN v4.0 — Сервер")
        clock  = pygame.time.Clock()

        try:
            f_title = pygame.font.SysFont("monospace", 32, bold=True)
            f_btn   = pygame.font.SysFont("monospace", 22, bold=True)
            f_sm    = pygame.font.SysFont("monospace", 14)
        except Exception:
            pygame.quit()
            return self._console_mode()

        BW, BH = 380, 58
        bx = 280 - BW//2
        btn_mp   = pygame.Rect(bx, 180, BW, BH)
        btn_ai   = pygame.Rect(bx, 254, BW, BH)
        btn_quit = pygame.Rect(bx, 340, BW, 38)

        result = None
        anim   = 0.0

        while result is None:
            dt = clock.tick(30) / 1000.0
            anim += dt

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    return None
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if btn_mp.collidepoint(event.pos):
                        result = False
                    elif btn_ai.collidepoint(event.pos):
                        result = True
                    elif btn_quit.collidepoint(event.pos):
                        pygame.quit()
                        return None

            mouse = pygame.mouse.get_pos()
            screen.fill((8, 8, 14))

            for x in range(0, 560, 56):
                pygame.draw.line(screen, (16,16,24), (x,0), (x,420))
            for y in range(0, 420, 56):
                pygame.draw.line(screen, (16,16,24), (0,y), (560,y))

            r_val = int(155 + 100 * abs(math.sin(anim * 2.0)))
            t = f_title.render("☠  HORROR LAN  v4.0", True, (r_val, 20, 20))
            screen.blit(t, t.get_rect(centerx=280, y=28))

            info_lines = [
                f"Карта: {MAP_W}x{MAP_H}  |  Игроков: до {MAX_PLAYERS}",
                f"Ключей: {NUM_KEYS}  |  Ловушек: {NUM_TRAPS}  |  Порт: {PORT}",
            ]
            for i, line in enumerate(info_lines):
                s = f_sm.render(line, True, (80, 80, 110))
                screen.blit(s, s.get_rect(centerx=280, y=78+i*18))

            for btn, text, c, desc in [
                (btn_mp,   "🎮  Мультиплеер (PvP)",  (55,15,15),  "Один игрок — монстр"),
                (btn_ai,   "🤖  AI-монстр",           (15,15,60),  "Все против ИИ"),
                (btn_quit, "✕  Выход",                (22,8,8),    ""),
            ]:
                hov = btn.collidepoint(mouse)
                col = tuple(min(255, x+50) for x in c) if hov else c
                pygame.draw.rect(screen, col, btn, border_radius=10)
                pygame.draw.rect(screen, (120,40,40), btn, 2, border_radius=10)
                tf = f_btn if btn != btn_quit else f_sm
                tt = tf.render(text, True, (255,255,255))
                screen.blit(tt, tt.get_rect(center=btn.center))
                if desc:
                    ds = f_sm.render(desc, True, (120,80,80))
                    screen.blit(ds, (btn.right + 8, btn.centery - 7))

            pygame.display.flip()

        pygame.quit()
        return result

    def _console_mode(self):
        print("\nВыберите режим:")
        print("  1 — Мультиплеер (PvP)")
        print("  2 — AI-монстр")
        print("  0 — Выход")
        while True:
            choice = input("Ваш выбор: ").strip()
            if choice == "1":
                return False
            elif choice == "2":
                return True
            elif choice == "0":
                return None


# ══════════════════════════════════════════════════════════════
#  ТОЧКА ВХОДА
# ══════════════════════════════════════════════════════════════

def main():
    print("=" * 62)
    print("  HORROR LAN — SERVER v4.0 ULTRA (FIXED)")
    print("=" * 62)
    print(f"  Карта: {MAP_W}x{MAP_H}")
    print(f"  Макс. игроков: {MAX_PLAYERS}")
    print(f"  Порт: {PORT}")
    print("=" * 62)

    gui     = ModeSelectGUI()
    ai_mode = gui.run()

    if ai_mode is None:
        print("Exit.")
        sys.exit(0)

    mode_str = "AI-монстр" if ai_mode else "Мультиплеер"
    print(f"\n[SERVER] Режим: {mode_str}")
    print(f"[SERVER] Запуск на {HOST}:{PORT} ...")

    server = GameServer(ai_mode)
    try:
        server.start()
    except KeyboardInterrupt:
        print("\n[SERVER] Stopped.")


if __name__ == "__main__":
    main()

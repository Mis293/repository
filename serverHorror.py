"""
╔══════════════════════════════════════════════════════════════════╗
║  HORROR LAN — SERVER  v3.0                                      ║
║                                                                  ║
║  Запуск: python server.py                                        ║
║  Сервер выбирает режим через GUI (pygame).                       ║
║  Порт: 5555                                                      ║
╚══════════════════════════════════════════════════════════════════╝
"""

import socket
import threading
import json
import time
import random
import math
import sys

import pygame   # только для GUI выбора режима на сервере

# ══════════════════════════════════════════════════════════════
#  КОНФИГУРАЦИЯ
# ══════════════════════════════════════════════════════════════

HOST       = "0.0.0.0"
PORT       = 5555
MAX_PLAYERS = 4
TICK_RATE  = 30          # обновлений игры в секунду
BROADCAST_RATE = 20      # отправок состояния клиентам в секунду

# Размер карты
MAP_W = 1600
MAP_H = 1200

# Параметры геймплея
GAME_DURATION   = 300    # 5 минут
MONSTER_SPEED   = 2.8    # пикселей за тик
SURVIVOR_SPEED  = 2.0
SPRINT_MULT     = 1.65
SILENT_MULT     = 0.60
KILL_RADIUS     = 28     # радиус захвата монстра
KEY_PICKUP_RADIUS = 36   # радиус подбора ключа
DOOR_USE_RADIUS   = 40   # радиус использования двери

# Параметры ИИ
AI_SIGHT_RADIUS = 280    # радиус обнаружения игрока монстром
AI_PATROL_SPEED = 1.4    # скорость патрулирования

# Шум шагов
NOISE_WALK   = 190
NOISE_RUN    = 340
NOISE_SILENT = 45
NOISE_TTL    = 1.8       # время жизни события шума


# ══════════════════════════════════════════════════════════════
#  СТЕНЫ (ПРЕПЯТСТВИЯ)
# ══════════════════════════════════════════════════════════════

def build_walls() -> list[pygame.Rect]:
    """
    Создаём набор прямоугольных стен для карты.
    Все координаты в мировом пространстве.
    """
    walls = []

    # ── Граница карты (4 стены) ──────────────────────────────
    T = 20   # толщина граничной стены
    walls += [
        pygame.Rect(0,       0,       MAP_W, T),        # верх
        pygame.Rect(0,       MAP_H-T, MAP_W, T),        # низ
        pygame.Rect(0,       0,       T,     MAP_H),    # лево
        pygame.Rect(MAP_W-T, 0,       T,     MAP_H),    # право
    ]

    # ── Внутренние препятствия ───────────────────────────────
    # (задаём вручную для предсказуемой карты)
    inner = [
        # Блоки в левой части
        (120,  100,  60,  200),
        (120,  380,  60,  160),
        (250,  120, 140,   50),
        (250,  300, 140,   50),

        # Центральный коридор
        (500,   80,  50,  300),
        (500,  500,  50,  300),
        (700,  200, 200,   50),
        (700,  600, 200,   50),

        # Правая часть
        (1050, 100, 200,   50),
        (1050, 250,  50,  200),
        (1300, 100,  50,  300),
        (1050, 600, 200,   50),
        (1050, 750,  50,  200),
        (1300, 600,  50,  300),

        # Нижняя зона
        (200,  750, 180,   50),
        (200,  900, 180,   50),
        (500,  800, 300,   50),
        (500,  950, 300,   50),
        (900,  800,  50,  200),

        # Дополнительные укрытия
        (650,  400, 100,  100),
        (380,  550,  80,   80),
        (820,  450,  80,  140),
        (1150, 450,  80,  100),
        (400,  850,  60,  120),
        (800, 1000, 160,   50),
    ]
    for x, y, w, h in inner:
        walls.append(pygame.Rect(x, y, w, h))

    return walls


# ══════════════════════════════════════════════════════════════
#  ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ══════════════════════════════════════════════════════════════

def dist(ax, ay, bx, by) -> float:
    return math.hypot(ax - bx, ay - by)


def normalize(dx, dy) -> tuple[float, float]:
    """Нормализует вектор. Возвращает (0, 0) для нулевого вектора."""
    length = math.hypot(dx, dy)
    if length == 0:
        return 0.0, 0.0
    return dx / length, dy / length


def rect_collides_circle(rect: pygame.Rect, cx: float, cy: float, r: float) -> bool:
    """Проверяет столкновение окружности с прямоугольником."""
    nearest_x = max(rect.left, min(cx, rect.right))
    nearest_y = max(rect.top,  min(cy, rect.bottom))
    return math.hypot(cx - nearest_x, cy - nearest_y) < r


def line_of_sight(walls: list[pygame.Rect],
                  ax: float, ay: float,
                  bx: float, by: float) -> bool:
    """
    Проверяет, есть ли прямая видимость между точками A и B.
    Возвращает True если НЕТ препятствий на пути (видно).
    Использует простую дискретную проверку вдоль луча.
    """
    dx, dy  = bx - ax, by - ay
    length  = math.hypot(dx, dy)
    if length == 0:
        return True
    steps  = int(length / 12) + 1
    sx, sy = dx / steps, dy / steps
    for i in range(1, steps):
        px, py = ax + sx * i, ay + sy * i
        for w in walls:
            if w.collidepoint(px, py):
                return False
    return True


def move_with_collision(x: float, y: float,
                        dx: float, dy: float,
                        radius: float,
                        walls: list[pygame.Rect]) -> tuple[float, float]:
    """
    Двигает точку (x, y) на (dx, dy) с учётом коллизий со стенами.
    Пробуем двигаться по X и Y раздельно (sliding collision).
    """
    # Попытка движения по X
    nx = x + dx
    collide_x = any(rect_collides_circle(w, nx, y, radius) for w in walls)
    if not collide_x:
        x = nx

    # Попытка движения по Y
    ny = y + dy
    collide_y = any(rect_collides_circle(w, x, ny, radius) for w in walls)
    if not collide_y:
        y = ny

    return x, y


def find_free_pos(walls: list[pygame.Rect], radius: float = 30) -> tuple[float, float]:
    """Ищет случайную позицию без пересечения со стенами."""
    for _ in range(1000):
        x = random.uniform(50, MAP_W - 50)
        y = random.uniform(50, MAP_H - 50)
        if not any(rect_collides_circle(w, x, y, radius) for w in walls):
            return x, y
    return MAP_W / 2, MAP_H / 2


# ══════════════════════════════════════════════════════════════
#  КЛАССЫ ИГРОВЫХ ОБЪЕКТОВ (СЕРВЕРНАЯ СТОРОНА)
# ══════════════════════════════════════════════════════════════

class ServerPlayer:
    """Состояние одного подключённого игрока на сервере."""

    RADIUS = 16  # радиус коллизии персонажа

    def __init__(self, pid: str, x: float, y: float):
        self.pid      = pid
        self.x        = x
        self.y        = y
        self.alive    = True
        self.escaped  = False        # добрался до двери
        self.is_monster = False
        self.has_key  = False        # держит ключ
        # Направление движения от клиента
        self.move_x   = 0.0
        self.move_y   = 0.0
        self.sprinting = False
        self.silent    = False
        # Таймер шагового шума
        self.noise_timer = 0.0

    def to_dict(self) -> dict:
        return {
            "pid":        self.pid,
            "x":          round(self.x, 1),
            "y":          round(self.y, 1),
            "alive":      self.alive,
            "escaped":    self.escaped,
            "is_monster": self.is_monster,
            "has_key":    self.has_key,
            "sprinting":  self.sprinting,
            "silent":     self.silent,
        }


class ServerAIMonster:
    """ИИ-монстр на сервере."""

    RADIUS = 18

    def __init__(self, x: float, y: float):
        self.x      = x
        self.y      = y
        self.pid    = "AI"
        self.target : ServerPlayer | None = None
        # Для патрулирования (когда нет цели)
        self._patrol_target_x = x
        self._patrol_target_y = y
        self._patrol_timer    = 0.0

    def update(self, players: dict[str, "ServerPlayer"],
               walls: list[pygame.Rect], dt: float):
        """Обновляем позицию ИИ-монстра."""
        self._pick_target(players, walls)
        self._move(walls, dt)

    def _pick_target(self, players: dict[str, "ServerPlayer"],
                     walls: list[pygame.Rect]):
        """Выбираем ближайшего видимого живого выжившего."""
        best     = None
        best_dist = float("inf")
        for p in players.values():
            if not p.alive or p.is_monster:
                continue
            d = dist(self.x, self.y, p.x, p.y)
            if d > AI_SIGHT_RADIUS:
                continue
            # Проверка линии видимости
            if not line_of_sight(walls, self.x, self.y, p.x, p.y):
                continue
            if d < best_dist:
                best_dist = d
                best      = p
        self.target = best

    def _move(self, walls: list[pygame.Rect], dt: float):
        if self.target:
            # Преследование
            dx, dy = normalize(self.target.x - self.x, self.target.y - self.y)
            speed  = MONSTER_SPEED
        else:
            # Патрулирование к случайной точке
            self._patrol_timer -= dt
            tdx = self._patrol_target_x - self.x
            tdy = self._patrol_target_y - self.y
            if math.hypot(tdx, tdy) < 20 or self._patrol_timer <= 0:
                self._patrol_target_x, self._patrol_target_y = \
                    find_free_pos(walls, self.RADIUS)
                self._patrol_timer = random.uniform(3, 8)
            dx, dy = normalize(tdx, tdy)
            speed  = AI_PATROL_SPEED

        step   = speed * dt * TICK_RATE
        self.x, self.y = move_with_collision(
            self.x, self.y, dx * step, dy * step, self.RADIUS, walls)

    def to_dict(self) -> dict:
        return {
            "pid":        "AI",
            "x":          round(self.x, 1),
            "y":          round(self.y, 1),
            "alive":      True,
            "escaped":    False,
            "is_monster": True,
            "has_key":    False,
            "sprinting":  False,
            "silent":     False,
        }


class KeyObject:
    """Ключ на карте. Подбирается выжившим."""

    def __init__(self, x: float, y: float):
        self.x       = x
        self.y       = y
        self.on_map  = True    # True пока лежит на карте

    def to_dict(self) -> dict:
        return {"x": round(self.x), "y": round(self.y), "on_map": self.on_map}


class DoorObject:
    """Дверь — точка выхода для выживших с ключом."""

    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y
        self.open = False      # открывается когда ключ подобран

    def to_dict(self) -> dict:
        return {"x": round(self.x), "y": round(self.y), "open": self.open}


# ══════════════════════════════════════════════════════════════
#  ИГРОВАЯ СЕССИЯ
# ══════════════════════════════════════════════════════════════

class GameSession:
    """
    Хранит полное состояние игры.
    Обновляется в главном игровом цикле (тик).
    """

    def __init__(self, ai_mode: bool):
        self.ai_mode  = ai_mode
        self.walls    = build_walls()
        self.players  : dict[str, ServerPlayer] = {}
        self.ai       : ServerAIMonster | None  = None

        # Ключ и дверь появляются при старте
        self.key  : KeyObject  | None = None
        self.door : DoorObject | None = None

        self.started   = False
        self.game_over = False
        self.winner    = None          # "survivors" | "monster"
        self.time_left = float(GAME_DURATION)

        # Шумовые события для монстра
        self.noise_events : list[dict] = []

        self.lock = threading.Lock()
        self._last_tick = time.time()

    # ── Игроки ───────────────────────────────────────────────

    def add_player(self, pid: str):
        with self.lock:
            x, y = find_free_pos(self.walls, ServerPlayer.RADIUS)
            self.players[pid] = ServerPlayer(pid, x, y)
            print(f"[SESSION] +Player {pid} @ ({x:.0f},{y:.0f})")

    def remove_player(self, pid: str):
        with self.lock:
            self.players.pop(pid, None)
            print(f"[SESSION] -Player {pid}")

    def apply_input(self, pid: str, data: dict):
        with self.lock:
            p = self.players.get(pid)
            if not p or not p.alive:
                return
            p.move_x   = float(data.get("mx", 0))
            p.move_y   = float(data.get("my", 0))
            p.sprinting = bool(data.get("sprint", False))
            p.silent    = bool(data.get("silent", False))

    # ── Старт ────────────────────────────────────────────────

    def start(self):
        with self.lock:
            if self.started or not self.players:
                return
            self.started = True
            print(f"[SESSION] Starting! AI={self.ai_mode}")

            # Размещаем игроков
            for p in self.players.values():
                p.x, p.y = find_free_pos(self.walls, ServerPlayer.RADIUS)
                p.is_monster = False

            if self.ai_mode:
                # Монстр — ИИ, появляется в центре карты
                mx, my = find_free_pos(self.walls, ServerAIMonster.RADIUS)
                self.ai = ServerAIMonster(mx, my)
            else:
                # Случайный игрок становится монстром
                monster_pid = random.choice(list(self.players.keys()))
                self.players[monster_pid].is_monster = True
                # Монстр появляется в другом конце карты от остальных
                self.players[monster_pid].x = MAP_W - 150
                self.players[monster_pid].y = MAP_H - 150
                print(f"[SESSION] Monster: {monster_pid}")

            # Ключ и дверь в случайных местах
            self.key  = KeyObject(*find_free_pos(self.walls, 20))
            self.door = DoorObject(*find_free_pos(self.walls, 20))
            print(f"[SESSION] Key@({self.key.x:.0f},{self.key.y:.0f})  "
                  f"Door@({self.door.x:.0f},{self.door.y:.0f})")

    # ── Тик ──────────────────────────────────────────────────

    def tick(self):
        now = time.time()
        dt  = now - self._last_tick
        self._last_tick = now

        if not self.started or self.game_over:
            return

        with self.lock:
            self.time_left -= dt
            if self.time_left <= 0:
                self.time_left = 0
                self._end_game("survivors")
                return

            # 1. Двигаем игроков
            for p in self.players.values():
                self._update_player(p, dt)

            # 2. Двигаем AI монстра
            if self.ai:
                self.ai.update(self.players, self.walls, dt)

            # 3. Проверяем взаимодействия
            self._check_key_pickup()
            self._check_door_escape()
            self._check_kills()
            self._update_noise(dt)

            # 4. Проверка условий победы
            self._check_win_conditions()

    def _update_player(self, p: ServerPlayer, dt: float):
        if not p.alive:
            return

        # Скорость зависит от режима движения
        if p.is_monster:
            speed = MONSTER_SPEED
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
                p.x, p.y, nx * step, ny * step, ServerPlayer.RADIUS, self.walls)

            # Генерация шума (только выжившие)
            if not p.is_monster:
                p.noise_timer -= dt
                if p.noise_timer <= 0:
                    if p.silent:
                        radius, interval = NOISE_SILENT, 0.9
                    elif p.sprinting:
                        radius, interval = NOISE_RUN, 0.3
                    else:
                        radius, interval = NOISE_WALK, 0.5
                    self.noise_events.append({
                        "x": p.x, "y": p.y,
                        "radius": radius,
                        "ttl": NOISE_TTL,
                    })
                    p.noise_timer = interval

    def _check_key_pickup(self):
        """Выживший подбирает ключ, если близко к нему."""
        if not self.key or not self.key.on_map:
            return
        for p in self.players.values():
            if p.is_monster or not p.alive:
                continue
            if dist(p.x, p.y, self.key.x, self.key.y) < KEY_PICKUP_RADIUS:
                self.key.on_map = False
                p.has_key = True
                # Дверь открывается
                if self.door:
                    self.door.open = True
                print(f"[SESSION] {p.pid} подобрал ключ!")
                break

    def _check_door_escape(self):
        """Выживший с ключом касается двери — он спасён."""
        if not self.door or not self.door.open:
            return
        for p in self.players.values():
            if p.is_monster or not p.alive or p.escaped:
                continue
            if dist(p.x, p.y, self.door.x, self.door.y) < DOOR_USE_RADIUS:
                p.escaped = True
                print(f"[SESSION] {p.pid} сбежал!")

    def _check_kills(self):
        """Монстр убивает выживших при касании."""
        monsters = []
        if self.ai:
            monsters.append(self.ai)
        monsters += [p for p in self.players.values()
                     if p.is_monster and p.alive]

        for m in monsters:
            for p in self.players.values():
                if p.is_monster or not p.alive or p.escaped:
                    continue
                if dist(m.x, m.y, p.x, p.y) < KILL_RADIUS + ServerPlayer.RADIUS:
                    p.alive = False
                    print(f"[SESSION] {p.pid} убит!")

    def _update_noise(self, dt: float):
        """Уменьшаем TTL шумовых событий и удаляем истёкшие."""
        for e in self.noise_events:
            e["ttl"] -= dt
        self.noise_events = [e for e in self.noise_events if e["ttl"] > 0]

    def _check_win_conditions(self):
        survivors = [p for p in self.players.values()
                     if not p.is_monster]
        alive_survivors = [p for p in survivors if p.alive and not p.escaped]
        escaped = [p for p in survivors if p.escaped]

        # Монстр побеждает если все выжившие мертвы (и никто не сбежал)
        if len(survivors) > 0 and not alive_survivors and not escaped:
            self._end_game("monster")
            return

        # Выжившие побеждают если хоть один сбежал и таймер вышел
        # (победа по таймеру — проверяется в tick, когда time_left ≤ 0)
        if escaped and self.time_left <= 0:
            self._end_game("survivors")

    def _end_game(self, winner: str):
        if self.game_over:
            return
        self.game_over = True
        self.winner    = winner
        print(f"[SESSION] Игра окончена! Победитель: {winner}")

    # ── Сборка состояния ─────────────────────────────────────

    def get_state(self) -> dict:
        with self.lock:
            return {
                "type":         "state",
                "players":      {pid: p.to_dict()
                                 for pid, p in self.players.items()},
                "ai_monster":   self.ai.to_dict() if self.ai else None,
                "key":          self.key.to_dict()  if self.key  else None,
                "door":         self.door.to_dict() if self.door else None,
                "walls":        [[w.x, w.y, w.width, w.height]
                                 for w in self.walls],
                "time_left":    round(self.time_left, 1),
                "game_over":    self.game_over,
                "winner":       self.winner,
                "started":      self.started,
                "ai_mode":      self.ai_mode,
                "noise_events": list(self.noise_events),
                "map_w":        MAP_W,
                "map_h":        MAP_H,
            }


# ══════════════════════════════════════════════════════════════
#  ОБРАБОТЧИК КЛИЕНТА
# ══════════════════════════════════════════════════════════════

class ClientHandler(threading.Thread):
    """Поток для каждого подключённого игрока."""

    def __init__(self, conn: socket.socket, addr, pid: str, session: GameSession):
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
                chunk = self.conn.recv(4096)
                if not chunk:
                    break
                self._buf += chunk.decode("utf-8", errors="ignore")
                while "\n" in self._buf:
                    line, self._buf = self._buf.split("\n", 1)
                    self._handle(line.strip())
        except Exception as e:
            print(f"[CLIENT {self.addr}] Ошибка: {e}")
        finally:
            self.running = False
            self.session.remove_player(self.pid)
            try:
                self.conn.close()
            except Exception:
                pass
            print(f"[CLIENT {self.addr}] Отключён.")

    def _handle(self, raw: str):
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

    def send(self, obj: dict):
        try:
            self.conn.sendall((json.dumps(obj) + "\n").encode())
        except Exception:
            self.running = False


# ══════════════════════════════════════════════════════════════
#  СЕРВЕР
# ══════════════════════════════════════════════════════════════

class GameServer:
    def __init__(self, ai_mode: bool):
        self.session = GameSession(ai_mode)
        self.clients : dict[str, ClientHandler] = {}
        self._lock   = threading.Lock()
        self._pid_n  = 0
        self.running = True

    def start(self):
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((HOST, PORT))
        srv.listen(MAX_PLAYERS)
        srv.settimeout(1.0)
        print(f"[SERVER] Слушаем {HOST}:{PORT}")

        # Поток принятия соединений
        threading.Thread(target=self._accept_loop,
                         args=(srv,), daemon=True).start()
        # Главный игровой цикл
        self._game_loop()

    def _accept_loop(self, srv: socket.socket):
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
                    print(f"[SERVER] Отклонён {addr} (сервер полон)")
                    continue
                self._pid_n += 1
                pid = f"P{self._pid_n}"
                self.session.add_player(pid)
                handler = ClientHandler(conn, addr, pid, self.session)
                self.clients[pid] = handler
                handler.start()
                # Отправляем приветствие
                handler.send({
                    "type":    "hello",
                    "pid":     pid,
                    "map_w":   MAP_W,
                    "map_h":   MAP_H,
                    "ai_mode": self.session.ai_mode,
                })
                print(f"[SERVER] +{addr} → {pid}")

    def _game_loop(self):
        tick_dt      = 1.0 / TICK_RATE
        broadcast_dt = 1.0 / BROADCAST_RATE
        last_bcast   = time.time()

        while self.running:
            t0 = time.time()

            # Тик логики
            self.session.tick()

            # Рассылка состояния
            now = time.time()
            if now - last_bcast >= broadcast_dt:
                last_bcast = now
                state = self.session.get_state()
                dead  = []
                with self._lock:
                    for pid, h in self.clients.items():
                        if h.running:
                            h.send(state)
                        else:
                            dead.append(pid)
                    for pid in dead:
                        del self.clients[pid]

            # Ограничение FPS
            elapsed = time.time() - t0
            sleep   = tick_dt - elapsed
            if sleep > 0:
                time.sleep(sleep)


# ══════════════════════════════════════════════════════════════
#  GUI ВЫБОРА РЕЖИМА (pygame)
# ══════════════════════════════════════════════════════════════

class ModeSelectGUI:
    """
    Простое окно для выбора режима игры перед стартом сервера.
    Возвращает True (AI) или False (Multiplayer).
    """

    def run(self) -> bool | None:
        pygame.init()
        screen = pygame.display.set_mode((480, 340))
        pygame.display.set_caption("HORROR LAN — Сервер: выбор режима")
        clock  = pygame.font.SysFont("monospace", 14)
        f_big  = pygame.font.SysFont("monospace", 30, bold=True)
        f_med  = pygame.font.SysFont("monospace", 20, bold=True)
        f_sm   = pygame.font.SysFont("monospace", 14)

        BW, BH = 320, 55
        bx = 240 - BW // 2
        btn_mp  = pygame.Rect(bx, 160, BW, BH)
        btn_ai  = pygame.Rect(bx, 228, BW, BH)
        btn_quit= pygame.Rect(bx, 300, BW, 30)

        result = None
        anim   = 0.0
        fps_clk= pygame.time.Clock()

        while result is None:
            dt = fps_clk.tick(30) / 1000.0
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
            screen.fill((10, 10, 16))

            # Сетка фона
            for x in range(0, 480, 48):
                pygame.draw.line(screen, (18, 18, 26), (x, 0), (x, 340))
            for y in range(0, 340, 48):
                pygame.draw.line(screen, (18, 18, 26), (0, y), (480, y))

            # Заголовок
            p = int(160 + 95 * math.sin(anim * 2.2))
            t = f_big.render("☠  HORROR LAN", True, (p, 20, 20))
            screen.blit(t, (240 - t.get_width() // 2, 30))
            s = f_sm.render("Сервер — выберите режим игры", True, (100, 100, 120))
            screen.blit(s, (240 - s.get_width() // 2, 78))
            s2 = f_sm.render(f"Порт: {PORT}   Карта: {MAP_W}x{MAP_H}", True, (70, 70, 90))
            screen.blit(s2, (240 - s2.get_width() // 2, 100))

            # Кнопки
            for btn, text, c in [
                (btn_mp,  "🎮  Мультиплеер",  (55, 18, 18)),
                (btn_ai,  "🤖  AI-монстр",    (18, 18, 60)),
                (btn_quit,"✕  Выход",         (25, 10, 10)),
            ]:
                hov = btn.collidepoint(mouse)
                col = tuple(min(255, x + 40) for x in c) if hov else c
                pygame.draw.rect(screen, col,           btn, border_radius=8)
                pygame.draw.rect(screen, (110, 45, 45), btn, 2,  border_radius=8)
                tf  = f_med if btn != btn_quit else f_sm
                tt  = tf.render(text, True, (255, 255, 255))
                screen.blit(tt, tt.get_rect(center=btn.center))

            pygame.display.flip()

        pygame.quit()
        return result


# ══════════════════════════════════════════════════════════════
#  ТОЧКА ВХОДА
# ══════════════════════════════════════════════════════════════

def main():
    print("=" * 60)
    print("  HORROR LAN — SERVER v3.0")
    print("=" * 60)

    gui     = ModeSelectGUI()
    ai_mode = gui.run()

    if ai_mode is None:
        print("Выход.")
        sys.exit(0)

    mode_str = "AI-монстр" if ai_mode else "Мультиплеер"
    print(f"[SERVER] Режим: {mode_str}")
    print(f"[SERVER] Запуск сервера на порту {PORT}...")

    server = GameServer(ai_mode)
    try:
        server.start()
    except KeyboardInterrupt:
        print("\n[SERVER] Остановлен.")


if __name__ == "__main__":
    main()
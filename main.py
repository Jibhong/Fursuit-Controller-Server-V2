#!/usr/bin/env python3
import os
import sys
import time
import subprocess
import pygame
from multiprocessing import Process, Pipe, set_start_method
import asyncio
import random
import threading

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def remap(f1, f2, value):
    value = max(0.0, min(1.0, value))  # clamp to [0,1]
    return f1 + (f2 - f1) * value

def blink(screen: pygame.Surface, factor: float = 0.5):
    w = screen.get_width()
    h = screen.get_height()
    
    pygame.draw.rect(screen, "black", pygame.Rect(-w/2,remap(-h*1.2, -h*2.4, factor),w*2,h*2.4))

# Child process: ensure DISPLAY is set, create its own pygame window and listen for commands.
def run_display(conn, x, y, w, h, name="display"):
    # Defensive: ensure the child has the correct X display
    os.environ.setdefault("DISPLAY", ":0")

    pygame.init()
    pygame.display.init()
    screen = pygame.display.set_mode((w, h), pygame.NOFRAME | pygame.DOUBLEBUF | pygame.HWSURFACE)
    pygame.display.set_caption(f"{name}")

    # Move the window to (x, y) using xdotool (requires xdotool installed)
    try:
        wid = pygame.display.get_wm_info().get("window")
        # Some builds return bytes; make sure it's a str/int
        wid = int(wid)
        subprocess.run(["xdotool", "windowmove", str(wid), str(x), str(y)], check=False)
    except Exception as e:
        print(f"[{name}] failed to move window: {e}", file=sys.stderr)

    clock = pygame.time.Clock()
    running = True

    # Colors
    color_bg = (255, 255, 255)
    color_highlight = (255, 255, 255)
    color_eye = (0, 0, 0)

    # Eye parameters
    eye_size=(h, h)
    eye_radius = min(eye_size)/2 * 1.2
    pupil_radius = eye_radius / 1.2
    pupil_pos_x = eye_size[0]/2 + 150 # offset
    pupil_pos_y = eye_size[1]/2

    # Blinking
    blinkTime = 0.2
    blinkLeft = -blinkTime

    while running:
        # Input
        keys = pygame.key.get_pressed()
        if keys[pygame.K_LCTRL] or keys[pygame.K_RCTRL]:
            if keys[pygame.K_c]:
                running = False

        # Logic
        deltaTime = clock.tick(60) / 1000  # convert milliseconds to seconds
        blinkLeft -= deltaTime
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
    
        # Commands
        if conn.poll():
            msg = conn.recv()
            if msg == "quit":
                running = False
            elif msg == "blink":
                blinkLeft = blinkTime
            elif isinstance(msg, tuple) and msg[0] == "bg":
                color_bg = msg[1]
            elif isinstance(msg, tuple) and msg[0] == "rect":
                color_eye = msg[1]


        screen.fill(pygame.Color(color_bg))
        # pygame.draw.circle(screen, color_eye, (pupil_pos_x, pupil_pos_y), eye_radius)  # sclera
        # pygame.draw.circle(screen, color_highlight, (pupil_pos_x, pupil_pos_y), pupil_radius)      # pupil

        iris_img = pygame.image.load(os.path.join(BASE_DIR,"iris.png")).convert_alpha()
        iris_size = eye_radius * 2
        iris_img = pygame.transform.smoothscale(iris_img, (iris_size, iris_size))
        iris_rect = iris_img.get_rect(center=(pupil_pos_x, pupil_pos_y))
        screen.blit(iris_img, iris_rect)


        if (blinkLeft > -blinkTime):
            blink(screen, abs(blinkLeft)/blinkTime)

        if (name == "RIGHT"):
            flipped = pygame.transform.flip(screen, False, True)  # (flip_x, flip_y)
            screen.blit(flipped, (0, 0))

        pygame.display.update()

    pygame.quit()
    conn.close()


def Blink():
    while True:
        parent1.send("blink")
        parent2.send("blink")
        time.sleep(random.uniform(2,3))

if __name__ == "__main__":
    # Force 'fork' start method on Linux so child inherits X connection
    try:
        set_start_method("fork")
    except RuntimeError:
        # start method already set; ignore
        pass
    except ValueError:
        # error@window
        pass

    print("Python:", sys.version.splitlines()[0])
    print("Pygame:", pygame.version.vernum)
    print("Launching two windows...")

    # Create pipes for command/control
    parent1, child1 = Pipe()
    parent2, child2 = Pipe()

    # Adjust coordinates/resolutions for your monitors
    p_left = Process(target=run_display, args=(child1, 0, 0, 800, 480, "RIGHT"))
    # p_left = Process(target=print, args=("a"))
    p_right = Process(target=run_display, args=(child2, 800, 0, 800, 480, "LEFT"))

    p_left.start()
    p_right.start()

    time.sleep(1)

    # Give them a moment to create windows
    parent1.send("blink")
    parent2.send("blink")
    # Blink()
    threading.Thread(target=Blink, daemon=True).start()
    while True:
        if not p_left.is_alive():
            print("Left process died, terminating right...")
            parent2.send("quit")
            break
        if not p_right.is_alive():
            print("Right process died, terminating left...")
            parent1.send("quit")
            break
    p_left.join()
    p_right.join()
    print("Done.")

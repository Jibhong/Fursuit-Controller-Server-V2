#!/usr/bin/env python3
import os
import sys
import time
import subprocess
import pygame
from multiprocessing import Process, Pipe, set_start_method

def blink(screen: pygame.Surface, factor: float = 0.5):
    w = screen.get_width()
    h = screen.get_height()
    pygame.draw.rect(screen, "black", pygame.Rect(0,0,w,h*factor))

# Child process: ensure DISPLAY is set, create its own pygame window and listen for commands.
def run_display(conn, x, y, w, h, name="display"):
    # Defensive: ensure the child has the correct X display
    os.environ.setdefault("DISPLAY", ":0")

    pygame.init()
    pygame.display.init()
    screen = pygame.display.set_mode((w, h), pygame.NOFRAME)
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
    eye_radius = min(eye_size)//2 - 10
    pupil_radius = eye_radius // 3
    pupil_pos_x = eye_size[0]//2
    pupil_pos_y = eye_size[1]//2

    # Blinking
    blinkTime = 1.0
    blinkLeft = 0.0

    while running:
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
        pygame.draw.circle(screen, color_eye, (eye_size[0]//2, eye_size[1]//2), eye_radius)  # sclera
        pygame.draw.circle(screen, color_highlight, (pupil_pos_x, pupil_pos_y), pupil_radius)      # pupil

        if (blinkLeft > 0):
            blink(screen, blinkLeft/blinkTime)

        pygame.display.update()

    pygame.quit()
    conn.close()

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
    p_left = Process(target=run_display,
                     args=(child1, 0, 0, 1920, 1080, "LEFT"))
    p_right = Process(target=run_display,
                      args=(child2, 1920, 0, 1280, 720, "RIGHT"))

    p_left.start()
    p_right.start()

    time.sleep(1)

    # Give them a moment to create windows
    parent1.send("blink")
    parent2.send("blink")

    time.sleep(3)

    # Quit both
    parent1.send("quit")
    parent2.send("quit")

    p_left.join()
    p_right.join()
    print("Done.")

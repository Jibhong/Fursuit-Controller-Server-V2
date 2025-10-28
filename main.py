#!/usr/bin/env python3
import os
import sys
import time
import subprocess
import pygame
from multiprocessing import Process, Pipe, set_start_method

# Child process: ensure DISPLAY is set, create its own pygame window and listen for commands.
def run_display(conn, x, y, w, h, color_bg, color_rect, name="display"):
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
    rect_x = 0
    rect_y = h // 2 - 25
    rect_w, rect_h = 50, 50
    speed = 6
    running = True

    while running:
        # read commands from parent (non-blocking)
        if conn.poll():
            msg = conn.recv()
            if msg == "quit":
                running = False
            elif msg == "reverse":
                speed = -speed
            elif isinstance(msg, tuple) and msg[0] == "bg":
                color_bg = msg[1]
            elif isinstance(msg, tuple) and msg[0] == "rect":
                color_rect = msg[1]

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        screen.fill(pygame.Color(color_bg))
        pygame.draw.rect(screen, pygame.Color(color_rect), (rect_x, rect_y, rect_w, rect_h))
        rect_x += speed
        if rect_x + rect_w > w or rect_x < 0:
            speed = -speed

        pygame.display.update()
        clock.tick(60)

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
                     args=(child1, 0, 0, 1920, 1080, "black", "red", "LEFT"))
    p_right = Process(target=run_display,
                      args=(child2, 1920, 0, 1280, 720, "navy", "yellow", "RIGHT"))

    p_left.start()
    p_right.start()

    # Give them a moment to create windows
    time.sleep(1.0)

    # Example control sequence
    parent1.send("reverse")               # reverse left rect
    time.sleep(0.8)
    parent2.send(("bg", "darkgreen"))     # change right background
    time.sleep(0.8)
    parent1.send(("rect", "orange"))      # change left rect color
    time.sleep(1.2)

    parent1.send("reverse") 
    parent2.send("reverse") 
    
    time.sleep(1.2)

    # Quit both
    parent1.send("quit")
    parent2.send("quit")

    p_left.join()
    p_right.join()
    print("Done.")

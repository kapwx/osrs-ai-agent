import time
import random
import math
import sys
import requests
import pyautogui

# Safety fail-safe: slamming mouse to upper-left corner (0, 0) immediately kills the script
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.05

try:
    import pygetwindow as gw
except ImportError:
    gw = None

BRAIN_API_URL = "http://localhost:8000/api/action"

def is_runelite_active() -> bool:
    """Verifies that the RuneLite game window is currently focused to prevent misclicks."""
    if not gw:
        return True
    try:
        active_window = gw.getActiveWindow()
        if active_window and "runelite" in active_window.title.lower():
            return True
        return False
    except Exception:
        return True

def human_bezier_move(target_x: int, target_y: int, duration: float = 0.4):
    """
    Moves the mouse to (target_x, target_y) along a natural cubic Bézier curve
    with random overshoot and speed variation to simulate realistic human input.
    """
    start_x, start_y = pyautogui.position()
    
    # Random deviation control points
    dist = math.hypot(target_x - start_x, target_y - start_y)
    deviation = min(max(dist * 0.2, 10), 100)
    
    ctrl1_x = start_x + (target_x - start_x) * 0.25 + random.uniform(-deviation, deviation)
    ctrl1_y = start_y + (target_y - start_y) * 0.25 + random.uniform(-deviation, deviation)
    
    ctrl2_x = start_x + (target_x - start_x) * 0.75 + random.uniform(-deviation, deviation)
    ctrl2_y = start_y + (target_y - start_y) * 0.75 + random.uniform(-deviation, deviation)

    steps = int(max(20, duration * 60))
    for i in range(steps + 1):
        t = i / steps
        # Cubic Bézier formula: B(t) = (1-t)^3*P0 + 3(1-t)^2*t*P1 + 3(1-t)*t^2*P2 + t^3*P3
        cx = (1 - t)**3 * start_x + 3 * (1 - t)**2 * t * ctrl1_x + 3 * (1 - t) * t**2 * ctrl2_x + t**3 * target_x
        cy = (1 - t)**3 * start_y + 3 * (1 - t)**2 * t * ctrl1_y + 3 * (1 - t) * t**2 * ctrl2_y
        pyautogui.moveTo(int(cx), int(cy))
        time.sleep(duration / steps)

def perform_human_click(x: int, y: int, button: str = "left"):
    """Moves to coordinate with human-like curve and performs a click with natural hold duration."""
    # Add minor pixel jitter to avoid clicking the exact same pixel
    jitter_x = x + random.randint(-3, 3)
    jitter_y = y + random.randint(-3, 3)
    
    move_duration = random.uniform(0.25, 0.45)
    human_bezier_move(jitter_x, jitter_y, duration=move_duration)
    
    pyautogui.mouseDown(button=button)
    time.sleep(random.uniform(0.06, 0.12))  # natural human click down duration
    pyautogui.mouseUp(button=button)

def execute_action(action: dict):
    action_type = action.get("action_type", "IDLE")
    reasoning = action.get("reasoning", "")
    target_name = action.get("target_name", "N/A")

    print(f"\n[EXECUTOR] Received Action: {action_type} | Target: {target_name}")
    print(f"[REASON] {reasoning}")

    if not is_runelite_active():
        print("[WARNING] RuneLite is not the focused window! Skipping physical input.")
        return

    if action_type == "IDLE":
        # Nothing to do
        pass
    elif action_type in ["ATTACK_NPC", "CLICK_OBJECT"]:
        coords = action.get("coordinates")
        if coords and "x" in coords and "y" in coords:
            print(f"[EXECUTOR] Clicking target at ({coords['x']}, {coords['y']})")
            perform_human_click(coords["x"], coords["y"])
        else:
            print(f"[EXECUTOR] Screen coordinates not provided for {target_name}. Awaiting targeted click data.")
    elif action_type == "EAT_FOOD":
        print(f"[EXECUTOR] Emergency Action: Eating food ({target_name})")
        # In a complete setup, coordinates for inventory slot containing food are mapped here
    elif action_type == "WALK_TO":
        coords = action.get("coordinates")
        if coords:
            print(f"[EXECUTOR] Walking to map coordinates: {coords}")

def main():
    print("=" * 60)
    print(" OSRS AI Agent - Humanized Action Executor")
    print(" Fail-safe: Slam mouse cursor into upper-left corner (0,0) to halt")
    print("=" * 60)

    last_reasoning = ""
    while True:
        try:
            resp = requests.get(BRAIN_API_URL, timeout=3)
            if resp.status_code == 200:
                action = resp.json()
                reasoning = action.get("reasoning", "")
                if reasoning != last_reasoning:
                    execute_action(action)
                    last_reasoning = reasoning
        except requests.exceptions.RequestException:
            # Backend server might be restarting or loading
            pass
        except Exception as e:
            print(f"[ERROR] Execution exception: {e}")

        # Polling tick interval
        time.sleep(random.uniform(0.8, 1.4))

if __name__ == "__main__":
    main()

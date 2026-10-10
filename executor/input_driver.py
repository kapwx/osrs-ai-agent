import time
import random
import math
import sys
import ctypes
from ctypes import wintypes
import requests

# Windows API Constants for Background Input
WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
MK_LBUTTON = 0x0001
VK_SPACE = 0x20

user32 = ctypes.windll.user32
WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

BRAIN_API_URL = "http://localhost:8000/api/action"

def find_runelite_hwnds():
    """
    Finds the RuneLite main top-level window and its internal Canvas rendering surface.
    Returns (top_hwnd, canvas_hwnd)
    """
    top_hwnds = []

    def enum_top(hwnd, lParam):
        if user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buff = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buff, length + 1)
                title = buff.value.lower()
                if "runelite" in title:
                    top_hwnds.append(hwnd)
        return True

    user32.EnumWindows(WNDENUMPROC(enum_top), 0)
    if not top_hwnds:
        return None, None

    top_hwnd = top_hwnds[0]
    canvas_hwnds = []

    def enum_child(hwnd, lParam):
        class_buff = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, class_buff, 256)
        if "canvas" in class_buff.value.lower():
            canvas_hwnds.append(hwnd)
        return True

    user32.EnumChildWindows(top_hwnd, WNDENUMPROC(enum_child), 0)
    canvas_hwnd = canvas_hwnds[0] if canvas_hwnds else top_hwnd
    return top_hwnd, canvas_hwnd

def post_background_click(hwnd, x: int, y: int):
    """
    Sends a mouse click to RuneLite via Windows PostMessage.
    Runs silently in the background:
    - Works even when RuneLite is in Alt+Tab / unfocused.
    - Does NOT steal active window focus.
    - Does NOT move the user's physical mouse cursor.
    """
    jitter_x = int(x + random.randint(-2, 2))
    jitter_y = int(y + random.randint(-2, 2))

    lParam = ((jitter_y & 0xFFFF) << 16) | (jitter_x & 0xFFFF)

    # 1. Hover / MouseMove
    user32.PostMessageW(hwnd, WM_MOUSEMOVE, 0, lParam)
    time.sleep(random.uniform(0.03, 0.06))

    # 2. Left Button Down
    user32.PostMessageW(hwnd, WM_LBUTTONDOWN, MK_LBUTTON, lParam)
    time.sleep(random.uniform(0.06, 0.12))

    # 3. Left Button Up
    user32.PostMessageW(hwnd, WM_LBUTTONUP, 0, lParam)

def post_background_space(hwnd):
    """
    Sends Spacebar key to RuneLite in the background to progress dialogues.
    """
    user32.PostMessageW(hwnd, WM_KEYDOWN, VK_SPACE, 0)
    time.sleep(random.uniform(0.05, 0.09))
    user32.PostMessageW(hwnd, WM_KEYUP, VK_SPACE, 0)

def execute_action(action: dict, top_hwnd, canvas_hwnd):
    action_type = action.get("action_type", "IDLE")
    reasoning = action.get("reasoning", "")
    target_name = action.get("target_name", "N/A")

    print(f"\n[EXECUTOR] Action: {action_type} | Target: {target_name}")
    print(f"[REASON] {reasoning}")

    if action_type == "IDLE":
        return

    target_hwnd = canvas_hwnd or top_hwnd

    # 1. Dialogue progression (Tutorial Island & Quest Dialogues)
    if action_type == "CONTINUE_DIALOGUE":
        print(f"[EXECUTOR] Progressing dialogue in background (Spacebar)")
        post_background_space(target_hwnd)
        return

    # 2. Targeted Interactions (Walk, Attack, Talk, Click)
    if action_type in ["WALK_TO", "ATTACK_NPC", "TALK_TO_NPC", "CLICK_OBJECT", "EAT_FOOD"]:
        cx = action.get("canvas_x")
        cy = action.get("canvas_y")

        if cx is not None and cy is not None:
            print(f"[EXECUTOR] Background Click at Canvas ({cx}, {cy}) for '{target_name or action_type}'")
            post_background_click(target_hwnd, cx, cy)
        else:
            print(f"[EXECUTOR] Coordinates not provided for '{target_name}'. Waiting for next telemetry projection.")

def main():
    print("=" * 65)
    print(" OSRS AI Agent - Background Action Executor (Alt+Tab Ready)")
    print(" Clicks are sent directly to RuneLite's window in the background.")
    print(" Your physical mouse will NOT move and focus will NOT be stolen.")
    print("=" * 65)

    last_reasoning = ""
    top_hwnd = None
    canvas_hwnd = None

    while True:
        try:
            # Refresh window handle if lost
            if not top_hwnd or not user32.IsWindow(top_hwnd):
                top_hwnd, canvas_hwnd = find_runelite_hwnds()
                if top_hwnd:
                    print(f"\n[RUNELITE CONNECTED] Top HWND: {top_hwnd}, Canvas HWND: {canvas_hwnd}")
                else:
                    print("[WAITING] Waiting for RuneLite window to open...", end="\r")
                    time.sleep(2)
                    continue

            resp = requests.get(BRAIN_API_URL, timeout=3)
            if resp.status_code == 200:
                action = resp.json()
                reasoning = action.get("reasoning", "")
                action_type = action.get("action_type", "IDLE")

                # Dialogue actions can repeat rapidly to advance multiline dialogues
                if action_type == "CONTINUE_DIALOGUE" or reasoning != last_reasoning:
                    execute_action(action, top_hwnd, canvas_hwnd)
                    last_reasoning = reasoning

        except requests.exceptions.RequestException:
            # Server restarting or loading
            pass
        except Exception as e:
            print(f"[ERROR] Execution error: {e}")

        # Polling tick interval
        time.sleep(random.uniform(0.8, 1.2))

if __name__ == "__main__":
    main()

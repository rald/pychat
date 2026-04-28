#!/usr/bin/env python3
import socket, curses, threading, time

HOST, PORT = '192.227.241.244', 14344
MAX_SCROLLBACK = 1024
MAX_INPUT_LENGTH = 512

class UIState:
    def __init__(self, name, room):
        self.name, self.room = name, room
        self.prompt = f"[{room}] {name}> "
        self.latency = 0

def receive_messages(sock, pad, pad_pos, h, w, state):
    while True:
        try:
            raw_data = sock.recv(2048).decode('utf-8')
            if not raw_data: break
            for data in raw_data.split('\n'):
                if not data: continue
                
                # Update Latency
                if data.startswith("PING|"):
                    ts = float(data.split("|")[1])
                    state.latency = int((time.time() - ts) * 1000)
                    sock.send(f"PONG|{ts}\n".encode('utf-8'))
                    continue
                
                # Synchronize UI with Server State (Critical for /nick and /join)
                if data.startswith("NICK_SUCCESS|") or data.startswith("JOIN_SUCCESS|"):
                    val = data.split("|")[1].strip()
                    if data.startswith("NICK"): state.name = val
                    else: state.room = val
                    state.prompt = f"[{state.room}] {state.name}> "
                    continue
                
                # Output to Chat Pad
                if "ENTER_USERNAME" not in data:
                    curr_y, _ = pad.getyx()
                    at_bottom = pad_pos[0] >= curr_y - (h - 4)
                    pad.addstr(f"{data}\n")
                    if at_bottom:
                        new_y, _ = pad.getyx()
                        pad_pos[0] = max(0, new_y - (h - 4))
                    pad.noutrefresh(pad_pos[0], 0, 0, 0, h - 4, w - 1)
        except: break

def get_input(win, state, history, pad, pad_pos, h, w):
    input_str, h_idx, cursor_idx = "", len(history), 0
    win.nodelay(True)
    while True:
        max_view_width = w - len(state.prompt) - 2
        offset = max(0, cursor_idx - max_view_width + 1)
        display_part = input_str[offset : offset + max_view_width]
        
        pad.noutrefresh(pad_pos[0], 0, 0, 0, h - 4, w - 1)
        win.erase(); win.border()
        win.addstr(1, 1, state.prompt + display_part)
        if state.latency > 0: win.addstr(2, w - 10, f" {state.latency}ms ")
        
        win.move(1, len(state.prompt) + (cursor_idx - offset) + 1)
        win.noutrefresh()
        curses.doupdate()
        
        key = win.getch()
        if key == -1: time.sleep(0.01); continue
        
        if key in (10, 13): # ENTER
            if input_str.strip(): history.append(input_str)
            return input_str
        elif key == curses.KEY_LEFT: cursor_idx = max(0, cursor_idx - 1)
        elif key == curses.KEY_RIGHT: cursor_idx = min(len(input_str), cursor_idx + 1)
        elif key == curses.KEY_HOME: cursor_idx = 0
        elif key == curses.KEY_END: cursor_idx = len(input_str)
        elif key == curses.KEY_UP and h_idx > 0:
            h_idx -= 1; input_str = history[h_idx]; cursor_idx = len(input_str)
        elif key == curses.KEY_DOWN:
            if h_idx < len(history) - 1: h_idx += 1; input_str = history[h_idx]
            else: h_idx = len(history); input_str = ""
            cursor_idx = len(input_str)
        elif key in (curses.KEY_BACKSPACE, 127, 8):
            if cursor_idx > 0:
                input_str = input_str[:cursor_idx-1] + input_str[cursor_idx:]
                cursor_idx -= 1
        elif key == curses.KEY_DC: # DELETE
            input_str = input_str[:cursor_idx] + input_str[cursor_idx+1:]
        elif key == curses.KEY_PPAGE: # SCROLL UP
            pad_pos[0] = max(0, pad_pos[0] - (h - 4))
        elif key == curses.KEY_NPAGE: # SCROLL DOWN
            curr_y, _ = pad.getyx()
            pad_pos[0] = min(max(0, curr_y - (h - 4)), pad_pos[0] + (h - 4))
        elif 32 <= key <= 126 and len(input_str) < MAX_INPUT_LENGTH:
            input_str = input_str[:cursor_idx] + chr(key) + input_str[cursor_idx:]
            cursor_idx += 1

def main(stdscr):
    curses.noecho(); stdscr.keypad(True); curses.curs_set(1)
    h, w = stdscr.getmaxyx()
    pad = curses.newpad(MAX_SCROLLBACK, w); pad_pos = [0]
    input_win = curses.newwin(3, w, h - 3, 0); input_win.keypad(True)
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try: sock.connect((HOST, PORT))
    except Exception as e:
        stdscr.addstr(0, 0, f"CONNECTION FAILED: {e}"); stdscr.refresh(); time.sleep(2); return

    # Secure Handshake
    name = ""
    while True:
        data = sock.recv(1024).decode('utf-8').strip()
        if "ENTER_USERNAME" in data:
            input_win.clear(); input_win.border(); input_win.addstr(1, 1, "Username: ")
            curses.echo(); attempt = input_win.getstr(1, 11).decode('utf-8').strip()[:32]
            curses.noecho(); sock.send(f"{attempt}\n".encode('utf-8'))
        elif "ACCEPT_NAME|" in data:
            name = data.split("|")[1].strip(); break
        elif "[!] ERROR" in data:
            input_win.addstr(2, 1, data[:w-2], curses.A_REVERSE); input_win.refresh(); time.sleep(1.5)

    state = UIState(name, "#lobby"); history = []
    threading.Thread(target=receive_messages, args=(sock, pad, pad_pos, h, w, state), daemon=True).start()

    while True:
        msg = get_input(input_win, state, history, pad, pad_pos, h, w)
        if not msg: continue
        
        # Local visual feedback for messages
        if not msg.startswith("/"):
            lbl = f"<{state.room}> <{state.name}>" if state.room.startswith("#") else f"<To {state.room}>"
            pad.addstr(f"{lbl}: {msg}\n")
            cy, _ = pad.getyx(); pad_pos[0] = max(0, cy - (h - 4))
            
        sock.send(f"{msg}\n".encode('utf-8'))
        if msg.startswith("/quit"):
            stdscr.clear(); stdscr.addstr(h//2, (w//2)-10, "Logging out..."); stdscr.refresh(); time.sleep(1); break

if __name__ == "__main__":
    try: curses.wrapper(main)
    except KeyboardInterrupt: pass
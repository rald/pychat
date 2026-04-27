#!/usr/bin/env python3
import socket
import curses
import threading

# Configuration
HOST = '192.227.241.244'
PORT = 14344
MAX_SCROLLBACK = 1024

def receive_messages(sock, pad, pad_pos, h, w):
    """Handles incoming data with intelligent auto-scroll."""
    while True:
        try:
            data = sock.recv(1024).decode('utf-8')
            if data and "ENTER_USERNAME" not in data:
                curr_y, _ = pad.getyx()
                # Check if user is looking at the bottom (threshold for auto-scroll)
                is_at_bottom = pad_pos[0] >= curr_y - (h - 4)
                
                pad.addstr(f"{data}\n")
                
                if is_at_bottom:
                    new_y, _ = pad.getyx()
                    pad_pos[0] = max(0, new_y - (h - 4))
                
                # Keep view within bounds
                pad.refresh(pad_pos[0], 0, 0, 0, h - 4, w - 1)
        except:
            break

def get_input_with_history(win, prompt, history, pad, pad_pos, h, w):
    win.clear()
    win.border()
    win.addstr(1, 1, prompt)
    win.refresh()
    
    input_str = ""
    h_idx = len(history)
    
    while True:
        pad.refresh(pad_pos[0], 0, 0, 0, h - 4, w - 1)
        key = win.getch()
        
        if key in (curses.KEY_ENTER, 10, 13):
            if input_str.strip(): history.append(input_str)
            return input_str
        
        # --- Scrolling ---
        elif key == curses.KEY_PPAGE: 
            pad_pos[0] = max(0, pad_pos[0] - (h - 4))
        elif key == curses.KEY_NPAGE: 
            curr_y, _ = pad.getyx()
            pad_pos[0] = min(curr_y - (h - 4), pad_pos[0] + (h - 4))
            if pad_pos[0] < 0: pad_pos[0] = 0

        # --- History ---
        elif key == curses.KEY_UP and h_idx > 0:
            h_idx -= 1
            input_str = history[h_idx]
        elif key == curses.KEY_DOWN:
            if h_idx < len(history) - 1:
                h_idx += 1
                input_str = history[h_idx]
            else:
                h_idx = len(history)
                input_str = ""
        
        # --- Editing ---
        elif key in (curses.KEY_BACKSPACE, 127, 8):
            input_str = input_str[:-1]
        elif 32 <= key <= 126:
            input_str += chr(key)

        win.clear()
        win.border()
        win.addstr(1, 1, prompt + input_str)
        win.refresh()

def main(stdscr):
    curses.noecho()
    stdscr.keypad(True)
    h, w = stdscr.getmaxyx()
    
    # 1024 line scrollback pad
    pad = curses.newpad(MAX_SCROLLBACK, w)
    pad.scrollok(True)
    pad_pos = [0] 
    
    input_win = curses.newwin(3, w, h - 3, 0)
    input_win.keypad(True)
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((HOST, PORT))
    except:
        return

    history = []
    my_name = ""
    active_room = "#general"

    # --- Handshake ---
    while True:
        data = sock.recv(1024).decode('utf-8')
        if "ENTER_USERNAME" in data:
            curses.echo()
            input_win.clear()
            input_win.border()
            input_win.addstr(1, 1, "Username: ")
            my_name = input_win.getstr(1, 11).decode('utf-8').strip()
            sock.send(my_name.encode('utf-8'))
            curses.noecho()
        elif "ACCEPT_NAME" in data:
            my_name = data.split("|")[1]
            break

    threading.Thread(target=receive_messages, args=(sock, pad, pad_pos, h, w), daemon=True).start()

    while True:
        prompt = f"[{active_room}] {my_name}> "
        msg = get_input_with_history(input_win, prompt, history, pad, pad_pos, h, w)
        if not msg: continue
        
        parts = msg.split()
        cmd = parts[0].lower()

        if cmd == '/quit':
            sock.send(msg.encode('utf-8'))
            break
        
        # Update local UI state
        if cmd == '/join' and len(parts) > 1:
            active_room = parts[1]
        elif cmd == '/part' and len(parts) > 1:
            if parts[1] == active_room: active_room = "#general"
        elif cmd == '/nick' and len(parts) > 1:
            my_name = parts[1]

        # Local echo to pad
        if not msg.startswith("/"):
            label = f"<To {active_room}>" if not active_room.startswith("#") else f"<{active_room}> <{my_name}>"
            pad.addstr(f"{label}: {msg}\n")
            curr_y, _ = pad.getyx()
            pad_pos[0] = max(0, curr_y - (h - 4))
            pad.refresh(pad_pos[0], 0, 0, 0, h - 4, w - 1)
        
        sock.send(msg.encode('utf-8'))

if __name__ == "__main__":
    try:
        curses.wrapper(main)
    except:
        pass
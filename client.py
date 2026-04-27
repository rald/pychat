#!/usr/bin/env python3
import socket, curses, threading

HOST, PORT = '192.227.241.244', 14344
MAX_SCROLLBACK = 1024

class UIState:
    def __init__(self, name, room):
        self.name, self.room = name, room
        self.prompt = f"[{room}] {name}> "

def receive_messages(sock, pad, pad_pos, h, w, input_win, state, current_input):
    while True:
        try:
            raw_data = sock.recv(1024).decode('utf-8')
            if not raw_data: break
            
            # Split by newline in case multiple messages arrive at once
            for data in raw_data.split('\n'):
                if not data: continue
                
                if data.startswith("NICK_SUCCESS|") or data.startswith("JOIN_SUCCESS|"):
                    val = data.split("|")[1].strip()
                    if data.startswith("NICK"): state.name = val
                    else: state.room = val
                    state.prompt = f"[{state.room}] {state.name}> "
                    input_win.clear(); input_win.border()
                    input_win.addstr(1, 1, state.prompt + current_input[0])
                    input_win.refresh()
                    continue
                
                if "ENTER_USERNAME" not in data:
                    curr_y, _ = pad.getyx()
                    at_bottom = pad_pos[0] >= curr_y - (h - 4)
                    
                    # Cleanly add the message with exactly one newline
                    pad.addstr(f"{data}\n")
                    
                    if at_bottom:
                        new_y, _ = pad.getyx()
                        pad_pos[0] = max(0, new_y - (h - 4))
                    
                    pad.refresh(pad_pos[0], 0, 0, 0, h - 4, w - 1)
                    input_win.addstr(1, 1, state.prompt + current_input[0])
                    input_win.refresh()
        except: break

def get_input_with_history(win, state, history, pad, pad_pos, h, w, current_input):
    win.clear(); win.border(); win.addstr(1, 1, state.prompt); win.refresh()
    input_str, h_idx = "", len(history)
    
    while True:
        current_input[0] = input_str
        pad.refresh(pad_pos[0], 0, 0, 0, h - 4, w - 1)
        win.move(1, len(state.prompt) + len(input_str) + 1)
        
        key = win.getch()
        if key in (10, 13):
            if input_str.strip(): history.append(input_str)
            res = input_str; input_str = ""; current_input[0] = ""; return res
        elif key == curses.KEY_PPAGE:
            pad_pos[0] = max(0, pad_pos[0] - (h - 4))
        elif key == curses.KEY_NPAGE:
            cy, _ = pad.getyx()
            pad_pos[0] = min(max(0, cy - (h - 4)), pad_pos[0] + (h - 4))
        elif key == curses.KEY_UP and h_idx > 0:
            h_idx -= 1; input_str = history[h_idx]
        elif key == curses.KEY_DOWN:
            if h_idx < len(history)-1: h_idx += 1; input_str = history[h_idx]
            else: h_idx = len(history); input_str = ""
        elif key in (curses.KEY_BACKSPACE, 127, 8):
            input_str = input_str[:-1]
        elif 32 <= key <= 126:
            input_str += chr(key)

        win.clear(); win.border(); win.addstr(1, 1, state.prompt + input_str); win.refresh()

def main(stdscr):
    curses.noecho(); stdscr.keypad(True)
    h, w = stdscr.getmaxyx()
    pad = curses.newpad(MAX_SCROLLBACK, w); pad.scrollok(True)
    pad_pos, current_input = [0], [""]
    input_win = curses.newwin(3, w, h - 3, 0); input_win.keypad(True)
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try: sock.connect((HOST, PORT))
    except: return

    while True:
        data = sock.recv(1024).decode('utf-8')
        if "ENTER_USERNAME" in data:
            curses.echo(); input_win.clear(); input_win.border(); input_win.addstr(1, 1, "Username: ")
            name = input_win.getstr(1, 11).decode('utf-8').strip()
            sock.send(f"{name}\n".encode('utf-8')); curses.noecho()
        elif "ACCEPT_NAME" in data:
            name = data.split("|")[1].strip(); break

    state = UIState(name, "#lobby"); history = []
    threading.Thread(target=receive_messages, args=(sock, pad, pad_pos, h, w, input_win, state, current_input), daemon=True).start()

    while True:
        msg = get_input_with_history(input_win, state, history, pad, pad_pos, h, w, current_input)
        if not msg: continue
        if not msg.startswith("/"):
            lbl = f"<{state.room}> <{state.name}>" if state.room.startswith("#") else f"<To {state.room}>"
            pad.addstr(f"{lbl}: {msg}\n")
            cy, _ = pad.getyx(); pad_pos[0] = max(0, cy - (h - 4))
        sock.send(f"{msg}\n".encode('utf-8'))
        if msg.startswith("/quit"): break

if __name__ == "__main__":
    try: curses.wrapper(main)
    except: pass
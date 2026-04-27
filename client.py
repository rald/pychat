import socket
import curses
import threading

HOST = '192.227.241.244'
PORT = 14344

def receive_messages(sock, msg_win):
    while True:
        try:
            data = sock.recv(1024).decode('utf-8')
            if data and "ENTER_USERNAME" not in data:
                msg_win.scrollok(True)
                msg_win.addstr(f"{data}\n")
                msg_win.refresh()
        except: break

def get_input_with_history(win, prompt, history, my_name, active_room):
    """Custom input handler supporting Up/Down arrow keys for history."""
    win.clear()
    win.border()
    win.addstr(1, 1, prompt)
    win.refresh()
    
    input_str = ""
    history_idx = len(history)
    
    while True:
        key = win.getch()
        
        if key in (curses.KEY_ENTER, 10, 13): # Enter keys
            if input_str.strip():
                history.append(input_str)
            return input_str

        elif key == curses.KEY_UP:
            if history_idx > 0:
                history_idx -= 1
                input_str = history[history_idx]
        
        elif key == curses.KEY_DOWN:
            if history_idx < len(history) - 1:
                history_idx += 1
                input_str = history[history_idx]
            else:
                history_idx = len(history)
                input_str = ""

        elif key in (curses.KEY_BACKSPACE, 127, 8):
            input_str = input_str[:-1]

        elif 32 <= key <= 126: # Printable characters
            input_str += chr(key)

        # Redraw the input line
        win.clear()
        win.border()
        win.addstr(1, 1, prompt + input_str)
        win.refresh()

def main(stdscr):
    curses.noecho() # Disable automatic echo for custom handler
    stdscr.keypad(True)
    h, w = stdscr.getmaxyx()
    msg_win = curses.newwin(h - 3, w, 0, 0)
    input_win = curses.newwin(3, w, h - 3, 0)
    input_win.keypad(True)
    msg_win.scrollok(True)
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((HOST, PORT))

    command_history = []
    my_name = ""
    
    # --- Handshake ---
    while True:
        data = sock.recv(1024).decode('utf-8')
        if "ENTER_USERNAME" in data:
            # Re-enable echo just for initial name entry
            curses.echo()
            input_win.clear()
            input_win.border()
            input_win.addstr(1, 1, "Username: ")
            input_win.refresh()
            my_name = input_win.getstr(1, 11).decode('utf-8')
            sock.send(my_name.encode('utf-8'))
            curses.noecho()
        elif "ACCEPT_NAME" in data:
            my_name = data.split("|")[1]
            break
        else:
            msg_win.addstr(f"{data}\n")
            msg_win.refresh()

    threading.Thread(target=receive_messages, args=(sock, msg_win), daemon=True).start()

    active_room = "#general"
    while True:
        prompt = f"[{active_room}] {my_name}> "
        msg = get_input_with_history(input_win, prompt, command_history, my_name, active_room)
        
        if not msg: continue
        if msg.lower() == '/quit': break
        
        # Local state updates
        if msg.startswith("/nick "):
            parts = msg.split(" ", 1)
            if len(parts) > 1:
                new_nick = parts[1].strip()
                if len(new_nick) <= 32: my_name = new_nick 
        elif msg.startswith("/join "):
            active_room = msg.split(" ", 1)[1].strip()
        elif msg.startswith("/part "):
            target = msg.split(" ", 1)[1].strip()
            if target == active_room: active_room = "#general"
        
        # Local echo
        if not msg.startswith("/"):
            if not active_room.startswith("#"):
                msg_win.addstr(f"<To {active_room}>: {msg}\n")
            else:
                msg_win.addstr(f"<{active_room}> <{my_name}>: {msg}\n")
            msg_win.refresh()
        
        sock.send(msg.encode('utf-8'))

if __name__ == "__main__":
    try: curses.wrapper(main)
    except KeyboardInterrupt: pass
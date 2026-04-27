import socket
import curses
import threading

# Updated Network Config
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
        except:
            break

def main(stdscr):
    curses.echo()
    h, w = stdscr.getmaxyx()
    msg_win = curses.newwin(h - 3, w, 0, 0)
    input_win = curses.newwin(3, w, h - 3, 0)
    msg_win.scrollok(True)
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # Connecting to your specific IP
    sock.connect((HOST, PORT))

    my_name = ""
    while True:
        data = sock.recv(1024).decode('utf-8')
        if "ENTER_USERNAME" in data:
            input_win.clear()
            input_win.border()
            input_win.addstr(1, 1, "Select Username: ")
            input_win.refresh()
            name_input = input_win.getstr(1, 17).decode('utf-8')
            sock.send(name_input.encode('utf-8'))
        elif "ACCEPT_NAME" in data:
            my_name = data.split("|")[1]
            break
        else:
            msg_win.addstr(f"{data}\n")
            msg_win.refresh()

    threading.Thread(target=receive_messages, args=(sock, msg_win), daemon=True).start()

    active_room = "general"
    while True:
        input_win.clear()
        input_win.border()
        prompt = f"[{active_room}] {my_name}> "
        input_win.addstr(1, 1, prompt)
        input_win.refresh()
        
        msg = input_win.getstr(1, len(prompt) + 1).decode('utf-8')
        if not msg: continue
        if msg.lower() == '/quit': break
        
        if msg.startswith("/nick "):
            new_nick = msg.split(" ", 1)[1].strip()
            if new_nick: my_name = new_nick 
        elif msg.startswith("/join "):
            active_room = msg.split(" ", 1)[1].strip()
        elif msg.startswith("/part "):
            parts = msg.split(" ", 1)
            if len(parts) > 1 and parts[1].strip() == active_room:
                active_room = "general" 
        
        if not msg.startswith("/"):
            msg_win.addstr(f"<{active_room}> <{my_name}>: {msg}\n")
            msg_win.refresh()
        
        sock.send(msg.encode('utf-8'))

if __name__ == "__main__":
    try:
        curses.wrapper(main)
    except KeyboardInterrupt:
        pass
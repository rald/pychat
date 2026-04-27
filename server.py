#!/usr/bin/env python3

import socket
import threading
import re

# Configuration
HOST = '192.227.241.244'
PORT = 14344
clients = {} 

def is_valid_identifier(name):
    return 1 <= len(name) <= 32 and re.match(r"^[A-Za-z0-9_]+$", name)

def broadcast(message, room, sender_sock):
    for sock, info in clients.items():
        if room in info["rooms"] and sock != sender_sock:
            try:
                sock.send(message.encode('utf-8'))
            except:
                pass

def handle_client(conn, addr):
    try:
        # --- Handshake ---
        while True:
            conn.send("ENTER_USERNAME".encode('utf-8'))
            name = conn.recv(1024).decode('utf-8').strip()
            if is_valid_identifier(name) and not any(i['name'].lower() == name.lower() for i in clients.values()):
                clients[conn] = {"name": name, "rooms": {"#general"}, "active_room": "#general"}
                conn.send(f"ACCEPT_NAME|{name}".encode('utf-8'))
                broadcast(f"--- {name} joined #general ---", "#general", conn)
                break
            conn.send("--- Error: Invalid or taken name ---\n".encode('utf-8'))

        while True:
            data = conn.recv(1024).decode('utf-8')
            if not data: break
            
            # --- Command: Quit ---
            if data.startswith("/quit"):
                reason = "Client Quit"
                parts = data.split(" ", 1)
                if len(parts) > 1:
                    reason = parts[1].strip()
                # Loop will break and trigger the 'finally' block for broadcasting
                break 

            # --- Command: Help ---
            elif data == "/help":
                help_text = (
                    "\n--- Commands ---\n"
                    "/nick <name>      - Change name (A-Z, 0-9, _, max 32)\n"
                    "/join #<chan>     - Join channel\n"
                    "/join <user>      - Private chat\n"
                    "/part #<chan>     - Leave channel\n"
                    "/list             - List #channels\n"
                    "/names #<chan>    - List users in channel\n"
                    "/quit [msg]       - Exit with optional message\n"
                    "Scrollback: Use PGUP/PGDN\n"
                    "History: Use UP/DOWN arrows\n"
                )
                conn.send(help_text.encode('utf-8'))

            # ... [Other commands: /nick, /join, /part, /list, /names same as before] ...
            
            elif data.startswith("/join "):
                # Logic for /join
                target = data.split(" ", 1)[1].strip()
                if target.startswith("#"):
                    if is_valid_identifier(target[1:]):
                        clients[conn]["rooms"].add(target)
                        clients[conn]["active_room"] = target
                        broadcast(f"--- {clients[conn]['name']} joined {target} ---", target, conn)
                else:
                    clients[conn]["active_room"] = target # Focus for PM

            else:
                # Regular messaging
                active = clients[conn]["active_room"]
                my_name = clients[conn]["name"]
                if active.startswith("#"):
                    broadcast(f"<{active}> <{my_name}>: {data}", active, conn)
                else:
                    # Private Message logic
                    priv_room = f"priv_{min(my_name, active)}_{max(my_name, active)}"
                    for s, info in clients.items():
                        if info['name'] == active: info['rooms'].add(priv_room)
                    broadcast(f"<PM from {my_name}>: {data}", priv_room, conn)

    except: pass
    finally:
        # Broadcast departure to all joined rooms
        if conn in clients:
            user_info = clients[conn]
            # Use 'reason' if defined by /quit, else default to Disconnected
            quit_msg = locals().get('reason', 'Disconnected')
            for room in user_info["rooms"]:
                broadcast(f"--- {user_info['name']} quit ({quit_msg}) ---", room, conn)
            del clients[conn]
        conn.close()

def start_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen()
    print(f"Server live on {HOST}:{PORT}")
    while True:
        conn, addr = server.accept()
        threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()

if __name__ == "__main__":
    start_server()

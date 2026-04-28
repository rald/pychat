#!/usr/bin/env python3
import socket, threading, re, time

# Updated to your specific IP
HOST, PORT = '192.227.241.244', 14344
TIMEOUT_LIMIT = 60
clients = {}

HELP_TEXT = """
============================================================
                 BIBLY CHAT - COMMAND LIST
============================================================
/join <#room>      - Join or switch to a channel
/join <username>   - Start a private chat with a user
/part [#room]      - Leave current or specified channel
/list              - List all active public channels
/names [#room]     - List users in current or specified room
/nick <new_name>   - Change your display name
/help              - Display this menu
/quit [reason]     - Disconnect from the server

SHORTCUTS:
[UP] / [DOWN]      - Cycle through input history
[LEFT] / [RIGHT]   - Navigate through input text
[HOME] / [END]     - Jump to start/end of input
[PG_UP] / [PG_DN]  - Scroll chat history
============================================================"""

def is_valid_id(name):
    return 1 <= len(name) <= 32 and re.match(r"^[A-Za-z0-9_]+$", name)

def broadcast(msg, room, sender_sock=None):
    formatted_msg = f"{msg}\n".encode('utf-8')
    if not room.startswith("#"):
        target_sock = next((s for s, info in clients.items() if info["name"].lower() == room.lower()), None)
        if target_sock:
            try: target_sock.send(formatted_msg)
            except: pass
            if sender_sock != target_sock:
                try: sender_sock.send(formatted_msg)
                except: pass
        else:
            try: sender_sock.send(f"[!] ERROR: User '{room}' is offline.\n".encode('utf-8'))
            except: pass
        return

    for sock, info in list(clients.items()):
        if room in info["rooms"] and sock != sender_sock:
            try: sock.send(formatted_msg)
            except: pass

def heartbeat(conn):
    try:
        while True:
            time.sleep(30)
            if conn not in clients: break
            silence = time.time() - clients[conn]["last_pong"]
            if silence > TIMEOUT_LIMIT:
                conn.close()
                break
            conn.send(f"PING|{time.time()}\n".encode('utf-8'))
    except: pass

def handle_client(conn, addr):
    try:
        # --- Handshake Loop ---
        while True:
            conn.send("ENTER_USERNAME\n".encode('utf-8'))
            raw = conn.recv(1024).decode('utf-8')
            if not raw: return
            name = raw.strip()
            
            if not is_valid_id(name):
                conn.send("[!] ERROR: Name must be 1-32 alphanumeric characters.\n".encode('utf-8'))
                continue
                
            if any(i['name'].lower() == name.lower() for i in clients.values()):
                conn.send(f"[!] ERROR: The name '{name}' is already in use.\n".encode('utf-8'))
                continue
            
            clients[conn] = {
                "name": name, 
                "rooms": {"#lobby"}, 
                "active_room": "#lobby", 
                "last_pong": time.time(),
                "quit_reason": ""
            }
            conn.send(f"ACCEPT_NAME|{name}\n".encode('utf-8'))
            broadcast(f"*** {name} joined #lobby ***", "#lobby")
            threading.Thread(target=heartbeat, args=(conn,), daemon=True).start()
            break

        # --- Main Loop ---
        while True:
            raw = conn.recv(1024).decode('utf-8')
            if not raw: break
            data = raw.strip()
            if not data: continue

            if data.startswith("PONG|"):
                if conn in clients: clients[conn]["last_pong"] = time.time()
                continue
            
            if data.startswith("/"):
                parts = data.split(" ", 1)
                cmd = parts[0].lower()
                arg = parts[1].strip() if len(parts) > 1 else ""
                
                if cmd == "/quit":
                    if arg: clients[conn]["quit_reason"] = f" ({arg})"
                    break
                elif cmd == "/help": 
                    conn.send(f"{HELP_TEXT}\n".encode('utf-8'))
                elif cmd == "/join" and arg:
                    if arg == clients[conn]["name"]:
                        conn.send("[!] ERROR: Cannot PM yourself.\n".encode('utf-8'))
                    else:
                        is_chan = arg.startswith("#")
                        exists = any(i['name'].lower() == arg.lower() for i in clients.values())
                        if is_chan or exists:
                            clients[conn]["rooms"].add(arg)
                            clients[conn]["active_room"] = arg
                            conn.send(f"JOIN_SUCCESS|{arg}\n[i] Switched to {arg}\n".encode('utf-8'))
                            if is_chan: broadcast(f"*** {clients[conn]['name']} joined {arg} ***", arg)
                        else:
                            conn.send(f"[!] ERROR: {arg} not found.\n".encode('utf-8'))
                # ... (Other commands like /list, /names, /part, /nick follow same logic)
            else:
                room, sender = clients[conn]["active_room"], clients[conn]["name"]
                if room.startswith("#"): broadcast(f"<{room}> <{sender}>: {data}", room, conn)
                else: broadcast(f"[PM from {sender}]: {data}", room, conn)

    except: pass
    finally:
        if conn in clients:
            u = clients[conn]
            reason = u.get("quit_reason", "")
            if not reason and (time.time() - u["last_pong"] > TIMEOUT_LIMIT):
                reason = " (timed out)"
            for r in u["rooms"]: 
                if r.startswith("#"): broadcast(f"*** {u['name']} quit{reason} ***", r)
            del clients[conn]
        conn.close()

def start_server():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.bind((HOST, PORT)); s.listen(5)
        print(f"[*] BIBLY Server LIVE on {HOST}:{PORT}")
    except Exception as e: print(f"BIND ERROR: {e}"); return
    while True:
        c, a = s.accept()
        threading.Thread(target=handle_client, args=(c, a), daemon=True).start()

if __name__ == "__main__":
    start_server()
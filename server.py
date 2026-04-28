#!/usr/bin/env python3
import socket, threading, re, time

HOST, PORT = '192.227.241.244', 14344
TIMEOUT_LIMIT = 60
clients = {}

# Full HELP_TEXT restored
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
            if time.time() - clients[conn]["last_pong"] > TIMEOUT_LIMIT:
                conn.close(); break
            conn.send(f"PING|{time.time()}\n".encode('utf-8'))
    except: pass

def handle_client(conn, addr):
    try:
        # --- PHASE 1: HANDSHAKE ---
        while True:
            conn.send("ENTER_USERNAME\n".encode('utf-8'))
            raw = conn.recv(1024).decode('utf-8')
            if not raw: return
            name = raw.strip()
            if is_valid_id(name) and not any(i['name'].lower() == name.lower() for i in clients.values()):
                clients[conn] = {"name": name, "rooms": {"#lobby"}, "active_room": "#lobby", "last_pong": time.time()}
                conn.send(f"ACCEPT_NAME|{name}\n".encode('utf-8'))
                broadcast(f"*** {name} joined #lobby ***", "#lobby")
                threading.Thread(target=heartbeat, args=(conn,), daemon=True).start()
                break
            conn.send("[!] ERROR: Name taken or invalid.\n".encode('utf-8'))

        # --- PHASE 2: COMMAND LOOP ---
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
                
                # RESTORED HELP COMMAND
                if cmd == "/help":
                    conn.send(f"{HELP_TEXT}\n".encode('utf-8'))
                
                elif cmd == "/quit":
                    break
                
                elif cmd == "/list":
                    room_counts = {}
                    for c_info in clients.values():
                        for r in c_info["rooms"]:
                            if r.startswith("#"): room_counts[r] = room_counts.get(r, 0) + 1
                    list_str = "\n".join([f"  {r} ({count} users)" for r, count in room_counts.items()])
                    conn.send(f"--- Active Channels ---\n{list_str if list_str else 'No public channels'}\n-----------------------\n".encode('utf-8'))

                elif cmd == "/names":
                    target = arg if arg else clients[conn]["active_room"]
                    u_list = [i["name"] for i in clients.values() if target in i["rooms"]]
                    if u_list: conn.send(f"--- Users in {target} ({len(u_list)}) ---\n{', '.join(u_list)}\n".encode('utf-8'))
                    else: conn.send(f"[!] ERROR: '{target}' not found.\n".encode('utf-8'))

                elif cmd == "/join" and arg:
                    if arg != clients[conn]["name"]:
                        is_chan = arg.startswith("#")
                        exists = any(i['name'].lower() == arg.lower() for i in clients.values())
                        if is_chan or exists:
                            clients[conn]["rooms"].add(arg); clients[conn]["active_room"] = arg
                            conn.send(f"JOIN_SUCCESS|{arg}\n[i] Switched to {arg}\n".encode('utf-8'))
                            if is_chan: broadcast(f"*** {clients[conn]['name']} joined {arg} ***", arg)
                        else: conn.send(f"[!] ERROR: {arg} not found.\n".encode('utf-8'))
                
                elif cmd == "/part":
                    target = arg if arg else clients[conn]["active_room"]
                    if target == "#lobby": conn.send("[!] ERROR: Cannot leave #lobby.\n".encode('utf-8'))
                    elif target in clients[conn]["rooms"]:
                        clients[conn]["rooms"].remove(target)
                        broadcast(f"*** {clients[conn]['name']} left {target} ***", target)
                        if clients[conn]["active_room"] == target:
                            clients[conn]["active_room"] = "#lobby"
                            conn.send(f"JOIN_SUCCESS|#lobby\n[i] Back in #lobby.\n".encode('utf-8'))
                    else: conn.send(f"[!] ERROR: Not in {target}.\n".encode('utf-8'))

                elif cmd == "/nick" and arg:
                    if is_valid_id(arg) and not any(i['name'].lower() == arg.lower() for i in clients.values()):
                        old = clients[conn]["name"]; clients[conn]["name"] = arg
                        conn.send(f"NICK_SUCCESS|{arg}\n[i] Now known as {arg}.\n".encode('utf-8'))
                        for r in clients[conn]["rooms"]: broadcast(f"*** {old} is now {arg} ***", r)
                    else: conn.send("[!] ERROR: Name taken or invalid.\n".encode('utf-8'))
            else:
                room = clients[conn]["active_room"]
                sender = clients[conn]["name"]
                if room.startswith("#"): broadcast(f"<{room}> <{sender}>: {data}", room, conn)
                else: broadcast(f"[PM from {sender}]: {data}", room, conn)
    except: pass
    finally:
        if conn in clients:
            u = clients[conn]
            for r in u["rooms"]: 
                if r.startswith("#"): broadcast(f"*** {u['name']} quit ***", r)
            del clients[conn]
        conn.close()

def start_server():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.bind((HOST, PORT)); s.listen(5)
        print(f"[*] Server LIVE on {PORT} with /help restored.")
    except Exception as e: print(f"BIND ERROR: {e}"); return
    while True:
        c, a = s.accept()
        threading.Thread(target=handle_client, args=(c, a), daemon=True).start()

if __name__ == "__main__":
    start_server()
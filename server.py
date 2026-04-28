#!/usr/bin/env python3
import socket, threading, re, time

# Use '0.0.0.0' if the specific IP fails to bind on your local machine
HOST, PORT = '192.227.241.244', 14344
TIMEOUT_LIMIT = 60
clients = {} 

HELP_TEXT = """
============================================================
                 BIBLY CHAT - COMMAND LIST
============================================================
/join <#room>      - Join or switch to a channel
/part [#room]      - Leave current or specified channel
/list              - List all active public channels
/names [#room]     - List users in current or specified room
/nick <new_name>   - Change your display name
/help              - Display this menu
/quit [reason]     - Disconnect from the server

SHORTCUTS:
[UP] / [DOWN]      - Cycle through input history
[HOME] / [END]     - Jump to start/end of input
[PG_UP] / [PG_DN]  - Scroll chat history
============================================================"""

def is_valid_id(name):
    return 1 <= len(name) <= 32 and re.match(r"^[A-Za-z0-9_]+$", name)

def broadcast(msg, room, sender_sock=None):
    formatted_msg = f"{msg}\n".encode('utf-8')
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
        # Handshake
        while True:
            conn.send("ENTER_USERNAME\n".encode('utf-8'))
            raw = conn.recv(1024).decode('utf-8')
            if not raw: return
            name = raw.strip()
            if is_valid_id(name) and not any(i['name'].lower() == name.lower() for i in clients.values()):
                clients[conn] = {
                    "name": name, 
                    "rooms": {"#lobby"}, 
                    "active_room": "#lobby", 
                    "last_pong": time.time()
                }
                conn.send(f"ACCEPT_NAME|{name}\n".encode('utf-8'))
                broadcast(f"*** {name} joined #lobby ***", "#lobby")
                threading.Thread(target=heartbeat, args=(conn,), daemon=True).start()
                break
            conn.send("[!] ERROR: Name invalid or taken.\n".encode('utf-8'))

        # Main Loop
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
                    break
                elif cmd == "/help":
                    conn.send(f"{HELP_TEXT}\n".encode('utf-8'))
                elif cmd == "/list":
                    room_counts = {}
                    for c_info in clients.values():
                        for r in c_info["rooms"]:
                            if r.startswith("#"):
                                room_counts[r] = room_counts.get(r, 0) + 1
                    list_str = "\n".join([f"{r} ({count} users)" for r, count in room_counts.items()])
                    conn.send(f"--- Active Channels ---\n{list_str if list_str else 'No public channels'}\n-----------------------\n".encode('utf-8'))
                elif cmd == "/names":
                    target = arg if arg else clients[conn]["active_room"]
                    user_list = [info["name"] for info in clients.values() if target in info["rooms"]]
                    if user_list:
                        res = f"--- Users in {target} ({len(user_list)}) ---\n{', '.join(user_list)}\n---------------------------\n"
                    else:
                        res = f"[!] ERROR: Room {target} not found.\n"
                    conn.send(res.encode('utf-8'))
                elif cmd == "/part":
                    target = arg if arg else clients[conn]["active_room"]
                    if target == "#lobby":
                        conn.send("[!] ERROR: You cannot leave #lobby.\n".encode('utf-8'))
                    elif target in clients[conn]["rooms"]:
                        clients[conn]["rooms"].remove(target)
                        broadcast(f"*** {clients[conn]['name']} left {target} ***", target)
                        if clients[conn]["active_room"] == target:
                            clients[conn]["active_room"] = "#lobby"
                            conn.send(f"JOIN_SUCCESS|#lobby\n[i] Switched to #lobby\n".encode('utf-8'))
                        conn.send(f"[i] You left {target}\n".encode('utf-8'))
                elif cmd == "/nick" and arg:
                    if is_valid_id(arg) and not any(i['name'].lower() == arg.lower() for i in clients.values()):
                        old = clients[conn]["name"]
                        clients[conn]["name"] = arg
                        conn.send(f"NICK_SUCCESS|{arg}\n".encode('utf-8'))
                        for r in clients[conn]["rooms"]: broadcast(f"*** {old} is now known as {arg} ***", r)
                elif cmd == "/join" and arg:
                    clients[conn]["rooms"].add(arg)
                    clients[conn]["active_room"] = arg
                    conn.send(f"JOIN_SUCCESS|{arg}\n".encode('utf-8'))
                    if arg.startswith("#"): broadcast(f"*** {clients[conn]['name']} joined {arg} ***", arg)
            else:
                room = clients[conn]["active_room"]
                broadcast(f"<{room}> <{clients[conn]['name']}>: {data}", room, conn)
    except: pass
    finally:
        if conn in clients:
            u = clients[conn]
            reason = "timed out" if (time.time() - u["last_pong"] > TIMEOUT_LIMIT) else "quit"
            for r in u["rooms"]: broadcast(f"*** {u['name']} {reason} ***", r)
            del clients[conn]
        conn.close()

def start_server():
    print(f"[*] BIBLY Server starting on {HOST}:{PORT}...")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.bind((HOST, PORT))
        s.listen(5)
        print(f"[+] Server LIVE.")
    except Exception as e:
        print(f"[!] BIND ERROR: {e}")
        return
    while True:
        c, a = s.accept()
        threading.Thread(target=handle_client, args=(c, a), daemon=True).start()

if __name__ == "__main__":
    start_server()
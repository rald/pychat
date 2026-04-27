#!/usr/bin/env python3
import socket
import threading
import re

# Configuration
HOST = '192.227.241.244'
PORT = 14344
clients = {} 

def is_valid_identifier(name):
    """
    Validates that the identifier (nick or channel name) is:
    - 1 to 32 characters long
    - Only contains A-Z, a-z, 0-9, and underscores
    """
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
            raw_name = conn.recv(1024).decode('utf-8').strip()
            if is_valid_identifier(raw_name) and not any(i['name'].lower() == raw_name.lower() for i in clients.values()):
                clients[conn] = {"name": raw_name, "rooms": {"#general"}, "active_room": "#general"}
                conn.send(f"ACCEPT_NAME|{raw_name}".encode('utf-8'))
                broadcast(f"--- {raw_name} joined #general ---", "#general", conn)
                break
            conn.send("--- Error: Nick must be 1-32 chars (A-Za-z0-9_) and unique ---\n".encode('utf-8'))

        while True:
            raw_data = conn.recv(1024).decode('utf-8')
            if not raw_data: break
            data = raw_data.strip()
            
            # --- Command: Join ---
            if data.startswith("/join"):
                parts = data.split(" ", 1)
                if len(parts) < 2:
                    conn.send("--- Error: Usage: /join #channel or /join user ---\n".encode('utf-8'))
                    continue
                
                target = parts[1].strip()
                
                if target.startswith("#"):
                    channel_name = target[1:] # Strip the # for validation
                    if is_valid_identifier(channel_name):
                        clients[conn]["rooms"].add(target)
                        clients[conn]["active_room"] = target
                        broadcast(f"--- {clients[conn]['name']} joined {target} ---", target, conn)
                        conn.send(f"--- Joined channel {target} ---\n".encode('utf-8'))
                    else:
                        conn.send("--- Error: Channel name must be 1-32 chars (A-Za-z0-9_) ---\n".encode('utf-8'))
                else:
                    # Private Chat logic
                    partner_sock = next((s for s, info in clients.items() if info['name'] == target), None)
                    if partner_sock:
                        clients[conn]["active_room"] = target
                        conn.send(f"--- Now private chatting with {target} ---\n".encode('utf-8'))
                    else:
                        conn.send(f"--- Error: User '{target}' is not online ---\n".encode('utf-8'))

            # --- Command: Nick ---
            elif data.startswith("/nick "):
                new_name = data.split(" ", 1)[1].strip()
                if is_valid_identifier(new_name) and not any(info['name'].lower() == new_name.lower() for info in clients.values()):
                    old_name = clients[conn]["name"]
                    clients[conn]["name"] = new_name
                    conn.send(f"--- You are now known as {new_name} ---\n".encode('utf-8'))
                    notice = f"--- {old_name} changed name to {new_name} ---"
                    for room in clients[conn]["rooms"]:
                        broadcast(notice, room, conn)
                else:
                    conn.send("--- Error: Invalid name or already taken ---\n".encode('utf-8'))

            # --- Command: Part ---
            elif data.startswith("/part "):
                room_to_leave = data.split(" ", 1)[1].strip()
                if room_to_leave in clients[conn]["rooms"]:
                    broadcast(f"--- {clients[conn]['name']} left {room_to_leave} ---", room_to_leave, conn)
                    clients[conn]["rooms"].remove(room_to_leave)
                    if clients[conn]["active_room"] == room_to_leave:
                        clients[conn]["active_room"] = "#general"
                        conn.send("--- Focus shifted to #general ---\n".encode('utf-8'))
                else:
                    conn.send(f"--- Error: You are not in {room_to_leave} ---\n".encode('utf-8'))

            elif data == "/list":
                all_rooms = set()
                for info in clients.values():
                    for r in info["rooms"]:
                        if r.startswith("#"): all_rooms.add(r)
                conn.send(f"--- Active Channels: {', '.join(all_rooms) if all_rooms else 'None'} ---\n".encode('utf-8'))

            elif data.startswith("/names"):
                parts = data.split(" ", 1)
                target_chan = parts[1].strip() if len(parts) > 1 else clients[conn]["active_room"]
                users_in_channel = [info['name'] for info in clients.values() if target_chan in info['rooms']]
                if users_in_channel:
                    conn.send(f"--- Users in {target_chan}: {', '.join(users_in_channel)} ---\n".encode('utf-8'))
                else:
                    conn.send(f"--- Error: No users found in {target_chan} ---\n".encode('utf-8'))

            elif data == "/help":
                help_text = (
                    "\n--- COMMANDS ---\n"
                    "/nick <name>      : Set identity (A-Za-z0-9_, max 32)\n"
                    "/join #<channel>  : Join/Focus channel (A-Za-z0-9_, max 32)\n"
                    "/join <user>      : Private chat with user\n"
                    "/part #<channel>  : Leave channel\n"
                    "/list             : List active channels\n"
                    "/names [#chan]    : List users in room\n"
                    "/quit [msg]       : Exit chat\n"
                    "--- UI TIPS ---\n"
                    "UP/DOWN Arrows    : Command History\n"
                    "PGUP/PGDN Keys    : Scroll Chat History\n"
                )
                conn.send(help_text.encode('utf-8'))
            
            elif data.startswith("/quit"):
                reason = "Client Quit"
                if " " in data: reason = data.split(" ", 1)[1]
                break

            else:
                # Regular messaging
                active = clients[conn]["active_room"]
                my_name = clients[conn]["name"]
                if active.startswith("#"):
                    broadcast(f"<{active}> <{my_name}>: {data}", active, conn)
                else:
                    priv_room = f"priv_{min(my_name, active)}_{max(my_name, active)}"
                    for s, info in clients.items():
                        if info['name'] == active: info['rooms'].add(priv_room)
                    broadcast(f"<PM from {my_name}>: {data}", priv_room, conn)

    except: pass
    finally:
        if conn in clients:
            user_info = clients[conn]
            q_msg = locals().get('reason', 'Disconnected')
            for room in user_info["rooms"]:
                broadcast(f"--- {user_info['name']} quit ({q_msg}) ---", room, conn)
            del clients[conn]
        conn.close()

def start_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen()
    print(f"Chat Server live on {HOST}:{PORT}")
    while True:
        conn, addr = server.accept()
        threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()

if __name__ == "__main__":
    start_server()
import socket
import threading
import re

# Configuration
HOST = '192.227.241.244'
PORT = 14344
clients = {} # {socket: {"name": str, "rooms": set(), "active_room": str}}

def is_valid_identifier(name):
    """Checks if string is 1-32 chars of A-Za-z0-9_."""
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
        # --- Nickname Handshake ---
        while True:
            conn.send("ENTER_USERNAME".encode('utf-8'))
            name = conn.recv(1024).decode('utf-8').strip()
            
            if not is_valid_identifier(name):
                conn.send("--- Error: Nick must be 1-32 chars (A-Z, a-z, 0-9, _) ---\n".encode('utf-8'))
                continue
                
            if any(info['name'].lower() == name.lower() for info in clients.values()):
                conn.send(f"--- Error: '{name}' is taken! ---\n".encode('utf-8'))
            else:
                clients[conn] = {"name": name, "rooms": {"#general"}, "active_room": "#general"}
                conn.send(f"ACCEPT_NAME|{name}".encode('utf-8'))
                broadcast(f"--- {name} joined #general ---", "#general", conn)
                break

        while True:
            data = conn.recv(1024).decode('utf-8')
            if not data: break
            
            # --- Command Handling ---
            if data.startswith("/nick "):
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

            elif data.startswith("/join "):
                target = data.split(" ", 1)[1].strip()
                if target.startswith("#"):
                    channel_name = target[1:]
                    if is_valid_identifier(channel_name):
                        clients[conn]["rooms"].add(target)
                        clients[conn]["active_room"] = target
                        broadcast(f"--- {clients[conn]['name']} joined {target} ---", target, conn)
                        conn.send(f"--- Joined channel {target} ---\n".encode('utf-8'))
                else:
                    partner_sock = next((s for s, info in clients.items() if info['name'] == target), None)
                    if partner_sock:
                        my_name = clients[conn]["name"]
                        priv_room = f"priv_{min(my_name, target)}_{max(my_name, target)}"
                        clients[conn]["rooms"].add(priv_room)
                        clients[conn]["active_room"] = target
                        conn.send(f"--- Private chat with {target} active ---\n".encode('utf-8'))
                    else:
                        conn.send(f"--- Error: User {target} not found ---\n".encode('utf-8'))

            elif data.startswith("/part "):
                room_to_leave = data.split(" ", 1)[1].strip()
                if room_to_leave.startswith("#") and room_to_leave in clients[conn]["rooms"]:
                    broadcast(f"--- {clients[conn]['name']} left {room_to_leave} ---", room_to_leave, conn)
                    clients[conn]["rooms"].remove(room_to_leave)
                    conn.send(f"--- Left channel: {room_to_leave} ---\n".encode('utf-8'))
                    if clients[conn]["active_room"] == room_to_leave:
                        clients[conn]["active_room"] = "#general"
                        conn.send("--- Focus shifted to #general ---\n".encode('utf-8'))

            elif data == "/list":
                # Filter all active rooms for those starting with '#'
                all_rooms = set()
                for info in clients.values():
                    for r in info["rooms"]:
                        if r.startswith("#"): all_rooms.add(r)
                conn.send(f"--- Active Channels: {', '.join(all_rooms) if all_rooms else 'None'} ---\n".encode('utf-8'))

            elif data.startswith("/names "):
                channel = data.split(" ", 1)[1].strip()
                users_in_channel = [info['name'] for info in clients.values() if channel in info['rooms']]
                if users_in_channel:
                    conn.send(f"--- Users in {channel}: {', '.join(users_in_channel)} ---\n".encode('utf-8'))
                else:
                    conn.send(f"--- Error: Channel {channel} not found or empty ---\n".encode('utf-8'))

            elif data == "/help":
                help_text = (
                    "\n/nick <name>      - Set name (A-Z, 0-9, _, max 32)\n"
                    "/join #<channel>  - Join/Focus channel\n"
                    "/join <user>      - Private chat user\n"
                    "/part #<channel>  - Leave a channel\n"
                    "/list             - List all #channels\n"
                    "/names #<channel> - List users in channel\n"
                )
                conn.send(help_text.encode('utf-8'))
            
            else:
                active = clients[conn]["active_room"]
                my_name = clients[conn]["name"]
                if not active.startswith("#"):
                    priv_room = f"priv_{min(my_name, active)}_{max(my_name, active)}"
                    for s, info in clients.items():
                        if info['name'] == active: info['rooms'].add(priv_room)
                    broadcast(f"<PM from {my_name}>: {data}", priv_room, conn)
                else:
                    broadcast(f"<{active}> <{my_name}>: {data}", active, conn)

    except: pass
    finally:
        if conn in clients: del clients[conn]
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
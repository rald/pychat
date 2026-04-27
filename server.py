import socket
import threading

# Updated Network Config
HOST = '192.227.241.244'
PORT = 14344
clients = {} 

def broadcast(message, room, sender_sock):
    for sock, info in clients.items():
        if room in info["rooms"] and sock != sender_sock:
            try:
                sock.send(message.encode('utf-8'))
            except:
                pass

def handle_client(conn, addr):
    try:
        while True:
            conn.send("ENTER_USERNAME".encode('utf-8'))
            name = conn.recv(1024).decode('utf-8').strip()
            name_taken = any(info['name'].lower() == name.lower() for info in clients.values())
            
            if not name:
                conn.send("--- Error: Name cannot be empty! ---\n".encode('utf-8'))
            elif name_taken:
                conn.send(f"--- Error: '{name}' is taken! ---\n".encode('utf-8'))
            else:
                clients[conn] = {"name": name, "rooms": {"general"}, "active_room": "general"}
                conn.send(f"ACCEPT_NAME|{name}".encode('utf-8'))
                broadcast(f"--- {name} joined general ---", "general", conn)
                break

        while True:
            data = conn.recv(1024).decode('utf-8')
            if not data: break
            
            if data.startswith("/nick "):
                new_name = data.split(" ", 1)[1].strip()
                if not new_name: continue
                if not any(info['name'].lower() == new_name.lower() for info in clients.values()):
                    old_name = clients[conn]["name"]
                    clients[conn]["name"] = new_name
                    conn.send(f"--- You are now known as {new_name} ---\n".encode('utf-8'))
                    notice = f"--- {old_name} changed their name to {new_name} ---"
                    for room in clients[conn]["rooms"]:
                        broadcast(notice, room, conn)
                else:
                    conn.send("--- Error: Name taken! ---\n".encode('utf-8'))

            elif data.startswith("/join "):
                room = data.split(" ", 1)[1].strip()
                if not room: continue
                if room not in clients[conn]["rooms"]:
                    broadcast(f"--- {clients[conn]['name']} joined {room} ---", room, conn)
                clients[conn]["rooms"].add(room)
                clients[conn]["active_room"] = room
                conn.send(f"--- Joined {room} (Now Active) ---\n".encode('utf-8'))

            elif data.startswith("/part "):
                parts = data.split(" ", 1)
                if len(parts) < 2: continue
                room_to_leave = parts[1].strip()
                if room_to_leave in clients[conn]["rooms"]:
                    broadcast(f"--- {clients[conn]['name']} left {room_to_leave} ---", room_to_leave, conn)
                    clients[conn]["rooms"].remove(room_to_leave)
                    conn.send(f"--- Left room: {room_to_leave} ---\n".encode('utf-8'))
                    if clients[conn]["active_room"] == room_to_leave:
                        clients[conn]["active_room"] = "general" if "general" in clients[conn]["rooms"] else "lobby"
                        clients[conn]["rooms"].add(clients[conn]["active_room"])
                        conn.send(f"--- Focus shifted to: {clients[conn]['active_room']} ---\n".encode('utf-8'))
                else:
                    conn.send(f"--- Error: You aren't in {room_to_leave} ---\n".encode('utf-8'))

            elif data == "/list":
                all_rooms = list(set(r for info in clients.values() for r in info["rooms"]))
                conn.send(f"--- Global Active Rooms: {', '.join(all_rooms)} ---\n".encode('utf-8'))

            elif data.startswith("/names "):
                room = data.split(" ", 1)[1].strip()
                names = [info['name'] for info in clients.values() if room in info['rooms']]
                conn.send(f"--- Users in {room}: {', '.join(names)} ---\n".encode('utf-8'))
            else:
                active_room = clients[conn]["active_room"]
                msg = f"<{active_room}> <{clients[conn]['name']}>: {data}"
                broadcast(msg, active_room, conn)
                
    except:
        pass
    finally:
        if conn in clients:
            final_name = clients[conn]['name']
            for room in clients[conn]['rooms']:
                broadcast(f"--- {final_name} has disconnected ---", room, conn)
            del clients[conn]
        conn.close()

def start_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    # Binding to your specific IP
    server.bind((HOST, PORT))
    server.listen()
    print(f"Chat Server live on {HOST}:{PORT}")
    while True:
        conn, addr = server.accept()
        threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()

if __name__ == "__main__":
    start_server()
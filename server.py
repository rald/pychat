#!/usr/bin/env python3
import socket, threading, re, time

HOST, PORT = '192.227.241.244', 14344
TIMEOUT_LIMIT = 60
clients = {} 

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
    name = ""
    try:
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
            conn.send("[!] ERROR: Name invalid or taken.\n".encode('utf-8'))

        while True:
            raw = conn.recv(1024).decode('utf-8')
            if not raw: break
            data = raw.strip()
            if data.startswith("PONG|"):
                if conn in clients: clients[conn]["last_pong"] = time.time()
                continue
            
            if data.startswith("/"):
                parts = data.split(" ", 1)
                cmd = parts[0].lower()
                arg = parts[1].strip() if len(parts) > 1 else ""
                if cmd == "/quit": break
                # ... other commands (/nick, /join) go here ...
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
    print(f"[*] Initializing server on {HOST}:{PORT}...")
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, PORT))
        s.listen(5)
        print(f"[+] Server is LIVE and listening for connections.")
    except Exception as e:
        print(f"[!] FATAL ERROR: Could not start server: {e}")
        return

    while True:
        try:
            c, a = s.accept()
            print(f"[*] New connection from {a}")
            threading.Thread(target=handle_client, args=(c, a), daemon=True).start()
        except KeyboardInterrupt:
            print("\n[!] Server shutting down.")
            break
        except Exception as e:
            print(f"[!] Loop error: {e}")

if __name__ == "__main__":
    start_server()
#!/usr/bin/env python3
import socket, threading, re

HOST, PORT = '192.227.241.244', 14344
clients = {} 

def is_valid_id(name):
    return 1 <= len(name) <= 32 and re.match(r"^[A-Za-z0-9_]+$", name)

def broadcast(msg, room, sender_sock=None):
    formatted_msg = f"{msg}\n".encode('utf-8')
    for sock, info in clients.items():
        if room in info["rooms"] and sock != sender_sock:
            try: sock.send(formatted_msg)
            except: pass

def handle_client(conn, addr):
    quit_msg = "quit" # Default quit reason
    try:
        # --- Handshake ---
        while True:
            conn.send("ENTER_USERNAME\n".encode('utf-8'))
            raw_data = conn.recv(1024).decode('utf-8')
            if not raw_data: return
            name = raw_data.strip()
            
            if is_valid_id(name) and not any(i['name'].lower() == name.lower() for i in clients.values()):
                clients[conn] = {"name": name, "rooms": {"#lobby"}, "active_room": "#lobby"}
                conn.send(f"ACCEPT_NAME|{name}\n".encode('utf-8'))
                broadcast(f"*** {name} joined #lobby ***", "#lobby")
                break
            conn.send("[!] ERROR: Name taken or invalid.\n".encode('utf-8'))

        while True:
            raw_data = conn.recv(1024).decode('utf-8')
            if not raw_data: break
            data = raw_data.strip()
            if not data: continue

            if data.startswith("/"):
                parts = data.split(" ", 1)
                cmd = parts[0].lower()
                arg = parts[1].strip() if len(parts) > 1 else ""

                if cmd == "/quit":
                    if arg: quit_msg = f"quit ({arg})"
                    break # Break the loop to trigger the 'finally' block

                elif cmd == "/help":
                    help_table = (
                        "\n+-------------------+------------------------------------------+\n"
                        "| COMMAND           | DESCRIPTION                              |\n"
                        "+-------------------+------------------------------------------+\n"
                        "| /join <#chan>     | Join and focus a public channel          |\n"
                        "| /join <nick>      | Focus private messages to a user         |\n"
                        "| /part [#chan]     | Leave a channel (cannot leave #lobby)    |\n"
                        "| /nick <name>      | Change your display name                 |\n"
                        "| /list             | List all active public channels          |\n"
                        "| /names [#chan]    | List users in channel or current room    |\n"
                        "| /quit [message]   | Disconnect with an optional reason       |\n"
                        "| /help             | Show this command table                  |\n"
                        "+-------------------+------------------------------------------+\n"
                    )
                    conn.send(help_table.encode('utf-8'))

                elif cmd == "/join" and arg:
                    if arg.startswith("#"):
                        if is_valid_id(arg[1:]):
                            clients[conn]["rooms"].add(arg)
                            clients[conn]["active_room"] = arg
                            conn.send(f"JOIN_SUCCESS|{arg}\n".encode('utf-8'))
                            broadcast(f"*** {clients[conn]['name']} joined {arg} ***", arg)
                        else:
                            conn.send(f"[!] ERROR: '{arg}' is not a valid channel name.\n".encode('utf-8'))
                    else:
                        if any(i['name'].lower() == arg.lower() for i in clients.values()):
                            clients[conn]["active_room"] = arg
                            conn.send(f"JOIN_SUCCESS|{arg}\n".encode('utf-8'))
                        else:
                            conn.send(f"[!] ERROR: User '{arg}' not found.\n".encode('utf-8'))

                elif cmd == "/part":
                    target = arg if arg else clients[conn]["active_room"]
                    if len(clients[conn]["rooms"]) <= 1 and "#lobby" in clients[conn]["rooms"]:
                        conn.send("[!] ERROR: Cannot leave #lobby.\n".encode('utf-8'))
                    elif target in clients[conn]["rooms"]:
                        broadcast(f"*** {clients[conn]['name']} left {target} ***", target)
                        clients[conn]["rooms"].remove(target)
                        if clients[conn]["active_room"] == target:
                            clients[conn]["active_room"] = "#lobby"
                            conn.send(f"JOIN_SUCCESS|#lobby\n".encode('utf-8'))
                    else:
                        conn.send(f"[!] ERROR: You are not in {target}.\n".encode('utf-8'))

                elif cmd == "/list":
                    all_chans = {r for c in clients.values() for r in c["rooms"] if r.startswith("#")}
                    conn.send(f"--- Channels: {', '.join(all_chans) if all_chans else 'None'} ---\n".encode('utf-8'))

                elif cmd == "/names":
                    target = arg if arg else clients[conn]["active_room"]
                    users = [info['name'] for info in clients.values() if target in info['rooms']]
                    conn.send(f"--- Users in {target}: {', '.join(users) if users else 'N/A'} ---\n".encode('utf-8'))

                elif cmd == "/nick" and arg:
                    if is_valid_id(arg) and not any(i['name'].lower() == arg.lower() for i in clients.values()):
                        old = clients[conn]["name"]
                        clients[conn]["name"] = arg
                        conn.send(f"NICK_SUCCESS|{arg}\n".encode('utf-8'))
                        for r in clients[conn]["rooms"]: 
                            broadcast(f"*** {old} is now known as {arg} ***", r)
                    else: 
                        conn.send("[!] ERROR: Nickname taken or invalid.\n".encode('utf-8'))

                else:
                    conn.send(f"[!] ERROR: Unknown command '{cmd}'.\n".encode('utf-8'))

            else:
                # Messaging
                active = clients[conn]["active_room"]
                my_name = clients[conn]["name"]
                if active.startswith("#"):
                    broadcast(f"<{active}> <{my_name}>: {data}", active, conn)
                else:
                    priv_room = f"priv_{min(my_name, active).lower()}_{max(my_name, active).lower()}"
                    target_exists = False
                    for s, info in clients.items():
                        if info['name'].lower() == active.lower(): 
                            info['rooms'].add(priv_room)
                            target_exists = True
                    if target_exists:
                        broadcast(f"<PM from {my_name}>: {data}", priv_room, conn)
                    else:
                        conn.send(f"[!] ERROR: User '{active}' is offline.\n".encode('utf-8'))
                        
    except: pass
    finally:
        if conn in clients:
            u = clients[conn]
            # Uses the captured quit_msg (either default or user-provided)
            for r in u["rooms"]: 
                broadcast(f"*** {u['name']} {quit_msg} ***", r)
            del clients[conn]
        conn.close()

def start_server():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((HOST, PORT))
    s.listen()
    print(f"Server live on {HOST}:{PORT}")
    while True:
        c, a = s.accept()
        threading.Thread(target=handle_client, args=(c, a), daemon=True).start()

if __name__ == "__main__": start_server()
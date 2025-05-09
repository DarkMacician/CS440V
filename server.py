import json
import socket
import threading
import pymongo
import certifi
import sys
from datetime import datetime

def get_timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def connect_to_mongodb():
    try:
        client_db = pymongo.MongoClient(
            "mongodb+srv://hoaiduy:introdatabase2024@cluster0.kvp0p.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0",
            tlsCAFile=certifi.where(),
            serverSelectionTimeoutMS=5000
        )
        # Test the connection
        client_db.admin.command('ping')
        print("✅ Successfully connected to MongoDB")
        return client_db
    except Exception as e:
        print(f"❌ Failed to connect to MongoDB: {e}")
        sys.exit(1)

# Initialize MongoDB connection
client_db = connect_to_mongodb()
db = client_db["CS440V"]
users_collection = db["users"]
groups_collection = db["groups"]

clients = {}

def register_user(username, password):
    """Registers a new user in MongoDB."""
    try:
        if users_collection.find_one({"username": username}):
            return False  # User already exists

        users_collection.insert_one({
            "username": username,
            "password": password
        })
        return True  # Successfully registered
    except Exception as e:
        print(f"❌ Error registering user: {e}")
        return False

def authenticate_user(username, password):
    """Authenticates a user."""
    try:
        user = users_collection.find_one({"username": username})
        if user and user["password"] == password:
            return True
        return False
    except Exception as e:
        print(f"❌ Error authenticating user: {e}")
        return False

def broadcast_message(message, sender_username):
    """Sends the message to all clients including the sender."""
    timestamp = get_timestamp()
    print(f"\n[{timestamp}] 📢 Broadcast from {sender_username}: {message}")
    
    disconnected_users = []
    for user, client_socket in clients.items():
        try:
            client_socket.sendall(message.encode())
        except:
            disconnected_users.append(user)
    # Clean up disconnected users
    for user in disconnected_users:
        if user in clients:
            try:
                clients[user].close()
            except:
                pass
            del clients[user]

def handle_client(client_socket):
    username = None
    try:
        # Send initial connection success
        client_socket.send("CONNECTED".encode())
        
        # Wait for authentication type
        auth_type = client_socket.recv(1024).decode().strip().lower()
        
        # Get username
        client_socket.send("USERNAME".encode())
        username = client_socket.recv(1024).decode().strip()
        
        # Get password
        client_socket.send("PASSWORD".encode())
        password = client_socket.recv(1024).decode().strip()

        if auth_type == "no":  # Registration
            if register_user(username, password):
                client_socket.send("REGISTER_SUCCESS".encode())
                print(f"\n[{get_timestamp()}] ✅ New user registered: {username}")
            else:
                client_socket.send("USERNAME_EXISTS".encode())
                print(f"\n[{get_timestamp()}] ❌ Registration failed - Username exists: {username}")
                return
        else:  # Login
            if authenticate_user(username, password):
                client_socket.send("LOGIN_SUCCESS".encode())
                print(f"\n[{get_timestamp()}] ✅ User logged in: {username}")
            else:
                client_socket.send("INVALID_CREDENTIALS".encode())
                print(f"\n[{get_timestamp()}] ❌ Login failed - Invalid credentials: {username}")
                return

        # Add client to active clients
        clients[username] = client_socket
        print(f"\n[{get_timestamp()}] 🟢 {username} connected.")

        # Main chat loop
        while True:
            try:
                data = client_socket.recv(1024).decode()
                if not data:
                    break

                data = json.loads(data)
                msg = data.get("message")
                client_name = data.get("username")

                if not msg:
                    continue

                if msg.startswith("/create_group"):
                    parts = msg.split(maxsplit=1)
                    if len(parts) != 2:
                        client_socket.sendall("❌ Usage: /create_group <group_name>".encode())
                        continue
                    
                    group_name = parts[1].strip()
                    if groups_collection.find_one({"group_name": group_name}):
                        client_socket.sendall("❌ Group already exists.".encode())
                        print(f"\n[{get_timestamp()}] ❌ Group creation failed - Already exists: {group_name}")
                    else:
                        groups_collection.insert_one({
                            "group_name": group_name,
                            "members": [username]
                        })
                        client_socket.sendall(f"✅ Group '{group_name}' created.".encode())
                        print(f"\n[{get_timestamp()}] ✅ Group created: {group_name} by {username}")

                elif msg.startswith("/join_group"):
                    parts = msg.split()
                    if len(parts) != 2:
                        client_socket.sendall("❌ Usage: /join_group <group_name>".encode())
                        continue
                    
                    group_name = parts[1]
                    group = groups_collection.find_one({"group_name": group_name})
                    if not group:
                        client_socket.sendall("❌ Group does not exist.".encode())
                        print(f"\n[{get_timestamp()}] ❌ Join group failed - Group not found: {group_name}")
                        continue
                    if username in group["members"]:
                        client_socket.sendall(f"⚠️ You are already in group '{group_name}'.".encode())
                        print(f"\n[{get_timestamp()}] ⚠️ Join group failed - Already member: {username} in {group_name}")
                        continue
                    
                    groups_collection.update_one(
                        {"group_name": group_name},
                        {"$push": {"members": username}}
                    )
                    client_socket.sendall(f"✅ You joined group '{group_name}'.".encode())
                    print(f"\n[{get_timestamp()}] ✅ User joined group: {username} joined {group_name}")

                elif msg.startswith("/group_msg"):
                    parts = msg.split(" ", 2)
                    if len(parts) != 3:
                        client_socket.sendall("❌ Usage: /group_msg <group_name> <message>".encode())
                        continue

                    group_name, message = parts[1], parts[2]
                    group = groups_collection.find_one({"group_name": group_name})
                    if not group:
                        client_socket.sendall("❌ Group does not exist.".encode())
                        print(f"\n[{get_timestamp()}] ❌ Group message failed - Group not found: {group_name}")
                        continue
                    if username not in group["members"]:
                        client_socket.sendall("❌ You are not a member of this group.".encode())
                        print(f"\n[{get_timestamp()}] ❌ Group message failed - Not a member: {username} in {group_name}")
                        continue

                    print(f"\n[{get_timestamp()}] 👥 Group message in {group_name} from {username}: {message}")
                    # Send to all members including sender
                    for member in group["members"]:
                        if member in clients:  # Remove the condition that excludes sender
                            try:
                                data = f'({group_name}) {username}: {message}'
                                clients[member].sendall(data.encode())
                            except:
                                if member in clients:
                                    try:
                                        clients[member].close()
                                    except:
                                        pass
                                    del clients[member]

                elif msg.startswith("/msg"):
                    parts = msg.split(" ", 2)
                    if len(parts) != 3:
                        client_socket.sendall("❌ Usage: /msg <username> <message>".encode())
                        continue

                    target_user, message = parts[1], parts[2]
                    if target_user not in clients:
                        client_socket.sendall("❌ User is not online.".encode())
                        print(f"\n[{get_timestamp()}] ❌ Private message failed - User offline: {target_user}")
                        continue

                    try:
                        data = f'(private) {username}: {message}'
                        # Send to both sender and recipient
                        clients[target_user].sendall(data.encode())
                        client_socket.sendall(data.encode())  # Send to sender as well
                        print(f"\n[{get_timestamp()}] 📩 Private message from {username} to {target_user}: {message}")
                    except:
                        client_socket.sendall("❌ Failed to send message.".encode())
                        print(f"\n[{get_timestamp()}] ❌ Private message failed - Send error: {username} to {target_user}")
                        if target_user in clients:
                            try:
                                clients[target_user].close()
                            except:
                                pass
                            del clients[target_user]

                else:
                    msg = f'(all) {username}: {msg}'
                    broadcast_message(msg, username)

            except json.JSONDecodeError:
                continue
            except Exception as e:
                print(f"\n[{get_timestamp()}] ❌ Error handling message: {e}")
                break

    except Exception as e:
        print(f"\n[{get_timestamp()}] ❌ Error: {e}")
    finally:
        if username and username in clients:
            del clients[username]
        try:
            client_socket.close()
        except:
            pass
        if username:
            print(f"\n[{get_timestamp()}] ❌ {username} disconnected.")

def start_server():
    """Starts the server."""
    try:
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("0.0.0.0", 5555))
        server.listen(5)
        print(f"\n[{get_timestamp()}] 🟢 Server started on port 5555")

        while True:
            try:
                client_socket, _ = server.accept()
                threading.Thread(target=handle_client, args=(client_socket,), daemon=True).start()
            except Exception as e:
                print(f"\n[{get_timestamp()}] ❌ Error accepting connection: {e}")
    except Exception as e:
        print(f"\n[{get_timestamp()}] ❌ Failed to start server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    start_server()
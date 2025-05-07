import json
import socket
import threading
import pymongo

# MongoDB connection
client_db = pymongo.MongoClient("mongodb+srv://hoaiduy:introdatabase2024@cluster0.kvp0p.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
db = client_db["CS440V"]
users_collection = db["users"]
groups_collection = db["groups"]

clients = {}

def register_user(username, password):
    """Registers a new user in MongoDB."""
    if users_collection.find_one({"username": username}):
        return None  # User already exists

    users_collection.insert_one({
        "username": username,
        "password": password
    })

    return True  # Successfully registered

def authenticate_user(username, password):
    """Authenticates a user."""
    user = users_collection.find_one({"username": username})
    if user["password"] == password:
        return True
    return False

def broadcast_message(message, sender_username):
    """Sends the message to all clients except the sender."""
    for user, client_socket in clients.items():
        if user != sender_username:
            try:
                client_socket.sendall(message.encode())
            except:
                client_socket.close()
                del clients[user]

def handle_client(client_socket):
    username = None
    """Handles user authentication and messaging."""
    try:
        client_socket.send("Do you have an account? (yes/no): ".encode())
        while True:
            has_account = client_socket.recv(1024).decode().strip().lower()
            if has_account in ("yes", "no"):
                break
            else:
                client_socket.send("❌ Invalid input. Please type 'yes' or 'no'.\nDo you have an account? (yes/no): ".encode())

        if has_account == "yes":
            client_socket.send("Enter username: ".encode())
            username = client_socket.recv(1024).decode().strip()

            client_socket.send("Enter password: ".encode())
            password = client_socket.recv(1024).decode().strip()

            if not authenticate_user(username, password):
                client_socket.send("Login failed. Closing connection.".encode())
                return
        else:
            client_socket.send("📝 Let's create a new account.\n".encode())

            client_socket.send("Enter username: ".encode())
            username = client_socket.recv(1024).decode().strip()

            client_socket.send("Enter password: ".encode())
            password = client_socket.recv(1024).decode().strip()

            while True:
                if register_user(username, password):
                    client_socket.send("✅ Account created successfully.\n".encode())
                    break
                else:
                    client_socket.send("❌ Username already exists. Try another one.\n".encode())

                client_socket.send("Enter another username: ".encode())
                username = client_socket.recv(1024).decode().strip()

        clients[username] = client_socket
        clients[username].send("You can chat now!".encode())
        print(f"🟢 {username} connected.")

        while True:
            data = client_socket.recv(1024).decode()
            print(data)
            data = json.loads(data)
            msg = data.get("message")
            client_name = data.get("username")
            if not msg:
                break

            try:
                if msg.startswith("/create_group"):
                    parts = msg.split(maxsplit=1)
                    if len(parts) != 2:
                        client_socket.sendall("❌ Usage: /create_group <group_name>".encode())
                        continue
                    group_name = parts[1].strip()
                    print(group_name)

                    # Kiểm tra nếu nhóm đã tồn tại
                    if groups_collection.find_one({"group_name": group_name}):
                        client_socket.sendall("❌ Group already exists.".encode())
                    else:
                        # Tạo nhóm mới
                        groups_collection.insert_one({
                            "group_name": group_name,
                            "members": [username]
                        })
                        client_socket.sendall(f"✅ Group '{group_name}' created.".encode())
                    continue

                elif msg.startswith("/join_group"):
                    parts = msg.split()
                    if len(parts) != 2:
                        client_socket.sendall("❌ Usage: /join_group <group_name>".encode())
                        continue
                    group_name = parts[1]
                    group = groups_collection.find_one({"group_name": group_name})
                    if not group:
                        client_socket.sendall("❌ Group does not exist.".encode())
                        continue
                    if username in group["members"]:
                        client_socket.sendall(f"⚠️ You are already in group '{group_name}'.".encode())
                        continue
                    groups_collection.update_one(
                        {"group_name": group_name},
                        {"$push": {"members": username}}
                    )
                    client_socket.sendall(f"✅ You joined group '{group_name}'.".encode())
                    continue

                elif msg.startswith("/group_msg"):
                    parts = msg.split(" ", 2)
                    if len(parts) != 3:
                        client_socket.sendall("❌ Usage: /group_msg <group_name> <message>".encode())
                        continue

                    group_name, message = parts[1], parts[2]
                    group = groups_collection.find_one({"group_name": group_name})
                    if not group:
                        client_socket.sendall("❌ Group does not exist.".encode())
                        continue
                    if username not in group["members"]:
                        client_socket.sendall("❌ You are not a member of this group.".encode())
                        continue

                    # Send plaintext message to all members
                    for member in group["members"]:
                        if member != username and member in clients:
                            receiver_socket = clients[member]
                            try:
                                data = f'({group_name}) {username}: {message}'
                                receiver_socket.sendall(data.encode())
                            except Exception as e:
                                print(f"❌ Failed to send to {member}: {e}")

                elif msg.startswith("/msg"):
                    #sender = users_collection.find_one({"username": username})
                    parts = msg.split(" ", 2)
                    if len(parts) != 3:
                        client_socket.sendall("❌ Usage: /msg <username> <message>".encode())
                        continue

                    target_user, message = parts[1], parts[2]

                    if target_user not in clients:
                        client_socket.sendall("❌ User is not online.".encode())
                        continue

                    try:
                        data = f'(private) {username}: {message}'
                        clients[target_user].sendall(data.encode())
                        client_socket.sendall(f"📩 Sent to {target_user}".encode())
                    except Exception as e:
                        client_socket.sendall("❌ Failed to send message.".encode())
                        print(f"❗ Error sending direct message: {e}")
                else:
                    msg = f'(all) {username}: {msg}'
                    broadcast_message(msg, username)

            except Exception as e:
                print(f"❌ Error handling message: {e}")

    except Exception as e:
        print(f"❗ Error: {e}")
    finally:
        if username in clients:
            del clients[username]
        client_socket.close()
        print(f"❌ {username} disconnected.")

def start_server():
    """Starts the server."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("0.0.0.0", 5555))
    server.listen(5)
    print("🟢 Server started on port 5555")

    while True:
        client_socket, _ = server.accept()
        threading.Thread(target=handle_client, args=(client_socket,)).start()

if __name__ == "__main__":
    start_server()
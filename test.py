import json
import socket
import threading


def start_client():
    """Starts the client and connects to the server."""
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # 🛠️ Thay đổi IP máy chủ ở đây nếu cần
    try:
        client.connect(("127.0.0.1", 5555))  # Sửa thành IP thật của server nếu cần
    except ConnectionRefusedError:
        print("❌ Cannot connect to server. Please, check the error.")
        return

    # Account Handling
    while True:
        prompt = client.recv(1024).decode()
        print(prompt, end="")  # "Do you have an account? (yes/no): "
        has_account = input().strip().lower()
        client.send(has_account.encode())

        if has_account in ("yes", "no"):
            break

    if has_account == "yes":
        print(client.recv(1024).decode(), end="")  # "Enter username: "
        username = input().strip()
        client.send(username.encode())

        print(client.recv(1024).decode(), end="")  # "Enter password: "
        password = input().strip()
        client.send(password.encode())

        response = client.recv(1024).decode()
        if "failed" in response.lower():
            print(response)
            client.close()
            return
        print("✅ Login successful.")

    else:
        print(client.recv(1024).decode(), end="")  # "📝 Let's create a new account.\n"
        print(client.recv(1024).decode(), end="")  # "Enter username: "
        username = input().strip()
        client.send(username.encode())

        print(client.recv(1024).decode(), end="")  # "Enter password: "
        password = input().strip()
        client.send(password.encode())

        while True:
            response = client.recv(1024).decode()
            print(response, end="")
            if "✅" in response:
                break
            elif "❌ Username already exists" in response:
                print(client.recv(1024).decode(), end="")  # "Enter another username: "
                username = input().strip()
                client.send(username.encode())

    print(client.recv(1024).decode())  # "You can chat now!"

    def receive_messages():
        """Receives messages from the server."""
        print("-------------------------------CHAT-------------------------------")
        while True:
            try:
                message = client.recv(2048)
                if not message:
                    print("❌ Connection is interrupted.")
                    break
                print(message.decode())
            except ConnectionResetError:
                print("⚠️ Server closed connection.")
                break

    threading.Thread(target=receive_messages, daemon=True).start()

    while True:
        msg = input()
        if msg.lower() == "exit":
            print("👋 Exiting ...")
            break

        data = json.dumps({"username": username, "message": msg})
        client.sendall(data.encode())

    client.close()


if __name__ == "__main__":
    start_client()
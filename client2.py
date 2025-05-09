import json
import socket
import threading


def start_client():
    """Starts the client and connects to the server."""
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        client.connect(("127.0.0.1", 5555))
    except ConnectionRefusedError:
        print("❌ Không thể kết nối tới server. Vui lòng kiểm tra lại.")
        return

    # Account Handling
    print(client.recv(1024).decode(), end="")  # "Do you have an account? (yes/no): "
    has_account = input().strip().lower()
    client.send(has_account.encode())

    print(client.recv(1024).decode(), end="")  # "Enter username: "
    username = input().strip()
    client.send(username.encode())

    print(client.recv(1024).decode(), end="")  # "Enter password: "
    password = input().strip()
    client.send(password.encode())

    # Nhận phản hồi xác thực
    auth_response = client.recv(1024).decode().strip()

    if "failed" in auth_response or "already exists" in auth_response:
        print(auth_response)
        client.close()
        return

    print("✅ Đăng nhập thành công. Bắt đầu trò chuyện.")

    def receive_messages():
        """Receives messages from the server."""
        print("-------------------------------CHAT-------------------------------")
        while True:
            try:
                message = client.recv(2048)
                if not message:
                    print("❌ Kết nối bị ngắt.")
                    break
                print(message.decode())
            except ConnectionResetError:
                print("⚠️ Server đã đóng kết nối.")
                break

    threading.Thread(target=receive_messages, daemon=True).start()

    while True:
        msg = input()
        if msg.lower() == "exit":
            print("👋 Thoát khỏi chat...")
            break

        data = json.dumps({"username": username, "message": msg})
        client.sendall(data.encode())

    client.close()


if __name__ == "__main__":
    start_client()

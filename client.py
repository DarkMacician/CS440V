import streamlit as st
import socket
import json
import threading
import time
import queue
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

def get_timestamp():
    return datetime.now().strftime("%H:%M:%S")

# Initialize session state
if 'username' not in st.session_state:
    st.session_state.username = None
if 'client_socket' not in st.session_state:
    st.session_state.client_socket = None
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'connected' not in st.session_state:
    st.session_state.connected = False
if 'auth_status' not in st.session_state:
    st.session_state.auth_status = None
if 'message_queue' not in st.session_state:
    st.session_state.message_queue = queue.Queue()
if 'last_refresh' not in st.session_state:
    st.session_state.last_refresh = time.time()
if 'receive_thread' not in st.session_state:
    st.session_state.receive_thread = None

def connect_to_server():
    try:
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.settimeout(5)  # Timeout only for initial connection
        print("Connecting to server...")
        client_socket.connect(('localhost', 5555))
        print("Connected to server!")
        st.session_state.client_socket = client_socket

        # Wait for initial connection confirmation
        response = client_socket.recv(1024).decode()
        print(f"Received response from server: {response}")
        if response == "CONNECTED":
            st.session_state.connected = True
            # After successful connection, set socket to blocking mode
            client_socket.settimeout(None)
            return True
        return False
    except socket.timeout:
        st.error("Connection to server timed out. Please check if the server is running.")
        return False
    except ConnectionRefusedError:
        st.error("Could not connect to server. Please check if the server is running.")
        return False
    except Exception as e:
        st.error(f"Connection error: {str(e)}")
        return False

def receive_messages(client_socket, message_queue):
    control_msgs = {"USERNAME", "PASSWORD", "LOGIN_SUCCESS", "REGISTER_SUCCESS", "USERNAME_EXISTS", "INVALID_CREDENTIALS"}
    while True:
        try:
            if not client_socket:
                print("Socket does not exist, stopping message receiving thread.")
                break
            data = client_socket.recv(1024).decode()
            print(f"Received from server: {data}")  # DEBUG
            if data and data not in control_msgs:
                message_queue.put(data)
        except Exception as e:
            print(f"Error in receive_messages: {e}")
            break

def handle_authentication(username, password, has_account):
    try:
        client_socket = st.session_state.client_socket
        if not client_socket:
            st.error("No connection to server!")
            return False

        print(f"Starting authentication with type: {has_account}")
        # Send authentication type
        auth_type = "yes" if has_account == "Yes" else "no"
        print(f"Sending authentication type: {auth_type}")
        client_socket.send(auth_type.encode())
        time.sleep(0.1)  # Add small delay to ensure server receives
        
        # Wait for username prompt
        print("Waiting for USERNAME response...")
        response = client_socket.recv(1024).decode().strip()
        print(f"Received response: {response}")
        if response == "USERNAME":
            print(f"Sending username: {username}")
            client_socket.send(username.encode())
            time.sleep(0.1)  # Add small delay
        else:
            st.error(f"Authentication error: {response}")
            return False
        
        # Wait for password prompt
        print("Waiting for PASSWORD response...")
        response = client_socket.recv(1024).decode().strip()
        print(f"Received response: {response}")
        if response == "PASSWORD":
            print("Sending password")
            client_socket.send(password.encode())
            time.sleep(0.1)  # Add small delay
        else:
            st.error(f"Authentication error: {response}")
            return False
        
        # Get authentication result
        print("Waiting for authentication result...")
        response = client_socket.recv(1024).decode().strip()
        print(f"Authentication result: {response}")
        
        if response == "LOGIN_SUCCESS":
            st.session_state.username = username
            st.session_state.auth_status = "success"
            st.success("Login successful!")
            # Only start message receiving thread after successful login
            client_socket.settimeout(None)  # Ensure socket is in blocking mode
            if st.session_state.receive_thread is None or not st.session_state.receive_thread.is_alive():
                print("Initializing message receiving thread (after login)")
                st.session_state.receive_thread = threading.Thread(
                    target=receive_messages,
                    args=(st.session_state.client_socket, st.session_state.message_queue),
                    daemon=True
                )
                st.session_state.receive_thread.start()
            return True
        elif response == "REGISTER_SUCCESS":
            st.session_state.username = username
            st.session_state.auth_status = "success"
            st.success("Registration successful!")
            # Only start message receiving thread after successful registration
            client_socket.settimeout(None)  # Ensure socket is in blocking mode
            if st.session_state.receive_thread is None or not st.session_state.receive_thread.is_alive():
                print("Initializing message receiving thread (after register)")
                st.session_state.receive_thread = threading.Thread(
                    target=receive_messages,
                    args=(st.session_state.client_socket, st.session_state.message_queue),
                    daemon=True
                )
                st.session_state.receive_thread.start()
            return True
        elif response == "USERNAME_EXISTS":
            st.error("Username already exists!")
        elif response == "INVALID_CREDENTIALS":
            st.error("Invalid username or password!")
        else:
            st.error(f"Unknown authentication error: {response}")
        return False
    except Exception as e:
        st.error(f"Error during authentication: {str(e)}")
        print(f"Error details: {str(e)}")
        return False

def main():
    st_autorefresh(interval=2000, key="chat_autorefresh")
    st.title("💬 Chat Application")
    
    # Process messages from queue
    while not st.session_state.message_queue.empty():
        try:
            message = st.session_state.message_queue.get_nowait()
            print(f"Adding to messages: {message}")  # DEBUG
            st.session_state.messages.append(message)
        except queue.Empty:
            break
    
    # Connect to server
    if not st.session_state.connected:
        if st.button("Connect to server"):
            if connect_to_server():
                st.success("Connected to server!")
            else:
                st.error("Could not connect to server!")

    # Authentication form
    if st.session_state.connected and not st.session_state.username:
        st.write("### Login/Register")
        has_account = st.radio("Do you have an account?", ["Yes", "No"], key="auth_type")
        username = st.text_input("Username", key="auth_username")
        password = st.text_input("Password", type="password", key="auth_password")
        
        if st.button("Confirm", key="auth_submit"):
            if not username or not password:
                st.error("Please enter both username and password!")
            else:
                print("Starting login/registration process...")
                if handle_authentication(username, password, has_account):
                    st.rerun()

    # Chat interface
    if st.session_state.username:
        st.write(f"Welcome, {st.session_state.username}!")
        
        # Display messages in a container with custom styling
        chat_container = st.container()
        with chat_container:
            for message in st.session_state.messages:
                if message.startswith("(private)"):
                    st.markdown(f"<div style='color: purple; padding: 5px;'>{message}</div>", unsafe_allow_html=True)
                elif message.startswith("(") and ")" in message:
                    st.markdown(f"<div style='color: blue; padding: 5px;'>{message}</div>", unsafe_allow_html=True)
                else:
                    st.markdown(f"<div style='color: green; padding: 5px;'>{message}</div>", unsafe_allow_html=True)
        
        # Message form
        st.write("### Send Message")
        message_type = st.selectbox(
            "Message Type",
            ["General Chat", "Private Message", "Group Message"],
            key="message_type"
        )
        
        if message_type == "Private Message":
            recipient = st.text_input("Recipient", key="private_recipient")
            message = st.text_input("Message content", key="private_message")
            if st.button("Send", key="private_send"):
                if message and recipient:
                    msg = f"/msg {recipient} {message}"
                    st.session_state.client_socket.send(json.dumps({
                        "username": st.session_state.username,
                        "message": msg
                    }).encode())
                    st.rerun()
        
        elif message_type == "Group Message":
            group_action = st.selectbox(
                "Action",
                ["Create Group", "Join Group", "Send Group Message"],
                key="group_action"
            )
            
            if group_action == "Create Group":
                group_name = st.text_input("Group Name", key="create_group_name")
                if st.button("Create", key="create_group_button"):
                    if group_name:
                        msg = f"/create_group {group_name}"
                        st.session_state.client_socket.send(json.dumps({
                            "username": st.session_state.username,
                            "message": msg
                        }).encode())
                        st.rerun()
            
            elif group_action == "Join Group":
                group_name = st.text_input("Group Name", key="join_group_name")
                if st.button("Join", key="join_group_button"):
                    if group_name:
                        msg = f"/join_group {group_name}"
                        st.session_state.client_socket.send(json.dumps({
                            "username": st.session_state.username,
                            "message": msg
                        }).encode())
                        st.rerun()
            
            else:  # Send group message
                group_name = st.text_input("Group Name", key="group_msg_name")
                message = st.text_input("Message content", key="group_msg_content")
                if st.button("Send", key="group_msg_send"):
                    if message and group_name:
                        msg = f"/group_msg {group_name} {message}"
                        st.session_state.client_socket.send(json.dumps({
                            "username": st.session_state.username,
                            "message": msg
                        }).encode())
                        st.rerun()
        
        else:  # General chat
            message = st.text_input("Message content", key="general_message")
            if st.button("Send", key="general_send"):
                if message:
                    st.session_state.client_socket.send(json.dumps({
                        "username": st.session_state.username,
                        "message": message
                    }).encode())
                    st.rerun()

if __name__ == "__main__":
    main()

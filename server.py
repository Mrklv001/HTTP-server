import socket
import threading
import logging
from config import HTTP_PORT, HTTPS_PORT, USE_HTTPS
from routes import route_handlers
from utils.logger import setup_logger
from utils.http_parser import parse_request

setup_logger()


def handle_request(client_socket):
    request_data = b""
    while b"\r\n\r\n" not in request_data:
        chunk = client_socket.recv(1024)
        if not chunk:
            break
        request_data += chunk

    headers_end = request_data.find(b"\r\n\r\n")
    if headers_end == -1:
        client_socket.send(b"HTTP/1.1 400 Bad Request\r\n\r\n")
        return

    header_bytes = request_data[:headers_end].decode()
    method, path, version, headers = parse_request(header_bytes)

    handler = route_handlers.get(method, {}).get(path, None)

    if handler:
        response = handler(path, headers)
        client_socket.send(response)
    else:
        client_socket.send(b"HTTP/1.1 404 Not Found\r\n\r\n")
    client_socket.close()


def handle_connection(client_socket):
    try:
        handle_request(client_socket)
    finally:
        client_socket.close()


def http_redirect_server():
    http_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    http_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    http_socket.bind(('localhost', HTTP_PORT))
    http_socket.listen(5)
    logging.info(f"HTTP server running on http://localhost:{HTTP_PORT}")

    while True:
        client_socket, addr = http_socket.accept()
        data = client_socket.recv(1024).decode()
        if data:
            path = data.split(' ')[1]
            location = f"https://localhost:{HTTPS_PORT}{path}"
            response = (
                "HTTP/1.1 301 Moved Permanently\r\n"
                f"Location: {location}\r\n"
                "Connection: close\r\n"
                "\r\n"
            )
            client_socket.send(response.encode())
        client_socket.close()


def main():
    https_thread = threading.Thread(target=http_redirect_server, daemon=True)
    https_thread.start()

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(('localhost', HTTPS_PORT))
    server_socket.listen(5)

    logging.info(f"HTTPS server running on https://localhost:{HTTPS_PORT}")

    try:
        while True:
            client_socket, addr = server_socket.accept()
            logging.info(f"Connection from {addr}")
            thread = threading.Thread(target=handle_connection, args=(client_socket,))
            thread.start()
    except KeyboardInterrupt:
        logging.info("Server is shutting down.")
    finally:
        server_socket.close()
        logging.info("Server has been shut down.")


if __name__ == "__main__":
    main()

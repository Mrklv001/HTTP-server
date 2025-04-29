import socket
import threading
import argparse
import os
import gzip
import time


def parse_request(request_data):
    lines = request_data.split('\r\n')
    start_line = lines[0]
    method, path, version = start_line.split(' ')

    headers = {}
    for line in lines[1:]:
        if line == "":
            break
        if ": " in line:
            key, value = line.split(": ", 1)
            headers[key] = value

    return method, path, version, headers


def format_size(size):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024:
            return f"{size:.0f} {unit}"
        size /= 1024
    return f"{size:.0f} TB"


def list_directory_html(full_path, rel_path):
    items = os.listdir(full_path)
    rows = ""
    for name in sorted(items):
        item_path = os.path.join(full_path, name)
        href_path = os.path.join("/static", rel_path, name).replace("\\", "/")
        display_name = name + "/" if os.path.isdir(item_path) else name
        size = format_size(os.path.getsize(item_path)) if os.path.isfile(item_path) else "-"
        modified = time.strftime('%Y-%m-%d %H:%M', time.localtime(os.path.getmtime(item_path)))
        rows += f"<tr><td><a href='{href_path}'>{display_name}</a></td><td>{size}</td><td>{modified}</td></tr>"

    html = f"""
    <html>
    <head>
        <title>Index of /static/{rel_path}</title>
        <style>
            body {{ font-family: sans-serif; padding: 1rem; }}
            table {{ width: 100%; border-collapse: collapse; }}
            th, td {{ padding: 0.5rem; border-bottom: 1px solid #ccc; text-align: left; }}
            a {{ text-decoration: none; color: #0366d6; }}
            a:hover {{ text-decoration: underline; }}
        </style>
    </head>
    <body>
        <h2>Index of /static/{rel_path}</h2>
        <table>
            <tr><th>Name</th><th>Size</th><th>Last Modified</th></tr>
            {rows}
        </table>
    </body>
    </html>
    """
    return html.encode()


def get_response(path, headers, should_close=False):
    accept_encoding = headers.get("Accept-Encoding", "")
    supports_gzip = "gzip" in accept_encoding

    def add_common_headers(body, content_type):
        connection_header = "Connection: close" if should_close else "Connection: keep-alive"
        if supports_gzip:
            body = gzip.compress(body)
            headers = (
                f"Content-Type: {content_type}\r\n"
                f"Content-Encoding: gzip\r\n"
                f"Content-Length: {len(body)}\r\n"
                f"{connection_header}"
            )
        else:
            headers = (
                f"Content-Type: {content_type}\r\n"
                f"Content-Length: {len(body)}\r\n"
                f"{connection_header}"
            )
        return headers, body

    if path.startswith("/echo/"):
        body = path[len("/echo/"):].encode()
        header_section, body = add_common_headers(body, "text/plain")
        return f"HTTP/1.1 200 OK\r\n{header_section}\r\n\r\n".encode() + body

    if path == "/user-agent":
        body = headers.get("User-Agent", "").encode()
        header_section, body = add_common_headers(body, "text/plain")
        return f"HTTP/1.1 200 OK\r\n{header_section}\r\n\r\n".encode() + body

    if path.startswith("/files/"):
        filename = path[len("/files/"):]
        file_path = os.path.join(FILES_DIR, filename)

        if os.path.isfile(file_path):
            with open(file_path, "rb") as f:
                content = f.read()
            header_section, content = add_common_headers(content, "application/octet-stream")
            return f"HTTP/1.1 200 OK\r\n{header_section}\r\n\r\n".encode() + content
        else:
            return b"HTTP/1.1 404 Not Found\r\nConnection: close\r\n\r\n" if should_close else b"HTTP/1.1 404 Not Found\r\nConnection: keep-alive\r\n\r\n"

    if path.startswith("/static"):
        rel_path = path[len("/static/"):]
        full_path = os.path.join(FILES_DIR, rel_path)

        if os.path.isdir(full_path):
            body = list_directory_html(full_path, rel_path)
            header_section, body = add_common_headers(body, "text/html")
            return f"HTTP/1.1 200 OK\r\n{header_section}\r\n\r\n".encode() + body
        elif os.path.isfile(full_path):
            with open(full_path, "rb") as f:
                body = f.read()
            header_section, body = add_common_headers(body, "application/octet-stream")
            return f"HTTP/1.1 200 OK\r\n{header_section}\r\n\r\n".encode() + body
        else:
            return b"HTTP/1.1 404 Not Found\r\nConnection: close\r\n\r\n" if should_close else b"HTTP/1.1 404 Not Found\r\nConnection: keep-alive\r\n\r\n"

    if path == "/":
        return f"HTTP/1.1 200 OK\r\nContent-Length: 0\r\n{'Connection: close' if should_close else 'Connection: keep-alive'}\r\n\r\n".encode()

    return f"HTTP/1.1 404 Not Found\r\n{'Connection: close' if should_close else 'Connection: keep-alive'}\r\n\r\n".encode()


def handle_request(client_socket):
    request_data = b""
    while b"\r\n\r\n" not in request_data:
        chunk = client_socket.recv(1024)
        if not chunk:
            return False  # клиент закрыл соединение
        request_data += chunk

    headers_end = request_data.find(b"\r\n\r\n")
    if headers_end == -1:
        client_socket.send(b"HTTP/1.1 400 Bad Request\r\n\r\n")
        return False

    header_bytes = request_data[:headers_end].decode()
    method, path, version, headers = parse_request(header_bytes)

    connection_header = headers.get("Connection", "").lower()
    should_close = connection_header == "close"

    body = b""
    if method in ["POST", "PUT"]:
        content_length = int(headers.get("Content-Length", 0))
        body = request_data[headers_end + 4:]
        while len(body) < content_length:
            chunk = client_socket.recv(1024)
            if not chunk:
                return False
            body += chunk

        if path.startswith("/files/"):
            filename = path[len("/files/"):]
            file_path = os.path.join(FILES_DIR, filename)
            with open(file_path, "wb") as f:
                f.write(body)
            status = b"201 Created" if method == "POST" else b"200 OK"
            connection_line = b"Connection: close\r\n" if should_close else b"Connection: keep-alive\r\n"
            response = b"HTTP/1.1 " + status + b"\r\n" + connection_line + b"\r\n"
            client_socket.send(response)
            return not should_close

    elif method == "DELETE":
        if path.startswith("/files/"):
            filename = path[len("/files/"):]
            file_path = os.path.join(FILES_DIR, filename)
            if os.path.exists(file_path):
                os.remove(file_path)
                status = b"200 OK"
            else:
                status = b"404 Not Found"
            connection_line = b"Connection: close\r\n" if should_close else b"Connection: keep-alive\r\n"
            response = b"HTTP/1.1 " + status + b"\r\n" + connection_line + b"\r\n"
            client_socket.send(response)
            return not should_close

    elif method == "HEAD":
        response = get_response(path, headers, should_close)
        if b"\r\n\r\n" in response:
            headers_only = response.split(b"\r\n\r\n")[0] + b"\r\n\r\n"
            client_socket.send(headers_only)
        else:
            client_socket.send(response)
        return not should_close

    elif method == "GET":
        response = get_response(path, headers, should_close)
        client_socket.send(response)
        return not should_close

    client_socket.send(b"HTTP/1.1 405 Method Not Allowed\r\n\r\n")
    return not should_close


def handle_connection(client_socket):
    try:
        while True:
            if not handle_request(client_socket):
                break
    finally:
        client_socket.close()


parser = argparse.ArgumentParser()
parser.add_argument('--directory', type=str, required=False, default='.')
args = parser.parse_args()
FILES_DIR = args.directory


def main():
    server_socket = socket.create_server(("localhost", 4221))
    print("Server is running on port 4221...")

    try:
        while True:
            client_socket, addr = server_socket.accept()
            print(f"Connection from {addr} has been established")

            thread = threading.Thread(target=handle_connection, args=(client_socket,))
            thread.start()

    except KeyboardInterrupt:
        print("\nServer is shutting down.")
    finally:
        server_socket.close()
        print("Server has been shut down.")


if __name__ == "__main__":
    main()

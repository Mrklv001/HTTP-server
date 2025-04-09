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
    for unit in ['B','KB','MB','GB']:
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


def get_response(path, headers):
    accept_encoding = headers.get("Accept-Encoding", "")
    supports_gzip = "gzip" in accept_encoding

    def add_common_headers(body, content_type):
        if supports_gzip:
            body = gzip.compress(body)
            headers = f"Content-Type: {content_type}\r\nContent-Encoding: gzip\r\nContent-Length: {len(body)}"
        else:
            headers = f"Content-Type: {content_type}\r\nContent-Length: {len(body)}"
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
            return b"HTTP/1.1 404 Not Found\r\n\r\n"

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
            return b"HTTP/1.1 404 Not Found\r\n\r\n"

    if path == "/":
        return b"HTTP/1.1 200 OK\r\n\r\n"

    return b"HTTP/1.1 404 Not Found\r\n\r\n"


def handle_request(client_socket):
    request_data = b""
    while b"\r\n\r\n" not in request_data:
        request_data += client_socket.recv(1024)

    headers_end = request_data.find(b"\r\n\r\n")
    header_bytes = request_data[:headers_end].decode()
    method, path, version, headers = parse_request(header_bytes)

    body = b""
    if method == "POST":
        content_length = int(headers.get("Content-Length", 0))
        body = request_data[headers_end+4:]
        while len(body) < content_length:
            body += client_socket.recv(1024)

        if path.startswith("/files/"):
            filename = path[len("/files/"):] 
            file_path = os.path.join(FILES_DIR, filename)
            with open(file_path, "wb") as f:
                f.write(body)
            response = b"HTTP/1.1 201 Created\r\n\r\n"
            client_socket.send(response)
            return

    response = get_response(path, headers)
    client_socket.send(response)


def handle_connection(client_socket):
    try:
        handle_request(client_socket)
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
import socket
import ssl
import threading
import argparse
import os
import gzip
import time
import logging
from urllib.parse import unquote

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)


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
    return method, unquote(path), version, headers


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
    <head><title>Index of /static/{rel_path}</title></head>
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


def is_path_safe(base_dir, target_path):
    abs_base = os.path.abspath(base_dir)
    abs_target = os.path.abspath(target_path)
    return abs_target.startswith(abs_base)


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
        if not is_path_safe(FILES_DIR, file_path):
            return b"HTTP/1.1 403 Forbidden\r\n\r\n"

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
        if not is_path_safe(FILES_DIR, full_path):
            return b"HTTP/1.1 403 Forbidden\r\n\r\n"

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
        return b"HTTP/1.1 200 OK\r\n\r\nWelcome to the secure HTTPS server!\n"

    return b"HTTP/1.1 404 Not Found\r\n\r\n"


def handle_request(client_socket, addr):
    try:
        while True:
            request_data = b""
            while b"\r\n\r\n" not in request_data:
                chunk = client_socket.recv(1024)
                if not chunk:
                    return
                request_data += chunk

            headers_end = request_data.find(b"\r\n\r\n")
            if headers_end == -1:
                client_socket.send(b"HTTP/1.1 400 Bad Request\r\n\r\n")
                return

            header_bytes = request_data[:headers_end].decode()
            method, path, version, headers = parse_request(header_bytes)
            keep_alive = headers.get("Connection", "").lower() == "keep-alive"

            logging.info(f"{addr[0]} {method} {path}")

            body = b""
            if method in ["POST", "PUT"]:
                content_length = int(headers.get("Content-Length", 0))
                body = request_data[headers_end + 4:]
                while len(body) < content_length:
                    body += client_socket.recv(1024)

                filename = path[len("/files/"):] if path.startswith("/files/") else None
                if filename:
                    file_path = os.path.join(FILES_DIR, filename)
                    if is_path_safe(FILES_DIR, file_path):
                        with open(file_path, "wb") as f:
                            f.write(body)
                        status = b"201 Created" if method == "POST" else b"200 OK"
                        response = b"HTTP/1.1 " + status + b"\r\n\r\n"
                    else:
                        response = b"HTTP/1.1 403 Forbidden\r\n\r\n"
                    client_socket.send(response)
                    if not keep_alive:
                        return
                    continue

            elif method == "DELETE":
                filename = path[len("/files/"):] if path.startswith("/files/") else None
                if filename:
                    file_path = os.path.join(FILES_DIR, filename)
                    if is_path_safe(FILES_DIR, file_path) and os.path.exists(file_path):
                        os.remove(file_path)
                        response = b"HTTP/1.1 200 OK\r\n\r\n"
                    else:
                        response = b"HTTP/1.1 404 Not Found\r\n\r\n"
                    client_socket.send(response)
                    if not keep_alive:
                        return
                    continue

            elif method == "HEAD":
                response = get_response(path, headers)
                if b"\r\n\r\n" in response:
                    headers_only = response.split(b"\r\n\r\n")[0] + b"\r\n\r\n"
                    client_socket.send(headers_only)
                else:
                    client_socket.send(response)
                if not keep_alive:
                    return
                continue

            elif method == "GET":
                response = get_response(path, headers)
                if keep_alive:
                    response = response.replace(b"HTTP/1.1 200 OK", b"HTTP/1.1 200 OK\r\nConnection: keep-alive", 1)
                client_socket.send(response)
                if not keep_alive:
                    return
            else:
                client_socket.send(b"HTTP/1.1 405 Method Not Allowed\r\n\r\n")
                return
    finally:
        client_socket.close()


def handle_connection(client_socket, addr):
    try:
        handle_request(client_socket, addr)
    except Exception as e:
        logging.error(f"Error handling request from {addr}: {e}")
    finally:
        client_socket.close()


parser = argparse.ArgumentParser()
parser.add_argument('--directory', type=str, default='.')
args = parser.parse_args()
FILES_DIR = args.directory


def main():
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile='cert.pem', keyfile='key.pem')

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(('localhost', 8443))
    server_socket.listen(5)

    server_socket = context.wrap_socket(server_socket, server_side=True)

    logging.info("HTTPS Server is running on https://localhost:8443")

    try:
        while True:
            client_socket, addr = server_socket.accept()
            thread = threading.Thread(target=handle_connection, args=(client_socket, addr))
            thread.start()
    except KeyboardInterrupt:
        logging.info("Shutting down...")
    finally:
        server_socket.close()


if __name__ == "__main__":
    main()


def http_redirect_server():
    http_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    http_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    http_socket.bind(('localhost', 8080))
    http_socket.listen(5)
    logging.info("Redirect HTTP server running on http://localhost:8080")

    try:
        while True:
            client_socket, addr = http_socket.accept()
            data = client_socket.recv(1024).decode()
            if data:
                try:
                    path = data.split(' ')[1]
                    location = f"https://localhost:8443{path}"
                    response = (
                        "HTTP/1.1 301 Moved Permanently\r\n"
                        f"Location: {location}\r\n"
                        "Connection: close\r\n"
                        "\r\n"
                    )
                    client_socket.send(response.encode())
                except Exception as e:
                    logging.warning(f"Bad request from {addr}: {e}")
            client_socket.close()
    except Exception as e:
        logging.error(f"Redirect server error: {e}")
    finally:
        http_socket.close()


if __name__ == "__main__":
    threading.Thread(target=http_redirect_server, daemon=True).start()
    main()

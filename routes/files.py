import os
from utils.gzip_utils import compress_gzip
import config

from utils.http_parser import format_size
import time


def handle_files(path, headers):
    if path.startswith("/files/"):
        filename = path[len("/files/"):]
        file_path = os.path.join(config.FILES_DIR, filename)

        if os.path.isfile(file_path):
            with open(file_path, "rb") as f:
                content = f.read()
            return compress_gzip(content, "application/octet-stream")
        else:
            return b"HTTP/1.1 404 Not Found\r\n\r\n"
    return b"HTTP/1.1 405 Method Not Allowed\r\n\r\n"


def list_directory_html(full_path, rel_path):
    items = os.listdir(full_path)
    rows = []
    for name in sorted(items):
        item_path = os.path.join(full_path, name)
        href_path = f"/static/{rel_path}/{name}"
        display_name = name + "/" if os.path.isdir(item_path) else name
        size = format_size(os.path.getsize(item_path)) if os.path.isfile(item_path) else "-"
        modified = time.strftime('%Y-%m-%d %H:%M', time.localtime(os.path.getmtime(item_path)))

        item = {
            "name": display_name,
            "href": href_path,
            "size": size,
            "modified": modified,
            "is_directory": os.path.isdir(item_path)
        }
        rows.append(item)

    html_content = render_template('directory.html', rel_path=rel_path, items=rows)
    return html_content

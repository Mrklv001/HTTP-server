import os
from utils.gzip_utils import compress_gzip
from utils.http_parser import format_size
import time

def list_directory_html(full_path, rel_path):
    items = os.listdir(full_path)
    rows = ""
    for name in sorted(items):
        item_path = os.path.join(full_path, name)
        href_path = f"/static/{rel_path}/{name}"
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

def handle_static(path, headers):
    rel_path = path[len("/static/"):]
    full_path = os.path.join(config.FILES_DIR, rel_path)

    if os.path.isdir(full_path):
        body = list_directory_html(full_path, rel_path)
        return compress_gzip(body, "text/html")
    elif os.path.isfile(full_path):
        with open(full_path, "rb") as f:
            body = f.read()
        return compress_gzip(body, "application/octet-stream")
    else:
        return b"HTTP/1.1 404 Not Found\r\n\r\n"

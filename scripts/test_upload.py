"""Test the /api/upload_scene endpoint by uploading a local USD file."""
import urllib.request
import sys

boundary = '----WebKitFormBoundary7MA4YWxk'
file_path = sys.argv[1] if len(sys.argv) > 1 else r'C:\Users\Rob\dev\rtx-viewer-demo-pro\usd_samples\cube_stacks_scene.usda'
filename = file_path.split('\\')[-1]

with open(file_path, 'rb') as f:
    body = (
        f'--{boundary}\r\n'
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f'Content-Type: application/octet-stream\r\n\r\n'
    ).encode() + f.read() + f'\r\n--{boundary}--\r\n'.encode()

req = urllib.request.Request('http://localhost:8080/api/upload_scene', data=body, method='POST')
req.add_header('Content-Type', f'multipart/form-data; boundary={boundary}')
with urllib.request.urlopen(req) as res:
    print(res.read().decode())

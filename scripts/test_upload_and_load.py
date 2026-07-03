"""Full pipeline test: upload a USD file via HTTP and load it over WebSocket."""
import asyncio
import json
import urllib.request
import websockets


def upload_file(file_path: str) -> str:
    boundary = '----WebKitFormBoundary7MA4YWxk'
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
        data = json.loads(res.read().decode())
    return data['path']


async def main():
    file_path = r'C:\Users\Rob\dev\rtx-viewer-demo-pro\usd_samples\cube_stacks_scene.usda'
    print(f"Uploading {file_path}...")
    uploaded_path = upload_file(file_path)
    print(f"Uploaded to: {uploaded_path}")

    async with websockets.connect('ws://localhost:8080/ws') as ws:
        print("Loading via WebSocket...")
        await ws.send(json.dumps({'cmd': 'load', 'path': uploaded_path}))
        msg = await ws.recv()
        print('Load response:', msg)

        await ws.send(json.dumps({'cmd': 'list_prims'}))
        msg = await ws.recv()
        print('List response:', msg)
        data = json.loads(msg)
        print(f"Prims: {len(data.get('prims', []))} found")
        for p in data.get('prims', [])[:5]:
            print('  ', p)

        for i in range(20):
            msg = await ws.recv()
            if isinstance(msg, bytes):
                print(f"Received frame: {len(msg)} bytes")
                break
            else:
                print('Text:', msg)


asyncio.run(main())

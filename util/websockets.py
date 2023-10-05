from fastapi import WebSocket

class ConnectionManager:
    """
    Adapted from https://fastapi.tiangolo.com/advanced/websockets/
    """
    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self.new_id = 0

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        self.new_id += 1
        print(f"New Connection -> {websocket}")
        return self.new_id

    def disconnect(self, websocket: WebSocket):
        print(f"Disconnect -> {websocket}")
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        print(f"Message ({message}) -> {websocket}")
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        print(f"Broadcast -> {message}"
        for connection in self.active_connections:
            await connection.send_text(message)
import asyncio
import json
import websockets
import sys

async def test_chat():
    uri = "ws://localhost:8000/api/v1/chat/ws/chat/test_session"
    # Note: Replace with a valid token if auth is enabled and mandatory for testing
    # For now, assuming we might need to skip auth or use a dummy if possible
    
    payload = {
        "message": "what is MCP and do not give me any image or screen shot",
        "role": "Teacher AI"
    }

    try:
        async with websockets.connect(uri) as websocket:
            await websocket.send(json.dumps(payload))
            print(f"Sent: {payload['message']}")

            full_text = ""
            has_sources = False
            
            while True:
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                    data = json.loads(message)
                    
                    if data["type"] == "chunk":
                        full_text += data.get("content", "")
                        if "sources" in data:
                            has_sources = True
                            print(f"Received sources: {len(data['sources'])}")
                    
                    elif data["type"] == "done":
                        print("Stream finished.")
                        break
                    
                    elif data["type"] == "error":
                        print(f"Error received: {data.get('content') or data.get('reason')}")
                        break
                except asyncio.TimeoutError:
                    print("Timeout waiting for response")
                    break

            print("\n--- Full Response ---")
            print(full_text)
            print("---------------------\n")
            
            if full_text and "!" in full_text and "[" in full_text and "]" in full_text:
                print("SUCCESS: Visual markdown detected in response.")
            elif has_sources:
                 print("SUCCESS: Sources with potential images detected.")
            else:
                 print("WARNING: No visual reference detected in text response.")

            if len(full_text) > 50:
                print("SUCCESS: Substantial text response received.")
            else:
                print("FAILURE: Text response too short.")

    except Exception as e:
        print(f"Connection failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_chat())

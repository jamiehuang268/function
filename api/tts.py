from http.server import BaseHTTPRequestHandler
import asyncio
import edge_tts
import json
import urllib.parse
import io


async def generate_speech(text, voice="en-US-AriaNeural", rate="-10%", pitch="-2Hz"):
    """使用 edge-tts 生成语音，返回 bytes"""
    communicate = edge_tts.Communicate(
        text=text,
        voice=voice,
        rate=rate,
        pitch=pitch
    )

    audio_data = io.BytesIO()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_data.write(chunk["data"])

    return audio_data.getvalue()


class handler(BaseHTTPRequestHandler):

    def do_GET(self):
        """GET 请求：通过 URL 参数传文本"""
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        text = params.get("text", [""])[0]
        voice = params.get("voice", ["en-US-AriaNeural"])[0]
        rate = params.get("rate", ["-10%"])[0]
        pitch = params.get("pitch", ["-2Hz"])[0]

        if not text:
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "error": "缺少 text 参数",
                "usage": "/api/tts?text=Hello+world&voice=en-US-AriaNeural&rate=-10%&pitch=-2Hz",
                "voices": {
                    "美式女声": "en-US-AriaNeural",
                    "美式男声": "en-US-GuyNeural",
                    "英式女声": "en-GB-SoniaNeural",
                    "英式男声": "en-GB-RyanNeural",
                    "中文女声": "zh-CN-XiaoxiaoNeural",
                    "中文男声": "zh-CN-YunxiNeural"
                }
            }).encode())
            return

        self._process_tts(text, voice, rate, pitch)

    def do_POST(self):
        """POST 请求：通过 JSON body 传文本（支持长文本）"""
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "无效的 JSON"}).encode())
            return

        text = data.get("text", "")
        voice = data.get("voice", "en-US-AriaNeural")
        rate = data.get("rate", "-10%")
        pitch = data.get("pitch", "-2Hz")

        if not text:
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "缺少 text 字段"}).encode())
            return

        self._process_tts(text, voice, rate, pitch)

    def _process_tts(self, text, voice, rate, pitch):
        """生成语音并返回"""
        try:
            # 运行异步函数
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            audio_bytes = loop.run_until_complete(
                generate_speech(text, voice, rate, pitch)
            )
            loop.close()

            if not audio_bytes:
                raise Exception("生成的音频为空")

            # 返回 MP3 音频
            self.send_response(200)
            self.send_header("Content-Type", "audio/mpeg")
            self.send_header("Content-Disposition", 'attachment; filename="speech.mp3"')
            self.send_header("Content-Length", str(len(audio_bytes)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(audio_bytes)

        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "error": str(e)
            }).encode())

    def do_OPTIONS(self):
        """处理 CORS 预检请求"""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Allow-Headers", "Content-Type")
        self.end_headers()

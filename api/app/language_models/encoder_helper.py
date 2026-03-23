import base64
import json


class BytesEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, bytes):
            # Option 1: Decode if bytes represent UTF-8 text:
            # return obj.decode("utf-8")
            # Option 2: Base64 encode the bytes (suitable for arbitrary binary data):
            return base64.b64encode(obj).decode("utf-8")
        return super().default(obj)

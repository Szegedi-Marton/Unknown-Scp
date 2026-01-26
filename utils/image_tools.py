import base64
from PIL import Image
from io import BytesIO

def save_base64_image(data_url, filename):
    image_data = data_url.split(',')[1]
    image_bytes = base64.b64decode(image_data)
    image = Image.open(BytesIO(image_bytes))
    image.save(filename)
    return filename

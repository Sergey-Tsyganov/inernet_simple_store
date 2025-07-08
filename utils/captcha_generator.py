from PIL import Image, ImageDraw, ImageFont
import random
import string


def generate_captcha():
    letters = string.ascii_uppercase + string.digits
    captcha_text = ''.join(random.choice(letters) for _ in range(6))

    image = Image.new('RGB', (150, 50), color=(255, 255, 255))
    font = ImageFont.load_default()
    draw = ImageDraw.Draw(image)
    draw.text((10, 10), captcha_text, font=font, fill=(0, 0, 0))

    path = 'static/captcha/current_captcha.png'
    image.save(path)
    return captcha_text, path
from pathlib import Path
from PIL import Image, ImageDraw

root = Path(__file__).resolve().parents[1]
image = Image.new("RGBA", (256, 256), (23, 105, 224, 255))
draw = ImageDraw.Draw(image)
draw.rounded_rectangle((42, 46, 214, 204), radius=22, fill=(255, 255, 255, 255))
draw.ellipse((72, 76, 184, 148), fill=(228, 239, 253, 255), outline=(23, 105, 224, 255), width=10)
draw.arc((72, 110, 184, 178), 0, 180, fill=(23, 105, 224, 255), width=10)
draw.line((160, 164, 208, 212), fill=(19, 138, 91, 255), width=16)
draw.line((208, 212, 228, 192), fill=(19, 138, 91, 255), width=16)
output = root / "assets" / "app.ico"
output.parent.mkdir(exist_ok=True)
image.save(output, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print(output)

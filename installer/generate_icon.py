from pathlib import Path

from PIL import Image, ImageDraw


SIZE = 256
image = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
draw = ImageDraw.Draw(image)

draw.rounded_rectangle((8, 8, 248, 248), radius=46, fill=(17, 24, 32, 255), outline=(246, 163, 59, 255), width=10)
draw.rounded_rectangle((40, 42, 216, 214), radius=22, fill=(24, 35, 46, 255), outline=(86, 106, 122, 255), width=5)

# A compact overhead-panel switch and annunciator motif that remains readable
# at Windows taskbar sizes.
draw.rounded_rectangle((68, 65, 188, 115), radius=8, fill=(246, 163, 59, 255))
draw.rounded_rectangle((80, 76, 176, 104), radius=4, fill=(18, 29, 39, 255))
draw.ellipse((98, 137, 158, 197), fill=(9, 14, 20, 255), outline=(246, 163, 59, 255), width=7)
draw.line((128, 165, 128, 129), fill=(246, 163, 59, 255), width=12)
draw.ellipse((119, 120, 137, 138), fill=(246, 163, 59, 255))

target = Path(__file__).with_name("overheadlink.ico")
image.save(target, format="ICO", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print(target)

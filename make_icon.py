import os
from PIL import Image, ImageDraw

def create_cool_icon():
    sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
    images = []

    for width, height in sizes:
        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        scale = width / 256.0

        # Background: Modern Rounded Box / Shield
        # Dark Obsidian background with subtle cyber blue glow
        padding = int(12 * scale)
        r = int(48 * scale)
        draw.rounded_rectangle(
            [padding, padding, width - padding, height - padding],
            radius=r,
            fill=(15, 23, 42, 255), # #0f172a slate-900
            outline=(56, 189, 248, 255), # #38bdf8 neon cyan
            width=max(1, int(8 * scale))
        )

        # Folder Tab
        tab_x0 = int(40 * scale)
        tab_y0 = int(55 * scale)
        tab_x1 = int(115 * scale)
        tab_y1 = int(85 * scale)
        draw.rounded_rectangle(
            [tab_x0, tab_y0, tab_x1, tab_y1],
            radius=max(1, int(10 * scale)),
            fill=(30, 41, 59, 255), # #1e293b
            outline=(56, 189, 248, 200),
            width=max(1, int(4 * scale))
        )

        # Folder Body
        f_x0 = int(40 * scale)
        f_y0 = int(75 * scale)
        f_x1 = int(216 * scale)
        f_y1 = int(195 * scale)
        draw.rounded_rectangle(
            [f_x0, f_y0, f_x1, f_y1],
            radius=max(2, int(20 * scale)),
            fill=(20, 30, 50, 255),
            outline=(14, 165, 233, 255), # #0ea5e9
            width=max(1, int(6 * scale))
        )

        # X-Ray / Tech Laser Grid lines
        laser_y = int(135 * scale)
        draw.line(
            [(f_x0 + int(15 * scale), laser_y), (f_x1 - int(15 * scale), laser_y)],
            fill=(6, 182, 212, 180),
            width=max(1, int(3 * scale))
        )

        # Glowing Neon Checkmark / Sync Arrow in the center
        # Arrow / Checkmark points:
        p1 = (int(85 * scale), int(135 * scale))
        p2 = (int(115 * scale), int(165 * scale))
        p3 = (int(180 * scale), int(100 * scale))
        
        # Glow layer
        draw.line([p1, p2, p3], fill=(16, 185, 129, 100), width=max(1, int(18 * scale)), joint="round")
        # Main neon emerald checkmark
        draw.line([p1, p2, p3], fill=(52, 211, 153, 255), width=max(1, int(10 * scale)), joint="round")
        # Inner white bright core
        draw.line([p1, p2, p3], fill=(240, 253, 250, 255), width=max(1, int(4 * scale)), joint="round")

        # Cyber dot at top right
        dot_r = int(14 * scale)
        dot_x = int(195 * scale)
        dot_y = int(55 * scale)
        draw.ellipse([dot_x - dot_r, dot_y - dot_r, dot_x + dot_r, dot_y + dot_r], fill=(56, 189, 248, 255))
        draw.ellipse([dot_x - int(6 * scale), dot_y - int(6 * scale), dot_x + int(6 * scale), dot_y + int(6 * scale)], fill=(255, 255, 255, 255))

        images.append(img)

    # Save multi-size ICO
    ico_path = "app_icon.ico"
    png_path = "app_icon.png"
    images[0].save(png_path, format="PNG")
    images[0].save(ico_path, format="ICO", sizes=[(im.width, im.height) for im in images])
    print(f"Generated {ico_path} and {png_path} successfully!")

if __name__ == "__main__":
    create_cool_icon()

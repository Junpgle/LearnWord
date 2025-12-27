from PIL import Image, ImageDraw, ImageFont, ImageFilter


def create_icon():
    # 1. 设置尺寸和颜色
    size = (256, 256)
    bg_color = "#0078d7"  # 您的主题蓝色
    text_color = "white"

    # 2. 创建画布 (RGBA 支持透明背景，但在 ico 中我们通常做成圆角或方形)
    # 为了 Windows 风格，我们做一个全填充的圆角矩形背景
    img = Image.new('RGBA', size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 3. 画圆角矩形背景
    rect_coords = [10, 10, 246, 246]
    radius = 40
    draw.rounded_rectangle(rect_coords, radius=radius, fill=bg_color)

    # 4. 画简单的书本形状 (左半边和右半边)
    # 书的左页
    draw.polygon([(60, 80), (120, 80), (120, 180), (60, 180)], fill="#339af0")
    # 书的右页
    draw.polygon([(128, 80), (188, 80), (188, 180), (128, 180)], fill="#66b3f5")

    # 5. 画文字 "L" (如果没有合适的字体文件，就用线条画)
    # 这里我们直接画一个粗线条的 L
    l_color = "white"
    # L 的竖线
    draw.rectangle([90, 100, 110, 160], fill=l_color)
    # L 的横线
    draw.rectangle([90, 145, 140, 160], fill=l_color)

    # 6. 保存为 icon.ico
    # 保存包含多种尺寸的 ICO 文件，以适应不同的显示环境 (桌面、文件列表等)
    img.save('icon.ico', format='ICO', sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])

    print("✅ 图标已生成: icon.ico")


if __name__ == "__main__":
    try:
        create_icon()
    except ImportError:
        print("请先安装 Pillow 库: pip install Pillow")
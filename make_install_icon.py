from PIL import Image, ImageDraw


def create_setup_icon():
    # 1. 设置尺寸
    size = (256, 256)
    # 使用稍微深一点的蓝色，或者保持品牌色
    bg_color = "#0078d7"
    arrow_color = "white"

    # 2. 创建画布
    img = Image.new('RGBA', size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 3. 画背景：圆角矩形 (代表安装包文件)
    # 这里画一个稍微扁一点的盒子形状，或者保持标准图标形状
    rect_coords = [20, 20, 236, 236]
    draw.rounded_rectangle(rect_coords, radius=40, fill=bg_color)

    # 4. 画一个 "硬盘/底座" 的线条 (表示安装到底座)
    draw.rectangle([70, 190, 186, 210], fill=arrow_color)

    # 5. 画向下的大箭头 (表示 Installing)
    # 箭头的一竖
    draw.rectangle([108, 60, 148, 140], fill=arrow_color)
    # 箭头的三角形头
    # 左点(78, 140), 右点(178, 140), 下尖点(128, 185)
    draw.polygon([(78, 140), (178, 140), (128, 185)], fill=arrow_color)

    # 6. 保存为 setup_icon.ico
    img.save('setup_icon.ico', format='ICO', sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])

    print("✅ 安装包图标已生成: setup_icon.ico")


if __name__ == "__main__":
    try:
        create_setup_icon()
    except ImportError:
        print("请先安装 Pillow 库: pip install Pillow")
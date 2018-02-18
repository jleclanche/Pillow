import lzma
import struct
from io import BytesIO

from . import Image, ImageFile


SC_TEX_RGBA = 0  # RGBA
SC_TEX_RGBA4444 = 2  # RGBA;4B
SC_TEX_RGB565 = 4  # RGB;16
SC_TEX_LA = 6  # LA
SC_TEX_L = 10  # L


def _fix_lzma_header(fp):
    return fp.read(9) + b"\0\0\0\0" + fp.read()


def pixel_to_rgba(pixel, type):
    if type == SC_TEX_RGBA:
        return struct.unpack("4B", pixel)
    elif type == SC_TEX_RGBA4444:
        pixel, = struct.unpack("<H", pixel)
        r = ((pixel >> 12) & 0xF) << 4
        g = ((pixel >> 8) & 0xF) << 4
        b = ((pixel >> 4) & 0xF) << 4
        a = ((pixel >> 0) & 0xF) << 4
        return r, g, b, a
    elif type == SC_TEX_RGB565:
        pixel, = struct.unpack("<H", pixel)
        r = ((pixel >> 11) & 0x1F) << 3
        g = ((pixel >> 5) & 0x3F) << 2
        b = (pixel & 0x1F) << 3
        return r, g, b
    elif type == SC_TEX_LA:
        pixel, = struct.unpack("<H", pixel)
        l = pixel >> 8
        a = pixel & 0xFF
        return l, a
    elif type == SC_TEX_L:
        l, = struct.unpack("<B", pixel)
        return l, l, l


def fix_pixels(img, pixels):
    width, height = img.size
    pix = img.load()
    i = 0

    for l in range(height // 32):  # block of 32 lines
        # normal 32-pixels blocks
        for k in range(width // 32):  # 32-pixels blocks in a line
            for j in range(32):  # line in a multi line block
                for h in range(32):  # pixels in a block
                    x = h + (k * 32)
                    y = j + (l * 32)
                    pix[x, y] = pixels[i]
                    i += 1

        # line end blocks
        for j in range(32):
            for h in range(width % 32):
                x = h + (width - (width % 32))
                y = j + (l * 32)
                pix[x, y] = pixels[i]
                i += 1

    # final lines
    for k in range(width // 32):  # 32-pixels blocks in a line
        for j in range(height % 32):  # line in a multi line block
            for h in range(32):  # pixels in a 32-pixels-block
                x = h + (k * 32)
                y = j + (height - (height % 32))
                pix[x, y] = pixels[i]
                i += 1

    # line end blocks
    for j in range(height % 32):
        for h in range(width % 32):
            x = h + (width - (width % 32))
            y = j + (height - (height % 32))
            pix[x, y] = pixels[i]
            i += 1


class ScTexImageFile(ImageFile.ImageFile):
    format = "SCTEX"
    format_description = "SuperCell Texture"

    magic = b"SC\0\0"

    def _open(self):
        self.mode = "RGBA"

        self.fp.read(26)  # Skip header
        compressed_data = _fix_lzma_header(self.fp)
        decompressed_data = lzma.LZMADecompressor().decompress(compressed_data)
        fp = BytesIO(decompressed_data)

        file_type, = struct.unpack("<b", fp.read(1))
        file_size, = struct.unpack("<I", fp.read(4))
        pixel_format, = struct.unpack("<b", fp.read(1))
        self.size = struct.unpack("<HH", fp.read(4))

        if file_type not in (27, 28):
            raise NotImplementedError("Unsupported file type %r" % (file_type))

        if pixel_format == SC_TEX_RGBA:
            pixel_size = 4
        elif pixel_format == SC_TEX_RGBA4444:
            pixel_size = 2
        elif pixel_format == SC_TEX_RGB565:
            pixel_size = 2
        elif pixel_format == SC_TEX_LA:
            pixel_size = 2
        elif pixel_format == SC_TEX_L:
            pixel_size = 1
        else:
            raise NotImplementedError(
                "Unknown pixel format %r" % (pixel_format)
            )

        pixels = []
        for y in range(self.size[1]):
            for x in range(self.size[0]):
                pixel_data = fp.read(pixel_size)
                pixels.append(pixel_to_rgba(pixel_data, pixel_format))

        # Now to fix pixel positions
        # Create a new canvas image
        self.tile = []
        canvas = Image.new("RGBA", self.size)
        fix_pixels(canvas, pixels)
        self.im = canvas.im


Image.register_open(
    ScTexImageFile.format, ScTexImageFile,
    lambda p: p[:4] == ScTexImageFile.magic
)
Image.register_extension(ScTexImageFile.format, "_tex.sc")

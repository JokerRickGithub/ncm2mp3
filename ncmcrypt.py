import struct
import base64
import json
from Crypto.Cipher import AES
import os

# ===================== 核心常量定义 =====================
# 网易云音乐公开的固定解密密钥（通过逆向工程获得）
# CORE_KEY：用于解密RC4核心密钥
CORE_KEY = bytes([0x68, 0x7A, 0x48, 0x52, 0x41, 0x6D, 0x73, 0x6F, 0x35, 0x6B, 0x49, 0x6E, 0x62, 0x61, 0x78, 0x57])
# MODIFY_KEY：用于解密歌曲元数据（歌手、专辑等）
MODIFY_KEY = bytes([0x23, 0x31, 0x34, 0x6C, 0x6A, 0x6B, 0x5F, 0x21, 0x5C, 0x5D, 0x26, 0x30, 0x55, 0x3C, 0x27, 0x28])
# PNG文件魔数，用于识别专辑封面格式
PNG_MAGIC = bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A])


# ===================== 底层算法函数 =====================
def _aes_ecb_decrypt(key: bytes, data: bytes) -> bytes:
    """
    AES-128-ECB模式解密，自动处理PKCS7填充
    :param key: AES解密密钥（16字节）
    :param data: 待解密的密文
    :return: 解密后的明文
    """
    # 创建AES-ECB解密器
    aes = AES.new(key, AES.MODE_ECB)
    # 执行解密
    out = aes.decrypt(data)
    # 处理PKCS7填充：取最后一个字节作为填充长度
    pad = out[-1]
    if pad > 16:  # 填充长度不可能超过16（AES块大小）
        pad = 0
    if pad:
        return out[:-pad]  # 去除填充字节
    return out


def _build_key_box(key: bytes) -> bytearray:
    """
    构建NCM定制的RC4密钥流S盒（核心解密算法）
    这是NCM加密的核心：用RC4密钥生成256字节的密钥盒，后续音频解密全靠它
    :param key: RC4密钥（从AES解密得到）
    :return: 256字节的密钥盒（S-box）
    """
    key_len = len(key)
    # 初始化S盒：0-255的顺序数组
    box = bytearray(range(256))
    last_byte = 0
    key_offset = 0
    
    # 打乱S盒（NCM定制的打乱规则，逆向自官方客户端）
    for i in range(256):
        swap = box[i]
        # 计算交换位置
        c = (swap + last_byte + key[key_offset]) & 0xff
        # 循环使用密钥
        key_offset += 1
        if key_offset >= key_len:
            key_offset = 0
        # 交换S盒中的两个元素
        box[i] = box[c]
        box[c] = swap
        last_byte = c
    
    return box


# ===================== 元数据解析类 =====================
class NeteaseMusicMetadata:
    """解析并存储NCM文件中的歌曲元数据（歌名、歌手、专辑等）"""
    def __init__(self, raw: dict):
        if not raw:
            self.name = None
            self.album = None
            self.artist = None
            self.bitrate = None
            self.duration = None
            self.format = None
            return

        # 从JSON中提取元数据
        self.name = raw.get('musicName')       # 歌曲名
        self.album = raw.get('album')           # 专辑名
        # 解析歌手信息（歌手是一个嵌套数组）
        artist = raw.get('artist')
        if artist:
            parts = []
            for a in artist:
                if isinstance(a, list) and len(a) > 0:
                    parts.append(a[0])
            self.artist = '/'.join(parts)       # 多个歌手用/连接
        else:
            self.artist = None
        self.bitrate = raw.get('bitrate')       # 比特率
        self.duration = raw.get('duration')     # 时长（毫秒）
        self.format = raw.get('format')         # 原始格式（mp3/flac）


# ===================== 核心解密类 =====================
class NeteaseCrypt:
    MP3 = 'mp3'
    FLAC = 'flac'

    def __init__(self, path: str):
        """
        初始化NCM解密器，按字节解析NCM文件结构
        :param path: NCM文件路径
        """
        self.filepath = path
        # 打开NCM文件（二进制只读模式）
        self._f = open(path, 'rb')
        
        # ========== 第一步：验证NCM文件头 ==========
        if not self._is_ncm_file():
            raise ValueError('Not netease protected file')

        # ========== 第二步：跳过固定间隙（2字节） ==========
        self._f.seek(2, os.SEEK_CUR)

        # ========== 第三步：读取并解密RC4核心密钥 ==========
        # 1. 读取密钥块长度（4字节小端无符号整数）
        n_bytes = self._f.read(4)
        if len(n_bytes) < 4:
            raise ValueError('Broken NCM file')
        (n,) = struct.unpack('<I', n_bytes)
        if n <= 0:
            raise ValueError('Broken NCM file')

        # 2. 读取加密的密钥块
        keydata = bytearray(self._f.read(n))
        # 3. 第一层解密：逐字节异或0x64（NCM的简单混淆）
        for i in range(n):
            keydata[i] ^= 0x64

        # 4. 第二层解密：用CORE_KEY进行AES-ECB解密
        mkeydata = _aes_ecb_decrypt(CORE_KEY, bytes(keydata))

        # 5. 去除前缀 "neteasecloudmusic"（17字节），构建RC4密钥盒
        self._key_box = _build_key_box(mkeydata[17:])

        # ========== 第四步：读取并解析歌曲元数据 ==========
        # 1. 读取元数据块长度
        meta_len_bytes = self._f.read(4)
        (meta_len,) = struct.unpack('<I', meta_len_bytes)
        if meta_len > 0:
            # 2. 读取加密的元数据
            modify_data = bytearray(self._f.read(meta_len))
            # 3. 第一层解密：逐字节异或0x63
            for i in range(meta_len):
                modify_data[i] ^= 0x63

            # 4. 去除前缀 "163 key(Don't modify):"（22字节）
            swap_modify = bytes(modify_data[22:])
            # 5. Base64解码
            decoded = base64.b64decode(swap_modify)
            # 6. 第二层解密：用MODIFY_KEY进行AES-ECB解密
            decrypted = _aes_ecb_decrypt(MODIFY_KEY, decoded)
            # 7. 去除前缀 "music:"（6字节），解析JSON
            json_str = decrypted[6:].decode('utf-8', errors='ignore')
            try:
                raw = json.loads(json_str)
                self.metadata = NeteaseMusicMetadata(raw)
            except Exception:
                self.metadata = None
        else:
            self.metadata = None

        # ========== 第五步：跳过CRC校验和封面数据 ==========
        # 1. 跳过CRC32校验（4字节）+ 图片版本（1字节），共5字节
        self._f.seek(5, os.SEEK_CUR)

        # 2. 读取封面帧总长度
        cover_frame_len_bytes = self._f.read(4)
        (self._cover_frame_len,) = struct.unpack('<I', cover_frame_len_bytes)

        # 3. 读取封面图片长度
        img_len_bytes = self._f.read(4)
        (img_len,) = struct.unpack('<I', img_len_bytes)
        if img_len > 0:
            # 4. 读取封面图片数据
            self.image_data = self._f.read(img_len)
        else:
            self.image_data = b''

        # 5. 跳过封面帧的剩余字节
        self._f.seek(self._cover_frame_len - img_len, os.SEEK_CUR)

        # 初始化输出文件路径和格式
        self._dump_filepath = None
        self.format = None

    def _is_ncm_file(self) -> bool:
        """
        验证NCM文件头：前8字节必须是 "CTENFDAM"
        :return: 是否为合法的NCM文件
        """
        self._f.seek(0)
        # 读取前4字节："CTEN" (0x4e455443)
        header = self._f.read(4)
        if len(header) < 4:
            return False
        if struct.unpack('<I', header)[0] != 0x4e455443:
            return False
        # 读取后4字节："FDAM" (0x4d414446)
        header2 = self._f.read(4)
        if struct.unpack('<I', header2)[0] != 0x4d414446:
            return False
        return True

    def dump_filepath(self):
        """获取转换后的文件路径"""
        return self._dump_filepath

    def dump(self, output_dir: str = ''):
        """
        解密音频数据并保存到文件
        :param output_dir: 输出文件夹（空则默认和原文件同目录）
        """
        # 确定输出文件路径
        if output_dir:
            base = os.path.join(output_dir, os.path.basename(self.filepath))
        else:
            base = self.filepath

        dump_path = base

        # ========== 核心：NCM定制的RC4流解密函数 ==========
        def process_buffer(buf: bytearray):
            """
            对音频数据块进行RC4流解密
            :param buf: 加密的音频数据块
            :return: 解密后的音频数据块
            """
            for i in range(len(buf)):
                j = (i + 1) & 0xff
                # NCM定制的双重密钥盒索引规则
                buf[i] ^= self._key_box[(self._key_box[j] + self._key_box[(self._key_box[j] + j) & 0xff]) & 0xff]
            return buf

        # ========== 逐块解密音频数据 ==========
        out = None
        while True:
            # 每次读取32KB（0x8000字节）
            chunk = self._f.read(0x8000)
            if not chunk:
                break  # 文件读取完毕
            
            # 解密当前块
            buf = bytearray(chunk)
            buf = process_buffer(buf)
            
            # 如果是第一块，先识别音频格式
            if out is None:
                # 检测MP3格式（开头是ID3标签）
                if len(buf) >= 3 and buf[0:3] == b'ID3':
                    dump_path = os.path.splitext(dump_path)[0] + '.mp3'
                    self.format = NeteaseCrypt.MP3
                # 否则默认是FLAC格式
                else:
                    dump_path = os.path.splitext(dump_path)[0] + '.flac'
                    self.format = NeteaseCrypt.FLAC
                # 打开输出文件
                out = open(dump_path, 'wb')
            
            # 写入解密后的音频数据
            out.write(buf)

        # 关闭输出文件
        if out:
            out.flush()
            out.close()

        self._dump_filepath = dump_path

    def fix_metadata(self):
        """
        修复音频文件的元数据：写入歌曲名、歌手、专辑、封面
        使用mutagen库，懒加载（只有调用时才需要安装mutagen）
        """
        # 懒加载mutagen库，避免依赖强制要求
        try:
            from mutagen.mp3 import MP3
            from mutagen.id3 import ID3, APIC, TIT2, TPE1, TALB
            from mutagen.flac import FLAC, Picture
        except Exception:
            return

        # 检查输出文件是否存在
        if not self._dump_filepath or not os.path.exists(self._dump_filepath):
            return

        # ========== 修复MP3的ID3标签 ==========
        if self.format == NeteaseCrypt.MP3:
            audio = MP3(self._dump_filepath, ID3=ID3)
            if audio.tags is None:
                audio.add_tags()
            tags = audio.tags
            
            # 写入专辑封面
            if self.image_data:
                tags.add(APIC(
                    mime='image/png' if self.image_data.startswith(PNG_MAGIC) else 'image/jpeg',
                    type=3,  # 3表示封面图
                    desc='cover',
                    data=self.image_data
                ))
            
            # 写入歌曲元数据
            if self.metadata:
                if self.metadata.name:
                    tags.add(TIT2(encoding=3, text=self.metadata.name))  # 歌曲名
                if self.metadata.artist:
                    tags.add(TPE1(encoding=3, text=self.metadata.artist))  # 歌手
                if self.metadata.album:
                    tags.add(TALB(encoding=3, text=self.metadata.album))  # 专辑
            
            audio.save()
        
        # ========== 修复FLAC的Vorbis注释 ==========
        elif self.format == NeteaseCrypt.FLAC:
            audio = FLAC(self._dump_filepath)
            
            # 写入专辑封面
            if self.image_data:
                pic = Picture()
                pic.data = self.image_data
                pic.type = 3
                pic.mime = 'image/png' if self.image_data.startswith(PNG_MAGIC) else 'image/jpeg'
                audio.add_picture(pic)
            
            # 写入歌曲元数据
            if self.metadata:
                if self.metadata.name:
                    audio['title'] = self.metadata.name
                if self.metadata.artist:
                    audio['artist'] = self.metadata.artist
                if self.metadata.album:
                    audio['album'] = self.metadata.album
            
            audio.save()

    def close(self):
        """关闭NCM文件句柄"""
        try:
            self._f.close()
        except Exception:
            pass

    def __enter__(self):
        """支持上下文管理器（with语句），自动关闭文件"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器退出时自动关闭文件"""
        self.close()
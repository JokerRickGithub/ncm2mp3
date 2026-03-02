#!/usr/bin/env python3
import argparse
import sys
import os
from pathlib import Path
from ncmcrypt import NeteaseCrypt


def process_file(path: Path, output_folder: Path, remove: bool):
    """
    处理单个NCM文件
    :param path: NCM文件路径
    :param output_folder: 输出文件夹
    :param remove: 是否删除原文件
    """
    # 检查文件是否存在
    if not path.exists():
        print(f"[Error] file '{path}' does not exist.")
        return

    # 只处理.ncm后缀的文件
    if path.suffix != '.ncm':
        return

    try:
        # 使用上下文管理器，自动关闭文件句柄
        with NeteaseCrypt(str(path)) as crypt:
            # 确定输出目录
            outdir = str(output_folder) if output_folder else ''
            # 解密音频数据
            crypt.dump(outdir)
            # 修复元数据
            crypt.fix_metadata()
            # 打印成功信息
            print(f"[Done] '{path}' -> '{crypt.dump_filepath()}'", end='')
            # 如果要求删除原文件
            if remove:
                path.unlink()
                print(' with removed as required.', end='')
            print()
    except Exception as e:
        print(f"[Exception] {e} '{path}'")


def main():
    """主函数：解析命令行参数，批量处理文件"""
    # 初始化命令行参数解析器
    parser = argparse.ArgumentParser(prog='ncmdump')
    parser.add_argument('-d', '--directory', help='Process files in a folder')  # 批量处理文件夹
    parser.add_argument('-r', '--recursive', action='store_true', help='Process files recursively')  # 递归扫描
    parser.add_argument('-o', '--output', help='Output folder (default: original file folder)')  # 输出目录
    parser.add_argument('-v', '--version', action='store_true', help='Print version information')  # 版本信息
    parser.add_argument('-m', '--remove', action='store_true', help='Remove original file if done')  # 删除原文件
    parser.add_argument('filenames', nargs='*', help='Input files')  # 单个文件输入

    args = parser.parse_args()

    # 打印版本信息
    if args.version:
        print('ncmdump python version 1.0.0')
        return

    # 处理输出目录
    output_dir = Path(args.output) if args.output else None
    if output_dir and not output_dir.exists():
        output_dir.mkdir(parents=True, exist_ok=True)  # 自动创建输出目录

    # 如果没有输入参数，打印帮助
    if not args.directory and not args.filenames:
        parser.print_help()
        sys.exit(1)

    # ========== 批量处理文件夹模式 ==========
    if args.directory:
        source = Path(args.directory)
        if not source.is_dir():
            print(f"[Error] '{source}' is not a valid directory.")
            sys.exit(1)

        # 递归扫描子文件夹
        if args.recursive:
            for p in source.rglob('*.ncm'):
                out = output_dir if output_dir else p.parent
                process_file(p, out, args.remove)
        # 只处理当前文件夹
        else:
            for p in source.glob('*.ncm'):
                out = output_dir if output_dir else p.parent
                process_file(p, out, args.remove)
        return

    # ========== 处理单个文件模式 ==========
    for f in args.filenames:
        p = Path(f)
        if not p.is_file():
            print(f"[Error] '{p}' is not a valid file.")
            continue
        out = output_dir if output_dir else p.parent
        process_file(p, out, args.remove)


if __name__ == '__main__':
    # ========== 新手友好的双击运行模式（修改这里的参数即可） ==========
    import sys
    from pathlib import Path

    # 在这里配置你的参数，修改后直接双击运行
    INPUT_FOLDER = r"E:\music\VipSongsDownload"  # 存放NCM文件的文件夹
    OUTPUT_FOLDER = r"E:\music\VipSongsDownload\已转换"  # 转换后文件的输出文件夹
    RECURSIVE_SCAN = False  # 是否扫描子文件夹里的NCM文件（True/False）
    DELETE_ORIGINAL = False  # 转换成功后是否删除原NCM文件（True/False）
    # ================================================================

    # 自动创建输出文件夹
    output_path = Path(OUTPUT_FOLDER)
    output_path.mkdir(parents=True, exist_ok=True)

    # 校验输入文件夹
    input_path = Path(INPUT_FOLDER)
    if not input_path.is_dir():
        print(f"[错误] 输入文件夹不存在: {INPUT_FOLDER}")
        sys.exit(1)

    # 扫描NCM文件
    if RECURSIVE_SCAN:
        ncm_files = input_path.rglob('*.ncm')
    else:
        ncm_files = input_path.glob('*.ncm')

    # 批量转换
    file_list = list(ncm_files)
    if not file_list:
        print("未找到任何NCM文件，请检查输入文件夹")
        sys.exit(0)

    print(f"共找到 {len(file_list)} 个NCM文件，开始转换...\n")
    for file in file_list:
        process_file(file, output_path, DELETE_ORIGINAL)

    print("\n全部转换任务完成！")
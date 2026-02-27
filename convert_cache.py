"""
缓存压缩转换工具

将现有缓存转换为指定压缩格式
"""
import pandas as pd
from pathlib import Path
import argparse
from datetime import datetime
from loguru import logger


def convert_cache_compression(compression: str = "gzip"):
    """转换缓存压缩格式"""
    cache_dir = Path("data_cache")
    
    # 获取所有 parquet 文件
    parquet_files = list(cache_dir.rglob("*.parquet"))
    print(f"找到 {len(parquet_files)} 个缓存文件")
    
    total_before = 0
    total_after = 0
    converted = 0
    
    for i, file in enumerate(parquet_files):
        try:
            # 读取原文件
            df = pd.read_parquet(file)
            size_before = file.stat().st_size
            total_before += size_before
            
            # 使用新压缩保存
            df.to_parquet(file, compression=compression)
            size_after = file.stat().st_size
            total_after += size_after
            
            converted += 1
            
            if (i + 1) % 100 == 0:
                print(f"  已转换 {i + 1}/{len(parquet_files)}...")
                
        except Exception as e:
            print(f"  跳过 {file.name}: {e}")
    
    # 显示结果
    print(f"\n转换完成!")
    print(f"  转换文件数：{converted}")
    print(f"  转换前：{total_before / 1024 / 1024:.2f} MB")
    print(f"  转换后：{total_after / 1024 / 1024:.2f} MB")
    print(f"  节省空间：{(total_before - total_after) / 1024 / 1024:.2f} MB ({(1 - total_after/total_before) * 100:.1f}%)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="缓存压缩转换工具")
    parser.add_argument("--compression", type=str, default="gzip",
                       choices=["none", "snappy", "gzip", "brotli", "zstd"],
                       help="压缩算法")
    
    args = parser.parse_args()
    
    print(f"转换缓存为 {args.compression} 压缩...")
    convert_cache_compression(args.compression)

"""
重建缓存元数据脚本

扫描 data_cache 目录中的所有 parquet 文件，重建 metadata.csv
"""
import pandas as pd
from pathlib import Path
from datetime import datetime
import re
from loguru import logger


def parse_filename(filename: str) -> dict:
    """从文件名解析元数据"""
    name = filename.stem  # 不含扩展名
    
    # 解析模式 1: daily_adj=qfq_end=20231231_start=20200101_ts_code=000001.SZ_20260226_153445
    # 解析模式 2: BJSE/daily_full_adj=qfq_ts_code=920000.BJ_20260227_142628
    
    result = {
        'data_type': 'unknown',
        'ts_code': None,
        'start_date': None,
        'end_date': None,
        'is_complete': False,
        'record_count': 0
    }
    
    # 提取数据类型
    if 'daily_full' in name:
        result['data_type'] = 'daily_full'
        result['is_complete'] = True
    elif 'daily_adj' in name:
        result['data_type'] = 'daily_adj'
    elif 'index_daily' in name:
        result['data_type'] = 'index_daily'
    elif 'adj_factor' in name:
        result['data_type'] = 'adj_factor'
    
    # 提取 ts_code
    ts_match = re.search(r'ts_code=([0-9A-Z\.]+)', name)
    if ts_match:
        result['ts_code'] = ts_match.group(1)
    
    # 提取日期范围
    start_match = re.search(r'start=([0-9]{8})', name)
    end_match = re.search(r'end=([0-9]{8})', name)
    if start_match:
        result['start_date'] = start_match.group(1)
    if end_match:
        result['end_date'] = end_match.group(1)
    
    # 提取时间戳
    time_match = re.search(r'(\d{8}_\d{6})$', name)
    if time_match:
        result['updated_at'] = time_match.group(1)
    else:
        result['updated_at'] = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    return result


def rebuild_metadata(cache_dir: str = './data_cache'):
    """重建缓存元数据"""
    cache_path = Path(cache_dir)
    metadata_file = cache_path / 'metadata.csv'
    
    # 扫描所有 parquet 文件
    parquet_files = list(cache_path.rglob('*.parquet'))
    print(f"发现 {len(parquet_files)} 个 parquet 文件")
    
    # 构建元数据
    records = []
    for i, file in enumerate(parquet_files):
        try:
            parsed = parse_filename(file)
            
            # 读取文件获取记录数
            try:
                df = pd.read_parquet(file)
                record_count = len(df)
            except:
                record_count = 0
            
            # 生成 key
            key = f"{parsed['data_type']}_{parsed['ts_code']}_{parsed.get('start_date', '')}_{parsed.get('end_date', '')}"
            
            records.append({
                'key': key,
                'path': str(file),
                'updated_at': parsed.get('updated_at', datetime.now().strftime('%Y%m%d_%H%M%S')),
                'start_date': parsed.get('start_date'),
                'end_date': parsed.get('end_date'),
                'data_type': parsed['data_type'],
                'ts_code': parsed['ts_code'],
                'is_complete': parsed['is_complete'],
                'record_count': record_count
            })
            
            if (i + 1) % 500 == 0:
                print(f"  已处理 {i + 1}/{len(parquet_files)} 个文件...")
                
        except Exception as e:
            print(f"  处理失败 {file}: {e}")
    
    # 创建 DataFrame
    df = pd.DataFrame(records)
    
    # 保存 metadata.csv
    df.to_csv(metadata_file, index=False)
    print(f"\n[OK] 元数据重建完成！")
    print(f"  总文件数：{len(records)}")
    print(f"  保存至：{metadata_file}")
    
    # 显示统计
    if not df.empty:
        print(f"\n缓存统计:")
        print(f"  股票数量：{df['ts_code'].dropna().nunique()}")
        print(f"  完整数据：{len(df[df['is_complete'] == True])}")
        print(f"  不完整：{len(df[df['is_complete'] == False])}")
        print(f"\n  数据类型分布:")
        for dtype, count in df['data_type'].value_counts().items():
            print(f"    - {dtype}: {count}")


if __name__ == '__main__':
    rebuild_metadata()

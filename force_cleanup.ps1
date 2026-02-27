# 强制清理旧数据结构

Write-Host "开始清理..."

# 删除 CSV 文件
Remove-Item "data_cache\metadata.csv" -Force -ErrorAction SilentlyContinue
Remove-Item "data_cache\access_log.csv" -Force -ErrorAction SilentlyContinue

# 删除所有 .bak 文件
Get-ChildItem "data_cache\*.bak" -Recurse | Remove-Item -Force

# 删除根目录的 parquet 文件
Get-ChildItem "data_cache\*.parquet" -File | Remove-Item -Force

# 删除 index_daily 文件
Get-ChildItem "data_cache\index_daily*" | Remove-Item -Force

Write-Host "清理完成！"

# 验证
Write-Host "`n验证结果:"
Write-Host "  metadata.csv: $((Test-Path 'data_cache\metadata.csv').ToString())"
Write-Host "  access_log.csv: $((Test-Path 'data_cache\access_log.csv').ToString())"
Write-Host "  .bak 文件：$((Get-ChildItem 'data_cache\*.bak').Count) 个"
Write-Host "  根目录 parquet: $((Get-ChildItem 'data_cache\*.parquet' -File).Count) 个"

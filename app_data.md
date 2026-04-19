```txt
{app_data}/
├── config/
│   ├── main.yaml                    # 用户主配置（可选）
│   ├── sites/                       # 各网站独立配置
│   └── formats/                     # 导出格式配置
├── storage/                         # 断点续传数据
│   └── {novel_id}/
│       ├── meta.json                # 小说元数据
│       ├── progress.json            # 下载进度状态
│       └── chapters/
│           ├── 00001.json           # 每章独立存储
│           └── ...
├── logs/                            # 运行日志
└── outputs/                         # 最终导出文件
    └── {group}/
        └── {novel_title}/
            ├── 小说名 - 作者.txt
            └── 小说名 - 作者.epub```
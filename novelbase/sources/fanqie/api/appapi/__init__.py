"""番茄小说官方 app API 直连（四件套签名：x-gorgon/x-khronos/x-argus/x-ladon）。

与 api/ 模式下第三方代理（oiapi / rain）不同，本 provider 直连番茄官方接口，
请求头携带字节系四件套签名（见 sign.py / _xgorgon.py，移植自
ssovit/x-gorogn-khronos-argus-ladon，MIT），公共参数见 _params。

可用能力（2026-08-23 实测）：
- search：✅ 可用（reading 域搜索接口）
- novel_info：✅ 可用（directory/list 的 book_info）
- chapter_list：✅ 可用（all_items 全量目录，含真实标题/卷名/字数）
- chapter_content：❌ 任意章节正文未打通（正文接口需 y 加密头 + 有效设备会话）
- first_chapter_content：✅ 首章明文正文可用（detail 接口 data.content，无需 y/设备会话，
  实测 1862 字 == 第 1 章 chapter_word_number）
"""

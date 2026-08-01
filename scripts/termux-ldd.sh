#!/data/data/com.termux/files/usr/bin/sh
# Termux ldd wrapper（Nuitka 依赖检测需要 ldd）
# 用 readelf 读取 DT_NEEDED，在系统库目录搜索绝对路径
for file in "$@"; do
    [ -f "$file" ] || continue
    readelf -d "$file" 2>/dev/null | grep 'NEEDED' | sed -n 's/.*\[\(.*\)\]/\1/p' | while read -r lib; do
        found=""
        for dir in /data/data/com.termux/files/usr/lib /system/lib64 /system/lib /vendor/lib64 /vendor/lib; do
            if [ -f "$dir/$lib" ]; then found="$dir/$lib"; break; fi
        done
        if [ -n "$found" ]; then
            echo "    $lib => $found (0x0)"
        else
            echo "    $lib => not found"
        fi
    done
done

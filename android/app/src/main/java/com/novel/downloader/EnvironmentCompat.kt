package com.novel.downloader

import android.os.Build
import android.os.Environment

object EnvironmentCompat {
    fun hasAllFilesAccess(): Boolean =
        if (Build.VERSION.SDK_INT >= 30) Environment.isExternalStorageManager() else true
}

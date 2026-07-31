package com.noveldownloader

import android.app.Application
import com.noveldownloader.config.ConfigService
import com.noveldownloader.storage.StoragePaths
import dagger.hilt.android.HiltAndroidApp
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltAndroidApp
class NovelApp : Application() {
    @Inject lateinit var configService: ConfigService

    override fun onCreate() {
        super.onCreate()
        StoragePaths.init()
        CoroutineScope(Dispatchers.IO).launch {
            configService.initDefaultConfigs()
        }
    }
}

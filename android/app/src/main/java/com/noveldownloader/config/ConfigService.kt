package com.noveldownloader.config

import android.content.Context
import com.google.gson.Gson
import com.noveldownloader.storage.StoragePaths
import dagger.hilt.android.qualifiers.ApplicationContext
import java.io.File
import javax.inject.Inject
import javax.inject.Singleton

/** 应用设置。 */
data class AppSettings(
    val exportFormat: String = "txt",
    val maxWorkers: Int = 3,
    val requestDelay: Long = 1500,  // ms
)

/** 站点配置。 */
data class SiteConfig(
    val delay: Long = 1500,
)

/** 配置服务 — JSON 文件存储。 */
@Singleton
class ConfigService @Inject constructor(
    @ApplicationContext private val context: Context,
) {
    private val gson = Gson()
    private val configDir = File(StoragePaths.dataDir, "config").also { it.mkdirs() }

    fun loadSettings(): AppSettings {
        val file = File(configDir, "settings.json")
        if (!file.exists()) return AppSettings()
        return try { gson.fromJson(file.readText(), AppSettings::class.java) } catch (_: Exception) { AppSettings() }
    }

    fun saveSettings(settings: AppSettings) {
        File(configDir, "settings.json").writeText(gson.toJson(settings))
    }

    fun loadSiteConfig(platform: String): SiteConfig {
        val file = File(configDir, "sites/$platform.json")
        if (!file.exists()) return SiteConfig()
        return try { gson.fromJson(file.readText(), SiteConfig::class.java) } catch (_: Exception) { SiteConfig() }
    }

    /** 首次启动时从 assets 复制默认配置。 */
    suspend fun initDefaultConfigs() {
        val sitesDir = File(configDir, "sites").also { it.mkdirs() }
        val assets = listOf("settings.json", "fanqie.json", "qidian.json", "qimao.json", "92xs.json")
        assets.forEach { name ->
            val target = if (name == "settings.json") File(configDir, name) else File(sitesDir, name)
            if (!target.exists()) {
                try {
                    context.assets.open("default_config/$name").use { input ->
                        target.writeBytes(input.readBytes())
                    }
                } catch (_: Exception) {
                    // 默认配置不存在则跳过
                }
            }
        }
    }
}

package com.noveldownloader.config

import android.content.Context
import com.google.gson.Gson
import com.google.gson.annotations.SerializedName
import java.io.File

data class AppConfig(
    val mode: String = "requests",
    @SerializedName("max_workers") val maxWorkers: Int = 3,
    val notify: NotifyConfig = NotifyConfig(),
) { data class NotifyConfig(@SerializedName("on_complete") val onComplete: Boolean = true) }

class ConfigManager(private val ctx: Context) {
    private val gson = Gson()
    private val dir = File(ctx.filesDir, "config").also { it.mkdirs() }
    private val configFile = File(dir, "config.json")

    fun load(): AppConfig = if (configFile.exists())
        try { gson.fromJson(configFile.readText(), AppConfig::class.java) } catch (_: Exception) { AppConfig() }
        else AppConfig()

    fun save(config: AppConfig) { configFile.writeText(gson.toJson(config)) }

    fun loadSiteYaml(platform: String): Map<String, Any> {
        val file = File(dir, "sites/$platform.json")
        if (!file.exists()) return mapOf("delay" to 1500L, "timeout" to 30, "retry_times" to 3)
        return try { gson.fromJson(file.readText(), Map::class.java) as Map<String, Any> } catch (_: Exception) { emptyMap() }
    }

    fun loadGroups(): Map<String, Any> {
        val file = File(dir, "groups.json")
        if (!file.exists()) return mapOf("default" to emptyMap<String, Any>())
        return try { gson.fromJson(file.readText(), Map::class.java) as Map<String, Any> } catch (_: Exception) { emptyMap() }
    }

    fun saveGroups(groups: Map<String, Any>) { File(dir, "groups.json").writeText(gson.toJson(groups)) }
}

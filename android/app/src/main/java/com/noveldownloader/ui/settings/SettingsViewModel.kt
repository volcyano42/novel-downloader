package com.noveldownloader.ui.settings

import androidx.lifecycle.ViewModel
import com.noveldownloader.config.AppSettings
import com.noveldownloader.config.ConfigService
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import javax.inject.Inject

@HiltViewModel
class SettingsViewModel @Inject constructor(
    private val configService: ConfigService,
) : ViewModel() {
    private val _settings = MutableStateFlow(configService.loadSettings())
    val settings: StateFlow<AppSettings> = _settings.asStateFlow()

    fun updateSettings(update: (AppSettings) -> AppSettings) {
        val new = update(_settings.value)
        _settings.value = new
        configService.saveSettings(new)
    }
}

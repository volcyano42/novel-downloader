package com.noveldownloader.ui.download

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.noveldownloader.data.repository.DownloadRepository
import com.noveldownloader.util.DownloadProgress
import com.noveldownloader.util.UiState
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class DownloadViewModel @Inject constructor(
    savedStateHandle: SavedStateHandle,
    private val downloadRepository: DownloadRepository,
) : ViewModel() {
    private val novelId: String = savedStateHandle["novelId"] ?: ""

    private val _state = MutableStateFlow<UiState<DownloadProgress>>(UiState.Loading)
    val state: StateFlow<UiState<DownloadProgress>> = _state.asStateFlow()

    init {
        startDownload()
    }

    private fun startDownload() {
        viewModelScope.launch {
            downloadRepository.startDownload(novelId, viewModelScope).collect { progress ->
                _state.value = UiState.Success(progress)
            }
        }
    }

    fun pauseDownload() {
        downloadRepository.pauseDownload(novelId)
    }
}

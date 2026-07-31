package com.noveldownloader.ui.reader

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.noveldownloader.data.db.ChapterDao
import com.noveldownloader.data.model.Chapter
import com.noveldownloader.util.UiState
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import javax.inject.Inject

data class ReaderState(
    val chapters: List<Chapter> = emptyList(),
    val currentIndex: Int = 0,
    val currentChapter: Chapter? = null,
    val fontSize: Float = 18f,
    val isDarkBg: Boolean = true,
)

@HiltViewModel
class ReaderViewModel @Inject constructor(
    savedStateHandle: SavedStateHandle,
    private val chapterDao: ChapterDao,
) : ViewModel() {
    private val novelId: String = savedStateHandle["novelId"] ?: ""
    private val startIndex: Int = savedStateHandle.get<Int>("chapterIndex") ?: 0

    private val _state = MutableStateFlow<UiState<ReaderState>>(UiState.Loading)
    val state: StateFlow<UiState<ReaderState>> = _state.asStateFlow()

    init {
        load()
    }

    private fun load() {
        viewModelScope.launch {
            val chapters = chapterDao.getByNovelIdSync(novelId)
            if (chapters.isEmpty()) {
                _state.value = UiState.Error("暂无章节")
                return@launch
            }
            val idx = startIndex.coerceIn(0, chapters.lastIndex)
            _state.value = UiState.Success(ReaderState(
                chapters = chapters,
                currentIndex = idx,
                currentChapter = chapters[idx],
            ))
        }
    }

    fun goToChapter(index: Int) {
        val current = (_state.value as? UiState.Success)?.data ?: return
        if (index < 0 || index >= current.chapters.size) return
        _state.value = UiState.Success(current.copy(
            currentIndex = index,
            currentChapter = current.chapters[index],
        ))
    }

    fun nextChapter(): Boolean {
        val current = (_state.value as? UiState.Success)?.data ?: return false
        if (current.currentIndex + 1 >= current.chapters.size) return false
        goToChapter(current.currentIndex + 1)
        return true
    }

    fun prevChapter(): Boolean {
        val current = (_state.value as? UiState.Success)?.data ?: return false
        if (current.currentIndex - 1 < 0) return false
        goToChapter(current.currentIndex - 1)
        return true
    }

    fun setFontSize(size: Float) {
        val current = (_state.value as? UiState.Success)?.data ?: return
        _state.value = UiState.Success(current.copy(fontSize = size))
    }

    fun toggleBackground() {
        val current = (_state.value as? UiState.Success)?.data ?: return
        _state.value = UiState.Success(current.copy(isDarkBg = !current.isDarkBg))
    }
}

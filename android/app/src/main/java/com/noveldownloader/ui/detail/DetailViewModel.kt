package com.noveldownloader.ui.detail

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.noveldownloader.data.db.ChapterDao
import com.noveldownloader.data.db.NovelDao
import com.noveldownloader.data.model.Chapter
import com.noveldownloader.data.model.Novel
import com.noveldownloader.data.model.ChapterItem
import com.noveldownloader.data.repository.NovelRepository
import com.noveldownloader.util.UiState
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import javax.inject.Inject

data class DetailState(
    val novel: Novel? = null,
    val chapters: List<ChapterItem> = emptyList(),
    val isInBookshelf: Boolean = false,
)

@HiltViewModel
class DetailViewModel @Inject constructor(
    savedStateHandle: SavedStateHandle,
    private val repository: NovelRepository,
    private val novelDao: NovelDao,
    private val chapterDao: ChapterDao,
) : ViewModel() {
    private val novelId: String = savedStateHandle["novelId"] ?: ""

    private val _state = MutableStateFlow<UiState<DetailState>>(UiState.Loading)
    val state: StateFlow<UiState<DetailState>> = _state.asStateFlow()

    init {
        load()
    }

    private fun load() {
        viewModelScope.launch {
            _state.value = UiState.Loading
            try {
                // 尝试从 DB 加载
                val novel = novelDao.getById(novelId)
                if (novel != null) {
                    val items = chapterDao.getByNovelIdSync(novelId).map { ch ->
                        ChapterItem(ch.chapterId, ch.title, ch.url, ch.order)
                    }
                    _state.value = UiState.Success(DetailState(
                        novel = novel,
                        chapters = items,
                        isInBookshelf = true,
                    ))
                } else {
                    // 新小说需要 fetch（但 novelId 是 "fanqie_123" 格式，需要 url）
                    // 实际上 Detail 应该在搜索结果点击后、加入书架前传入 url
                    _state.value = UiState.Error("请先在搜索结果中查看详情")
                }
            } catch (e: Exception) {
                _state.value = UiState.Error(e.message ?: "加载失败")
            }
        }
    }

    /** 从 URL 获取详情（搜索结果跳转时用）。 */
    fun loadFromUrl(url: String) {
        viewModelScope.launch {
            _state.value = UiState.Loading
            try {
                val novel = repository.fetchNovelInfo(url)
                _state.value = UiState.Success(DetailState(
                    novel = novel,
                    isInBookshelf = false,
                ))
            } catch (e: Exception) {
                _state.value = UiState.Error(e.message ?: "加载失败")
            }
        }
    }

    fun addToBookshelfAndFetchChapters() {
        viewModelScope.launch {
            val current = (_state.value as? UiState.Success)?.data ?: return@launch
            val novel = current.novel ?: return@launch
            try {
                repository.addToBookshelf(novel)
                val items = repository.fetchChapterList(novel)
                if (items.isNotEmpty()) {
                    // 批量插入章节
                    val chapters = items.map { item ->
                        Chapter(
                            chapterId = item.chapterId,
                            novelId = novel.novelId,
                            title = item.title,
                            url = item.url,
                            order = item.order,
                        )
                    }
                    chapterDao.upsertAll(chapters)
                }
                _state.value = UiState.Success(current.copy(
                    chapters = items,
                    isInBookshelf = true,
                ))
            } catch (e: Exception) {
                _state.value = UiState.Error(e.message ?: "加入书架失败")
            }
        }
    }
}

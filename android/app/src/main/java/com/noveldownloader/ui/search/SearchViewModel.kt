package com.noveldownloader.ui.search

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.noveldownloader.data.model.SearchResult
import com.noveldownloader.data.repository.NovelRepository
import com.noveldownloader.util.UiState
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class SearchViewModel @Inject constructor(
    private val repository: NovelRepository,
) : ViewModel() {
    private val _query = MutableStateFlow("")
    val query: StateFlow<String> = _query.asStateFlow()

    private val _state = MutableStateFlow<UiState<Map<String, List<SearchResult>>>>(UiState.Loading)
    val state: StateFlow<UiState<Map<String, List<SearchResult>>>> = _state.asStateFlow()

    private var searchJob: Job? = null

    fun onQueryChanged(q: String) {
        _query.value = q
        if (q.length < 2) {
            _state.value = UiState.Success(emptyMap())
            return
        }
        // 防抖 300ms
        searchJob?.cancel()
        searchJob = viewModelScope.launch {
            delay(300)
            _state.value = UiState.Loading
            try {
                val results = repository.search(q)
                _state.value = UiState.Success(results)
            } catch (e: Exception) {
                _state.value = UiState.Error(e.message ?: "搜索失败")
            }
        }
    }
}

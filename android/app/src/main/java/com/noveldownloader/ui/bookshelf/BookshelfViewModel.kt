package com.noveldownloader.ui.bookshelf

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.noveldownloader.data.db.NovelDao
import com.noveldownloader.data.model.Novel
import com.noveldownloader.util.UiState
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class BookshelfViewModel @Inject constructor(
    private val novelDao: NovelDao,
) : ViewModel() {
    private val _state = MutableStateFlow<UiState<List<Novel>>>(UiState.Loading)
    val state: StateFlow<UiState<List<Novel>>> = _state.asStateFlow()

    init {
        viewModelScope.launch {
            novelDao.getAll().collect { novels ->
                _state.value = UiState.Success(novels)
            }
        }
    }

    fun deleteNovel(novelId: String) {
        viewModelScope.launch {
            novelDao.deleteById(novelId)
        }
    }
}

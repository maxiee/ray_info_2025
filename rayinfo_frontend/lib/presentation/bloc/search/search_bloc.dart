import 'package:equatable/equatable.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../domain/entities/article.dart';
import '../../../domain/entities/pagination.dart';
import '../../../domain/usecases/search_articles.dart';

/// 搜索事件
abstract class SearchEvent extends Equatable {
  const SearchEvent();
  
  @override
  List<Object?> get props => [];
}

/// 搜索资讯事件
class SearchArticles extends SearchEvent {
  final String query;
  final int page;
  final int limit;
  final String? source;
  final DateTime? startDate;
  final DateTime? endDate;
  
  const SearchArticles({
    required this.query,
    this.page = 1,
    this.limit = 20,
    this.source,
    this.startDate,
    this.endDate,
  });
  
  @override
  List<Object?> get props => [query, page, limit, source, startDate, endDate];
}

/// 加载更多搜索结果事件
class LoadMoreSearchResults extends SearchEvent {
  const LoadMoreSearchResults();
}

/// 清空搜索结果事件
class ClearSearch extends SearchEvent {
  const ClearSearch();
}

/// 搜索状态
abstract class SearchState extends Equatable {
  const SearchState();
  
  @override
  List<Object?> get props => [];
}

/// 搜索初始状态
class SearchInitial extends SearchState {}

/// 搜索中状态
class SearchLoading extends SearchState {}

/// 搜索成功状态
class SearchLoaded extends SearchState {
  final List<Article> articles;
  final Pagination pagination;
  final String query;
  final bool isLoadingMore;
  final String? currentSource;
  final DateTime? currentStartDate;
  final DateTime? currentEndDate;
  
  const SearchLoaded({
    required this.articles,
    required this.pagination,
    required this.query,
    this.isLoadingMore = false,
    this.currentSource,
    this.currentStartDate,
    this.currentEndDate,
  });
  
  SearchLoaded copyWith({
    List<Article>? articles,
    Pagination? pagination,
    String? query,
    bool? isLoadingMore,
    String? currentSource,
    DateTime? currentStartDate,
    DateTime? currentEndDate,
  }) {
    return SearchLoaded(
      articles: articles ?? this.articles,
      pagination: pagination ?? this.pagination,
      query: query ?? this.query,
      isLoadingMore: isLoadingMore ?? this.isLoadingMore,
      currentSource: currentSource ?? this.currentSource,
      currentStartDate: currentStartDate ?? this.currentStartDate,
      currentEndDate: currentEndDate ?? this.currentEndDate,
    );
  }
  
  @override
  List<Object?> get props => [
    articles,
    pagination,
    query,
    isLoadingMore,
    currentSource,
    currentStartDate,
    currentEndDate,
  ];
}

/// 搜索失败状态
class SearchError extends SearchState {
  final String message;
  
  const SearchError(this.message);
  
  @override
  List<Object?> get props => [message];
}

/// 搜索BLoC
class SearchBloc extends Bloc<SearchEvent, SearchState> {
  final SearchArticlesUseCase _searchArticlesUseCase;
  
  SearchBloc(this._searchArticlesUseCase) : super(SearchInitial()) {
    on<SearchArticles>(_onSearchArticles);
    on<LoadMoreSearchResults>(_onLoadMoreSearchResults);
    on<ClearSearch>(_onClearSearch);
  }
  
  /// 处理搜索事件
  Future<void> _onSearchArticles(
    SearchArticles event,
    Emitter<SearchState> emit,
  ) async {
    try {
      if (event.page == 1) {
        emit(SearchLoading());
      } else if (state is SearchLoaded) {
        final currentState = state as SearchLoaded;
        emit(currentState.copyWith(isLoadingMore: true));
      }
      
      final (articles, pagination) = await _searchArticlesUseCase(
        searchQuery: event.query,
        page: event.page,
        limit: event.limit,
        source: event.source,
        startDate: event.startDate,
        endDate: event.endDate,
      );
      
      if (event.page == 1) {
        // 新搜索，替换整个列表
        emit(SearchLoaded(
          articles: articles,
          pagination: pagination,
          query: event.query,
          currentSource: event.source,
          currentStartDate: event.startDate,
          currentEndDate: event.endDate,
        ));
      } else if (state is SearchLoaded) {
        // 加载更多，追加到现有列表
        final currentState = state as SearchLoaded;
        final updatedArticles = [...currentState.articles, ...articles];
        
        emit(SearchLoaded(
          articles: updatedArticles,
          pagination: pagination,
          query: event.query,
          currentSource: event.source,
          currentStartDate: event.startDate,
          currentEndDate: event.endDate,
        ));
      }
    } catch (e) {
      emit(SearchError(e.toString()));
    }
  }
  
  /// 处理加载更多搜索结果事件
  Future<void> _onLoadMoreSearchResults(
    LoadMoreSearchResults event,
    Emitter<SearchState> emit,
  ) async {
    if (state is SearchLoaded) {
      final currentState = state as SearchLoaded;
      
      // 检查是否还有更多数据
      if (!currentState.pagination.hasNext || currentState.isLoadingMore) {
        return;
      }
      
      add(SearchArticles(
        query: currentState.query,
        page: currentState.pagination.currentPage + 1,
        source: currentState.currentSource,
        startDate: currentState.currentStartDate,
        endDate: currentState.currentEndDate,
      ));
    }
  }
  
  /// 处理清空搜索事件
  Future<void> _onClearSearch(
    ClearSearch event,
    Emitter<SearchState> emit,
  ) async {
    emit(SearchInitial());
  }
}
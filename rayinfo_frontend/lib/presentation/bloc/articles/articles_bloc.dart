import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../domain/usecases/get_articles.dart';
import 'articles_event.dart';
import 'articles_state.dart';

/// 资讯列表BLoC
class ArticlesBloc extends Bloc<ArticlesEvent, ArticlesState> {
  final GetArticlesUseCase _getArticlesUseCase;
  
  ArticlesBloc(this._getArticlesUseCase) : super(ArticlesInitial()) {
    on<LoadArticles>(_onLoadArticles);
    on<RefreshArticles>(_onRefreshArticles);
    on<LoadMoreArticles>(_onLoadMoreArticles);
  }
  
  /// 处理加载资讯事件
  Future<void> _onLoadArticles(
    LoadArticles event,
    Emitter<ArticlesState> emit,
  ) async {
    try {
      if (event.isRefresh && state is ArticlesLoaded) {
        // 刷新时保持当前状态，只显示loading状态
        final currentState = state as ArticlesLoaded;
        emit(currentState.copyWith(isLoadingMore: false));
      } else if (event.page == 1) {
        // 首次加载或筛选条件改变
        emit(ArticlesLoading());
      } else if (state is ArticlesLoaded) {
        // 加载更多
        final currentState = state as ArticlesLoaded;
        emit(currentState.copyWith(isLoadingMore: true));
      }
      
      final (articles, pagination) = await _getArticlesUseCase(
        page: event.page,
        limit: event.limit,
        source: event.source,
        query: event.query,
        startDate: event.startDate,
        endDate: event.endDate,
      );
      
      if (event.page == 1 || event.isRefresh) {
        // 首次加载或刷新，替换整个列表
        emit(ArticlesLoaded(
          articles: articles,
          pagination: pagination,
          currentSource: event.source,
          currentQuery: event.query,
          currentStartDate: event.startDate,
          currentEndDate: event.endDate,
        ));
      } else if (state is ArticlesLoaded) {
        // 加载更多，追加到现有列表
        final currentState = state as ArticlesLoaded;
        final updatedArticles = [...currentState.articles, ...articles];
        
        emit(ArticlesLoaded(
          articles: updatedArticles,
          pagination: pagination,
          currentSource: event.source,
          currentQuery: event.query,
          currentStartDate: event.startDate,
          currentEndDate: event.endDate,
        ));
      }
    } catch (e) {
      emit(ArticlesError(e.toString()));
    }
  }
  
  /// 处理刷新资讯事件
  Future<void> _onRefreshArticles(
    RefreshArticles event,
    Emitter<ArticlesState> emit,
  ) async {
    add(LoadArticles(
      page: 1,
      source: event.source,
      query: event.query,
      startDate: event.startDate,
      endDate: event.endDate,
      isRefresh: true,
    ));
  }
  
  /// 处理加载更多资讯事件
  Future<void> _onLoadMoreArticles(
    LoadMoreArticles event,
    Emitter<ArticlesState> emit,
  ) async {
    if (state is ArticlesLoaded) {
      final currentState = state as ArticlesLoaded;
      
      // 检查是否还有更多数据
      if (!currentState.pagination.hasNext || currentState.isLoadingMore) {
        return;
      }
      
      add(LoadArticles(
        page: currentState.pagination.currentPage + 1,
        source: currentState.currentSource,
        query: currentState.currentQuery,
        startDate: currentState.currentStartDate,
        endDate: currentState.currentEndDate,
      ));
    }
  }
}
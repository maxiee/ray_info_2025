import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../domain/usecases/get_articles.dart';
import '../../../domain/entities/article.dart';
import '../../../data/models/read_status_models.dart';
import 'articles_event.dart';
import 'articles_state.dart';

/// 资讯列表BLoC
class ArticlesBloc extends Bloc<ArticlesEvent, ArticlesState> {
  final GetArticlesUseCase _getArticlesUseCase;

  ArticlesBloc(this._getArticlesUseCase) : super(ArticlesInitial()) {
    on<LoadArticles>(_onLoadArticles);
    on<RefreshArticles>(_onRefreshArticles);
    on<LoadMoreArticles>(_onLoadMoreArticles);
    on<UpdateArticleReadStatus>(_onUpdateArticleReadStatus); // 新增
    on<UpdateFilters>(_onUpdateFilters); // 新增
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
        readStatus: event.readStatus, // 新增已读状态参数
      );

      if (event.page == 1 || event.isRefresh) {
        // 首次加载或刷新，替换整个列表
        emit(
          ArticlesLoaded(
            articles: articles,
            pagination: pagination,
            currentSource: event.source,
            currentQuery: event.query,
            currentStartDate: event.startDate,
            currentEndDate: event.endDate,
            currentReadStatus: event.readStatus ?? ReadStatusFilter.all,
          ),
        );
      } else if (state is ArticlesLoaded) {
        // 加载更多，追加到现有列表
        final currentState = state as ArticlesLoaded;
        final updatedArticles = [...currentState.articles, ...articles];

        emit(
          ArticlesLoaded(
            articles: updatedArticles,
            pagination: pagination,
            currentSource: event.source,
            currentQuery: event.query,
            currentStartDate: event.startDate,
            currentEndDate: event.endDate,
            currentReadStatus:
                event.readStatus ?? currentState.currentReadStatus,
          ),
        );
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
    add(
      LoadArticles(
        page: 1,
        source: event.source,
        query: event.query,
        startDate: event.startDate,
        endDate: event.endDate,
        readStatus: event.readStatus,
        isRefresh: true,
      ),
    );
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

      add(
        LoadArticles(
          page: currentState.pagination.currentPage + 1,
          source: currentState.currentSource,
          query: currentState.currentQuery,
          startDate: currentState.currentStartDate,
          endDate: currentState.currentEndDate,
          readStatus: currentState.currentReadStatus,
        ),
      );
    }
  }

  /// 处理更新文章已读状态事件
  void _onUpdateArticleReadStatus(
    UpdateArticleReadStatus event,
    Emitter<ArticlesState> emit,
  ) {
    if (state is ArticlesLoaded) {
      final currentState = state as ArticlesLoaded;

      // 查找并更新对应的文章
      final updatedArticles = currentState.articles.map((article) {
        if (article.postId == event.postId) {
          return article.copyWith(isRead: event.isRead, readAt: event.readAt);
        }
        return article;
      }).toList();

      // 根据当前筛选条件过滤文章列表
      final filteredArticles = _applyReadStatusFilter(
        updatedArticles,
        currentState.currentReadStatus,
      );

      emit(currentState.copyWith(articles: filteredArticles));
    }
  }

  /// 处理更新筛选条件事件
  void _onUpdateFilters(UpdateFilters event, Emitter<ArticlesState> emit) {
    if (state is ArticlesLoaded) {
      final currentState = state as ArticlesLoaded;

      // 检查筛选条件是否发生变化
      final hasSourceChanged = event.source != currentState.currentSource;
      final hasReadStatusChanged =
          event.readStatus != null &&
          event.readStatus != currentState.currentReadStatus;
      final hasDateChanged =
          event.startDate != currentState.currentStartDate ||
          event.endDate != currentState.currentEndDate;

      if (hasSourceChanged || hasReadStatusChanged || hasDateChanged) {
        // 筛选条件发生变化，重新加载数据
        add(
          LoadArticles(
            page: 1,
            source: event.source ?? currentState.currentSource,
            readStatus: event.readStatus ?? currentState.currentReadStatus,
            startDate: event.startDate ?? currentState.currentStartDate,
            endDate: event.endDate ?? currentState.currentEndDate,
          ),
        );
      }
    } else {
      // 如果当前状态不是ArticlesLoaded，直接加载
      add(
        LoadArticles(
          page: 1,
          source: event.source,
          readStatus: event.readStatus,
          startDate: event.startDate,
          endDate: event.endDate,
        ),
      );
    }
  }

  /// 便捷方法：根据已读状态筛选
  void filterByReadStatus(ReadStatusFilter readStatus) {
    add(UpdateFilters(readStatus: readStatus));
  }

  /// 便捷方法：根据来源筛选
  void filterBySource(String? source) {
    add(UpdateFilters(source: source));
  }

  /// 便捷方法：更新文章状态
  void updateArticleStatus(String postId, bool isRead, DateTime? readAt) {
    add(
      UpdateArticleReadStatus(postId: postId, isRead: isRead, readAt: readAt),
    );
  }

  /// 根据已读状态筛选条件过滤文章列表
  List<Article> _applyReadStatusFilter(
    List<Article> articles,
    ReadStatusFilter filter,
  ) {
    switch (filter) {
      case ReadStatusFilter.read:
        return articles.where((article) => article.isRead).toList();
      case ReadStatusFilter.unread:
        return articles.where((article) => !article.isRead).toList();
      case ReadStatusFilter.all:
        return articles;
    }
  }
}

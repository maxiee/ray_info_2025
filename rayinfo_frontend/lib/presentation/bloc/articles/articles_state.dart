import 'package:equatable/equatable.dart';
import '../../../domain/entities/article.dart';
import '../../../domain/entities/pagination.dart';
import '../../../data/models/read_status_models.dart';

/// 资讯列表状态
abstract class ArticlesState extends Equatable {
  const ArticlesState();
  
  @override
  List<Object?> get props => [];
}

/// 初始状态
class ArticlesInitial extends ArticlesState {}

/// 加载中状态
class ArticlesLoading extends ArticlesState {}

/// 加载成功状态
class ArticlesLoaded extends ArticlesState {
  final List<Article> articles;
  final Pagination pagination;
  final bool isLoadingMore;
  final String? currentSource;
  final String? currentQuery;
  final DateTime? currentStartDate;
  final DateTime? currentEndDate;
  final ReadStatusFilter currentReadStatus; // 新增已读状态筛选
  
  const ArticlesLoaded({
    required this.articles,
    required this.pagination,
    this.isLoadingMore = false,
    this.currentSource,
    this.currentQuery,
    this.currentStartDate,
    this.currentEndDate,
    this.currentReadStatus = ReadStatusFilter.all,
  });
  
  /// 复制状态并更新部分字段
  ArticlesLoaded copyWith({
    List<Article>? articles,
    Pagination? pagination,
    bool? isLoadingMore,
    String? currentSource,
    String? currentQuery,
    DateTime? currentStartDate,
    DateTime? currentEndDate,
    ReadStatusFilter? currentReadStatus,
  }) {
    return ArticlesLoaded(
      articles: articles ?? this.articles,
      pagination: pagination ?? this.pagination,
      isLoadingMore: isLoadingMore ?? this.isLoadingMore,
      currentSource: currentSource ?? this.currentSource,
      currentQuery: currentQuery ?? this.currentQuery,
      currentStartDate: currentStartDate ?? this.currentStartDate,
      currentEndDate: currentEndDate ?? this.currentEndDate,
      currentReadStatus: currentReadStatus ?? this.currentReadStatus,
    );
  }
  
  @override
  List<Object?> get props => [
    articles,
    pagination,
    isLoadingMore,
    currentSource,
    currentQuery,
    currentStartDate,
    currentEndDate,
    currentReadStatus,
  ];
}

/// 加载失败状态
class ArticlesError extends ArticlesState {
  final String message;
  
  const ArticlesError(this.message);
  
  @override
  List<Object?> get props => [message];
}
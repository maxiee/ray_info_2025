import 'package:equatable/equatable.dart';
import '../../../domain/entities/article.dart';
import '../../../domain/entities/pagination.dart';

/// 资讯列表事件
abstract class ArticlesEvent extends Equatable {
  const ArticlesEvent();
  
  @override
  List<Object?> get props => [];
}

/// 加载资讯列表事件
class LoadArticles extends ArticlesEvent {
  final int page;
  final int limit;
  final String? source;
  final String? query;
  final DateTime? startDate;
  final DateTime? endDate;
  final bool isRefresh;
  
  const LoadArticles({
    this.page = 1,
    this.limit = 20,
    this.source,
    this.query,
    this.startDate,
    this.endDate,
    this.isRefresh = false,
  });
  
  @override
  List<Object?> get props => [
    page, limit, source, query, startDate, endDate, isRefresh
  ];
}

/// 刷新资讯列表事件
class RefreshArticles extends ArticlesEvent {
  final String? source;
  final String? query;
  final DateTime? startDate;
  final DateTime? endDate;
  
  const RefreshArticles({
    this.source,
    this.query,
    this.startDate,
    this.endDate,
  });
  
  @override
  List<Object?> get props => [source, query, startDate, endDate];
}

/// 加载更多资讯事件
class LoadMoreArticles extends ArticlesEvent {
  const LoadMoreArticles();
}
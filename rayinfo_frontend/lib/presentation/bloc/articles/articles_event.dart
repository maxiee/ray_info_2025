import 'package:equatable/equatable.dart';
import '../../../data/models/read_status_models.dart';

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
  final String? instanceId; // 新增实例ID参数
  final String? query;
  final DateTime? startDate;
  final DateTime? endDate;
  final ReadStatusFilter? readStatus; // 新增已读状态筛选
  final bool isRefresh;

  const LoadArticles({
    this.page = 1,
    this.limit = 20,
    this.source,
    this.instanceId, // 新增实例ID参数
    this.query,
    this.startDate,
    this.endDate,
    this.readStatus,
    this.isRefresh = false,
  });

  @override
  List<Object?> get props => [
    page,
    limit,
    source,
    instanceId,
    query,
    startDate,
    endDate,
    readStatus,
    isRefresh,
  ];
}

/// 刷新资讯列表事件
class RefreshArticles extends ArticlesEvent {
  final String? source;
  final String? instanceId; // 新增实例ID参数
  final String? query;
  final DateTime? startDate;
  final DateTime? endDate;
  final ReadStatusFilter? readStatus; // 新增已读状态筛选

  const RefreshArticles({
    this.source,
    this.instanceId, // 新增实例ID参数
    this.query,
    this.startDate,
    this.endDate,
    this.readStatus,
  });

  @override
  List<Object?> get props => [
    source,
    instanceId,
    query,
    startDate,
    endDate,
    readStatus,
  ];
}

/// 加载更多资讯事件
class LoadMoreArticles extends ArticlesEvent {
  const LoadMoreArticles();
}

/// 更新单篇资讯已读状态事件
class UpdateArticleReadStatus extends ArticlesEvent {
  final String postId;
  final bool isRead;
  final DateTime? readAt;

  const UpdateArticleReadStatus({
    required this.postId,
    required this.isRead,
    this.readAt,
  });

  @override
  List<Object?> get props => [postId, isRead, readAt];
}

/// 更新筛选条件事件
class UpdateFilters extends ArticlesEvent {
  final String? source;
  final ReadStatusFilter? readStatus;
  final DateTime? startDate;
  final DateTime? endDate;

  const UpdateFilters({
    this.source,
    this.readStatus,
    this.startDate,
    this.endDate,
  });

  @override
  List<Object?> get props => [source, readStatus, startDate, endDate];
}

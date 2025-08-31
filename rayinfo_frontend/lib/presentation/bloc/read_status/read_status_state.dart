import 'package:equatable/equatable.dart';
import '../../../data/models/read_status_models.dart';

/// 已读状态状态基类
abstract class ReadStatusState extends Equatable {
  const ReadStatusState();

  @override
  List<Object?> get props => [];
}

/// 初始状态
class ReadStatusInitial extends ReadStatusState {
  const ReadStatusInitial();
}

/// 加载中状态
class ReadStatusLoading extends ReadStatusState {
  final String? postId; // 可选，标识正在处理的特定资讯
  
  const ReadStatusLoading({this.postId});

  @override
  List<Object?> get props => [postId];
}

/// 切换成功状态
class ReadStatusSuccess extends ReadStatusState {
  final String postId;
  final bool isRead;
  final DateTime? readAt;
  final DateTime updatedAt;

  const ReadStatusSuccess({
    required this.postId,
    required this.isRead,
    this.readAt,
    required this.updatedAt,
  });

  @override
  List<Object?> get props => [postId, isRead, readAt, updatedAt];
}

/// 批量操作成功状态
class BatchReadStatusSuccess extends ReadStatusState {
  final int successCount;
  final int failedCount;
  final List<ReadStatusResponse> results;

  const BatchReadStatusSuccess({
    required this.successCount,
    required this.failedCount,
    required this.results,
  });

  @override
  List<Object?> get props => [successCount, failedCount, results];
}

/// 获取已读状态成功
class ReadStatusFetched extends ReadStatusState {
  final ReadStatusResponse readStatus;

  const ReadStatusFetched({required this.readStatus});

  @override
  List<Object?> get props => [readStatus];
}

/// 错误状态
class ReadStatusError extends ReadStatusState {
  final String message;
  final String? postId; // 可选，标识出错的特定资讯

  const ReadStatusError({
    required this.message,
    this.postId,
  });

  @override
  List<Object?> get props => [message, postId];
}

/// 网络错误状态（可重试）
class ReadStatusNetworkError extends ReadStatusState {
  final String message;
  final String? postId;

  const ReadStatusNetworkError({
    required this.message,
    this.postId,
  });

  @override
  List<Object?> get props => [message, postId];
}
import 'package:equatable/equatable.dart';

/// 已读状态事件基类
abstract class ReadStatusEvent extends Equatable {
  const ReadStatusEvent();

  @override
  List<Object?> get props => [];
}

/// 切换单篇资讯的已读状态事件
class ToggleReadStatus extends ReadStatusEvent {
  final String postId;
  final bool isRead;

  const ToggleReadStatus({
    required this.postId,
    required this.isRead,
  });

  @override
  List<Object?> get props => [postId, isRead];
}

/// 批量切换已读状态事件
class BatchToggleReadStatus extends ReadStatusEvent {
  final List<String> postIds;
  final bool isRead;

  const BatchToggleReadStatus({
    required this.postIds,
    required this.isRead,
  });

  @override
  List<Object?> get props => [postIds, isRead];
}

/// 获取单篇资讯已读状态事件
class GetReadStatus extends ReadStatusEvent {
  final String postId;

  const GetReadStatus({required this.postId});

  @override
  List<Object?> get props => [postId];
}

/// 重置已读状态事件
class ResetReadStatus extends ReadStatusEvent {
  const ResetReadStatus();
}
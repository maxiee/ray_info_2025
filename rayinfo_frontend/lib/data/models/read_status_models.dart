/// 已读状态相关的数据模型
/// 用于与后端API进行已读状态相关的数据交互
library;

/// 已读状态请求模型
class ReadStatusRequest {
  final bool isRead;
  
  const ReadStatusRequest({required this.isRead});
  
  /// 转换为 JSON
  Map<String, dynamic> toJson() {
    return {
      'is_read': isRead,
    };
  }
}

/// 批量已读状态请求模型
class BatchReadStatusRequest {
  final List<String> postIds;
  final bool isRead;
  
  const BatchReadStatusRequest({
    required this.postIds,
    required this.isRead,
  });
  
  /// 转换为 JSON
  Map<String, dynamic> toJson() {
    return {
      'post_ids': postIds,
      'is_read': isRead,
    };
  }
}

/// 已读状态响应模型
class ReadStatusResponse {
  final String postId;
  final bool isRead;
  final DateTime? readAt;
  final DateTime updatedAt;
  
  const ReadStatusResponse({
    required this.postId,
    required this.isRead,
    this.readAt,
    required this.updatedAt,
  });
  
  /// 从 JSON 创建响应实例
  factory ReadStatusResponse.fromJson(Map<String, dynamic> json) {
    return ReadStatusResponse(
      postId: json['post_id'] as String,
      isRead: json['is_read'] as bool,
      readAt: json['read_at'] != null 
          ? DateTime.parse(json['read_at'] as String) 
          : null,
      updatedAt: DateTime.parse(json['updated_at'] as String),
    );
  }
  
  /// 转换为 JSON
  Map<String, dynamic> toJson() {
    return {
      'post_id': postId,
      'is_read': isRead,
      'read_at': readAt?.toIso8601String(),
      'updated_at': updatedAt.toIso8601String(),
    };
  }
}

/// 批量已读状态响应模型
class BatchReadStatusResponse {
  final int successCount;
  final int failedCount;
  final List<ReadStatusResponse> results;
  
  const BatchReadStatusResponse({
    required this.successCount,
    required this.failedCount,
    required this.results,
  });
  
  /// 从 JSON 创建响应实例
  factory BatchReadStatusResponse.fromJson(Map<String, dynamic> json) {
    return BatchReadStatusResponse(
      successCount: json['success_count'] as int,
      failedCount: json['failed_count'] as int,
      results: (json['results'] as List<dynamic>)
          .map((item) => ReadStatusResponse.fromJson(item as Map<String, dynamic>))
          .toList(),
    );
  }
  
  /// 转换为 JSON
  Map<String, dynamic> toJson() {
    return {
      'success_count': successCount,
      'failed_count': failedCount,
      'results': results.map((result) => result.toJson()).toList(),
    };
  }
}

/// 已读状态筛选枚举
enum ReadStatusFilter {
  all,
  read,
  unread,
}

/// 扩展方法，将枚举转换为API参数
extension ReadStatusFilterExtension on ReadStatusFilter {
  String toApiParam() {
    switch (this) {
      case ReadStatusFilter.all:
        return 'all';
      case ReadStatusFilter.read:
        return 'read';
      case ReadStatusFilter.unread:
        return 'unread';
    }
  }
  
  /// 从字符串解析
  static ReadStatusFilter fromString(String value) {
    switch (value.toLowerCase()) {
      case 'read':
        return ReadStatusFilter.read;
      case 'unread':
        return ReadStatusFilter.unread;
      case 'all':
      default:
        return ReadStatusFilter.all;
    }
  }
}
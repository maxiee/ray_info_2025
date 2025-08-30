import 'package:equatable/equatable.dart';

/// 来源统计模型
class Source extends Equatable {
  final String name;
  final String displayName;
  final int count;
  final DateTime? latestUpdate;
  
  const Source({
    required this.name,
    required this.displayName,
    required this.count,
    this.latestUpdate,
  });
  
  /// 从 JSON 创建 Source 实例
  factory Source.fromJson(Map<String, dynamic> json) {
    return Source(
      name: json['name'] as String,
      displayName: json['display_name'] as String,
      count: json['count'] as int,
      latestUpdate: json['latest_update'] != null 
          ? DateTime.parse(json['latest_update'] as String)
          : null,
    );
  }
  
  /// 转换为 JSON
  Map<String, dynamic> toJson() {
    return {
      'name': name,
      'display_name': displayName,
      'count': count,
      if (latestUpdate != null) 'latest_update': latestUpdate!.toIso8601String(),
    };
  }
  
  /// 获取相对更新时间
  String get relativeUpdateTime {
    if (latestUpdate == null) return '未知';
    
    final now = DateTime.now();
    final difference = now.difference(latestUpdate!);
    
    if (difference.inMinutes < 1) {
      return '刚刚更新';
    } else if (difference.inHours < 1) {
      return '${difference.inMinutes}分钟前更新';
    } else if (difference.inDays < 1) {
      return '${difference.inHours}小时前更新';
    } else if (difference.inDays < 7) {
      return '${difference.inDays}天前更新';
    } else {
      return '${latestUpdate!.month}月${latestUpdate!.day}日更新';
    }
  }
  
  @override
  List<Object?> get props => [name, displayName, count, latestUpdate];
}
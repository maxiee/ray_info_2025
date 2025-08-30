import 'package:equatable/equatable.dart';

/// 资讯实体模型
class Article extends Equatable {
  final String postId;
  final String source;
  final String? title;
  final String? url;
  final String? description;
  final String? query;
  final String? engine;
  final DateTime collectedAt;
  final int processed;
  final Map<String, dynamic>? rawData; // 详情页专用
  
  const Article({
    required this.postId,
    required this.source,
    this.title,
    this.url,
    this.description,
    this.query,
    this.engine,
    required this.collectedAt,
    required this.processed,
    this.rawData,
  });
  
  /// 从 JSON 创建 Article 实例
  factory Article.fromJson(Map<String, dynamic> json) {
    return Article(
      postId: json['post_id'] as String,
      source: json['source'] as String,
      title: json['title'] as String?,
      url: json['url'] as String?,
      description: json['description'] as String?,
      query: json['query'] as String?,
      engine: json['engine'] as String?,
      collectedAt: DateTime.parse(json['collected_at'] as String),
      processed: json['processed'] as int,
      rawData: json['raw_data'] as Map<String, dynamic>?,
    );
  }
  
  /// 转换为 JSON
  Map<String, dynamic> toJson() {
    return {
      'post_id': postId,
      'source': source,
      'title': title,
      'url': url,
      'description': description,
      'query': query,
      'engine': engine,
      'collected_at': collectedAt.toIso8601String(),
      'processed': processed,
      if (rawData != null) 'raw_data': rawData,
    };
  }
  
  /// 获取来源显示名称
  String get sourceDisplayName {
    const sourceNames = {
      'mes.search': '搜索引擎',
      'weibo.home': '微博首页',
      'rss.feed': 'RSS订阅',
    };
    return sourceNames[source] ?? source;
  }
  
  /// 获取短描述（限制长度）
  String? get shortDescription {
    if (description == null || description!.isEmpty) return null;
    return description!.length > 100 
        ? '${description!.substring(0, 100)}...' 
        : description;
  }
  
  /// 获取相对时间显示
  String get relativeTime {
    final now = DateTime.now();
    final difference = now.difference(collectedAt);
    
    if (difference.inMinutes < 1) {
      return '刚刚';
    } else if (difference.inHours < 1) {
      return '${difference.inMinutes}分钟前';
    } else if (difference.inDays < 1) {
      return '${difference.inHours}小时前';
    } else if (difference.inDays < 7) {
      return '${difference.inDays}天前';
    } else {
      return '${collectedAt.month}月${collectedAt.day}日';
    }
  }
  
  @override
  List<Object?> get props => [
    postId,
    source,
    title,
    url,
    description,
    query,
    engine,
    collectedAt,
    processed,
  ];
}
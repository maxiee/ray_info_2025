import '../../domain/entities/source.dart';

/// 来源统计响应模型
class SourcesResponse {
  final List<Source> sources;
  
  const SourcesResponse({
    required this.sources,
  });
  
  /// 从 JSON 创建响应实例
  factory SourcesResponse.fromJson(Map<String, dynamic> json) {
    return SourcesResponse(
      sources: (json['sources'] as List<dynamic>)
          .map((item) => Source.fromJson(item as Map<String, dynamic>))
          .toList(),
    );
  }
  
  /// 转换为 JSON
  Map<String, dynamic> toJson() {
    return {
      'sources': sources.map((source) => source.toJson()).toList(),
    };
  }
}
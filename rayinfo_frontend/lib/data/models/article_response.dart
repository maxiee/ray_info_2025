import '../../domain/entities/article.dart';
import '../../domain/entities/pagination.dart';

/// 分页资讯响应模型
class PaginatedArticlesResponse {
  final List<Article> data;
  final Pagination pagination;
  
  const PaginatedArticlesResponse({
    required this.data,
    required this.pagination,
  });
  
  /// 从 JSON 创建响应实例
  factory PaginatedArticlesResponse.fromJson(Map<String, dynamic> json) {
    return PaginatedArticlesResponse(
      data: (json['data'] as List<dynamic>)
          .map((item) => Article.fromJson(item as Map<String, dynamic>))
          .toList(),
      pagination: Pagination.fromJson(json['pagination'] as Map<String, dynamic>),
    );
  }
  
  /// 转换为 JSON
  Map<String, dynamic> toJson() {
    return {
      'data': data.map((article) => article.toJson()).toList(),
      'pagination': pagination.toJson(),
    };
  }
}
import '../../core/network/api_client.dart';
import '../models/article_response.dart';
import '../models/source_response.dart';
import '../../domain/entities/article.dart';

/// API数据源接口
abstract class ApiDataSource {
  /// 获取分页资讯列表
  Future<PaginatedArticlesResponse> getArticles({
    int page = 1,
    int limit = 20,
    String? source,
    String? query,
    DateTime? startDate,
    DateTime? endDate,
  });
  
  /// 获取资讯详情
  Future<Article> getArticleDetail(String postId);
  
  /// 搜索资讯
  Future<PaginatedArticlesResponse> searchArticles({
    required String searchQuery,
    int page = 1,
    int limit = 20,
    String? source,
    DateTime? startDate,
    DateTime? endDate,
  });
  
  /// 获取来源统计
  Future<SourcesResponse> getSources();
}

/// API数据源实现
class ApiDataSourceImpl implements ApiDataSource {
  final ApiClient _apiClient;
  
  ApiDataSourceImpl(this._apiClient);
  
  @override
  Future<PaginatedArticlesResponse> getArticles({
    int page = 1,
    int limit = 20,
    String? source,
    String? query,
    DateTime? startDate,
    DateTime? endDate,
  }) async {
    final queryParameters = <String, dynamic>{
      'page': page,
      'limit': limit,
    };
    
    if (source != null) queryParameters['source'] = source;
    if (query != null) queryParameters['query'] = query;
    if (startDate != null) queryParameters['start_date'] = startDate.toIso8601String();
    if (endDate != null) queryParameters['end_date'] = endDate.toIso8601String();
    
    final response = await _apiClient.get(
      '/articles',
      queryParameters: queryParameters,
    );
    
    return PaginatedArticlesResponse.fromJson(response.data as Map<String, dynamic>);
  }
  
  @override
  Future<Article> getArticleDetail(String postId) async {
    final response = await _apiClient.get('/articles/$postId');
    return Article.fromJson(response.data as Map<String, dynamic>);
  }
  
  @override
  Future<PaginatedArticlesResponse> searchArticles({
    required String searchQuery,
    int page = 1,
    int limit = 20,
    String? source,
    DateTime? startDate,
    DateTime? endDate,
  }) async {
    final queryParameters = <String, dynamic>{
      'q': searchQuery,
      'page': page,
      'limit': limit,
    };
    
    if (source != null) queryParameters['source'] = source;
    if (startDate != null) queryParameters['start_date'] = startDate.toIso8601String();
    if (endDate != null) queryParameters['end_date'] = endDate.toIso8601String();
    
    final response = await _apiClient.get(
      '/search',
      queryParameters: queryParameters,
    );
    
    return PaginatedArticlesResponse.fromJson(response.data as Map<String, dynamic>);
  }
  
  @override
  Future<SourcesResponse> getSources() async {
    final response = await _apiClient.get('/sources');
    return SourcesResponse.fromJson(response.data as Map<String, dynamic>);
  }
}
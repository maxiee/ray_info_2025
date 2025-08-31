import '../../core/network/api_client.dart';
import '../models/article_response.dart';
import '../models/source_response.dart';
import '../models/read_status_models.dart';
import '../models/collector_models.dart';
import '../../domain/entities/article.dart';

/// API数据源接口
abstract class ApiDataSource {
  /// 获取分页资讯列表
  Future<PaginatedArticlesResponse> getArticles({
    int page = 1,
    int limit = 20,
    String? source,
    String? instanceId, // 新增实例ID参数
    String? query,
    DateTime? startDate,
    DateTime? endDate,
    ReadStatusFilter? readStatus, // 新增参数
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

  /// 获取采集器列表（按类型分组）
  Future<CollectorsResponse> getCollectors();

  // 已读状态相关方法

  /// 切换单篇资讯的已读状态
  Future<ReadStatusResponse> toggleReadStatus(
    String postId,
    ReadStatusRequest request,
  );

  /// 批量切换资讯的已读状态
  Future<BatchReadStatusResponse> batchToggleReadStatus(
    BatchReadStatusRequest request,
  );

  /// 获取单篇资讯的已读状态
  Future<ReadStatusResponse> getReadStatus(String postId);
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
    String? instanceId, // 新增实例ID参数
    String? query,
    DateTime? startDate,
    DateTime? endDate,
    ReadStatusFilter? readStatus, // 新增参数
  }) async {
    final queryParameters = <String, dynamic>{'page': page, 'limit': limit};

    if (source != null) queryParameters['source'] = source;
    if (instanceId != null)
      queryParameters['instance_id'] = instanceId; // 新增实例ID参数
    if (query != null) queryParameters['query'] = query;
    if (startDate != null)
      queryParameters['start_date'] = startDate.toIso8601String();
    if (endDate != null)
      queryParameters['end_date'] = endDate.toIso8601String();
    if (readStatus != null)
      queryParameters['read_status'] = readStatus.toApiParam(); // 添加已读状态参数

    final response = await _apiClient.get(
      '/articles',
      queryParameters: queryParameters,
    );

    return PaginatedArticlesResponse.fromJson(
      response.data as Map<String, dynamic>,
    );
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
    if (startDate != null)
      queryParameters['start_date'] = startDate.toIso8601String();
    if (endDate != null)
      queryParameters['end_date'] = endDate.toIso8601String();

    final response = await _apiClient.get(
      '/search',
      queryParameters: queryParameters,
    );

    return PaginatedArticlesResponse.fromJson(
      response.data as Map<String, dynamic>,
    );
  }

  @override
  Future<SourcesResponse> getSources() async {
    final response = await _apiClient.get('/sources');
    return SourcesResponse.fromJson(response.data as Map<String, dynamic>);
  }

  @override
  Future<CollectorsResponse> getCollectors() async {
    final response = await _apiClient.get('/collectors');
    return CollectorsResponse.fromJson(response.data as Map<String, dynamic>);
  }

  // 已读状态相关方法实现

  @override
  Future<ReadStatusResponse> toggleReadStatus(
    String postId,
    ReadStatusRequest request,
  ) async {
    final response = await _apiClient.put(
      '/articles/$postId/read-status',
      data: request.toJson(),
    );

    return ReadStatusResponse.fromJson(response.data as Map<String, dynamic>);
  }

  @override
  Future<BatchReadStatusResponse> batchToggleReadStatus(
    BatchReadStatusRequest request,
  ) async {
    final response = await _apiClient.put(
      '/articles/batch-read-status',
      data: request.toJson(),
    );

    return BatchReadStatusResponse.fromJson(
      response.data as Map<String, dynamic>,
    );
  }

  @override
  Future<ReadStatusResponse> getReadStatus(String postId) async {
    final response = await _apiClient.get('/articles/$postId/read-status');
    return ReadStatusResponse.fromJson(response.data as Map<String, dynamic>);
  }
}

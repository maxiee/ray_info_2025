import '../../domain/repositories/article_repository.dart';
import '../../domain/entities/article.dart';
import '../../domain/entities/source.dart';
import '../../domain/entities/pagination.dart';
import '../datasources/api_datasource.dart';

/// 资讯Repository实现
class ArticleRepositoryImpl implements ArticleRepository {
  final ApiDataSource _apiDataSource;
  
  ArticleRepositoryImpl(this._apiDataSource);
  
  @override
  Future<(List<Article>, Pagination)> getArticles({
    int page = 1,
    int limit = 20,
    String? source,
    String? query,
    DateTime? startDate,
    DateTime? endDate,
  }) async {
    try {
      final response = await _apiDataSource.getArticles(
        page: page,
        limit: limit,
        source: source,
        query: query,
        startDate: startDate,
        endDate: endDate,
      );
      
      return (response.data, response.pagination);
    } catch (e) {
      throw Exception('获取资讯列表失败: $e');
    }
  }
  
  @override
  Future<Article> getArticleDetail(String postId) async {
    try {
      return await _apiDataSource.getArticleDetail(postId);
    } catch (e) {
      throw Exception('获取资讯详情失败: $e');
    }
  }
  
  @override
  Future<(List<Article>, Pagination)> searchArticles({
    required String searchQuery,
    int page = 1,
    int limit = 20,
    String? source,
    DateTime? startDate,
    DateTime? endDate,
  }) async {
    try {
      final response = await _apiDataSource.searchArticles(
        searchQuery: searchQuery,
        page: page,
        limit: limit,
        source: source,
        startDate: startDate,
        endDate: endDate,
      );
      
      return (response.data, response.pagination);
    } catch (e) {
      throw Exception('搜索资讯失败: $e');
    }
  }
  
  @override
  Future<List<Source>> getSources() async {
    try {
      final response = await _apiDataSource.getSources();
      return response.sources;
    } catch (e) {
      throw Exception('获取来源统计失败: $e');
    }
  }
}
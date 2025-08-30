import '../entities/article.dart';
import '../entities/source.dart';
import '../entities/pagination.dart';

/// 资讯Repository接口
abstract class ArticleRepository {
  /// 获取分页资讯列表
  Future<(List<Article>, Pagination)> getArticles({
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
  Future<(List<Article>, Pagination)> searchArticles({
    required String searchQuery,
    int page = 1,
    int limit = 20,
    String? source,
    DateTime? startDate,
    DateTime? endDate,
  });
  
  /// 获取来源统计
  Future<List<Source>> getSources();
}
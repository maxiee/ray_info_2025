import '../entities/article.dart';
import '../entities/source.dart';
import '../entities/pagination.dart';
import '../../data/models/read_status_models.dart';

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
    ReadStatusFilter? readStatus, // 新增已读状态筛选
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
  
  // 已读状态相关方法
  
  /// 切换单篇资讯的已读状态
  Future<ReadStatusResponse> toggleReadStatus(
    String postId, 
    ReadStatusRequest request
  );
  
  /// 批量切换资讯的已读状态
  Future<BatchReadStatusResponse> batchToggleReadStatus(
    BatchReadStatusRequest request
  );
  
  /// 获取单篇资讯的已读状态
  Future<ReadStatusResponse> getReadStatus(String postId);
}
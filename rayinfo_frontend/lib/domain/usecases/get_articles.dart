import '../entities/article.dart';
import '../entities/pagination.dart';
import '../repositories/article_repository.dart';
import '../../data/models/read_status_models.dart';

/// 获取资讯列表用例
class GetArticlesUseCase {
  final ArticleRepository _repository;

  GetArticlesUseCase(this._repository);

  /// 执行获取资讯列表
  Future<(List<Article>, Pagination)> call({
    int page = 1,
    int limit = 20,
    String? source,
    String? instanceId, // 新增实例ID参数
    String? query,
    DateTime? startDate,
    DateTime? endDate,
    ReadStatusFilter? readStatus, // 新增已读状态筛选
  }) async {
    if (page < 1) {
      throw ArgumentError('页码必须大于0');
    }

    if (limit < 1 || limit > 100) {
      throw ArgumentError('每页条数必须在1-100之间');
    }

    return await _repository.getArticles(
      page: page,
      limit: limit,
      source: source,
      instanceId: instanceId,
      query: query,
      startDate: startDate,
      endDate: endDate,
      readStatus: readStatus,
    );
  }
}

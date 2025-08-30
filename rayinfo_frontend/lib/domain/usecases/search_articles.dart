import '../entities/article.dart';
import '../entities/pagination.dart';
import '../repositories/article_repository.dart';

/// 搜索资讯用例
class SearchArticlesUseCase {
  final ArticleRepository _repository;
  
  SearchArticlesUseCase(this._repository);
  
  /// 执行搜索
  Future<(List<Article>, Pagination)> call({
    required String searchQuery,
    int page = 1,
    int limit = 20,
    String? source,
    DateTime? startDate,
    DateTime? endDate,
  }) async {
    if (searchQuery.isEmpty) {
      throw ArgumentError('搜索关键词不能为空');
    }
    
    if (page < 1) {
      throw ArgumentError('页码必须大于0');
    }
    
    if (limit < 1 || limit > 100) {
      throw ArgumentError('每页条数必须在1-100之间');
    }
    
    return await _repository.searchArticles(
      searchQuery: searchQuery,
      page: page,
      limit: limit,
      source: source,
      startDate: startDate,
      endDate: endDate,
    );
  }
}
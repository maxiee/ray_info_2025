import '../entities/article.dart';
import '../repositories/article_repository.dart';

/// 获取资讯详情用例
class GetArticleDetailUseCase {
  final ArticleRepository _repository;
  
  GetArticleDetailUseCase(this._repository);
  
  /// 执行获取资讯详情
  Future<Article> call(String postId) async {
    if (postId.isEmpty) {
      throw ArgumentError('资讯ID不能为空');
    }
    
    return await _repository.getArticleDetail(postId);
  }
}
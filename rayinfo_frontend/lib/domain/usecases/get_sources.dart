import '../entities/source.dart';
import '../repositories/article_repository.dart';

/// 获取来源统计用例
class GetSourcesUseCase {
  final ArticleRepository _repository;
  
  GetSourcesUseCase(this._repository);
  
  /// 执行获取来源统计
  Future<List<Source>> call() async {
    return await _repository.getSources();
  }
}
import '../../data/models/collector_models.dart';
import '../repositories/collector_repository.dart';

/// 获取采集器列表用例
class GetCollectorsUseCase {
  final CollectorRepository _repository;

  GetCollectorsUseCase(this._repository);

  /// 执行获取采集器列表操作
  Future<CollectorsResponse> call() async {
    return await _repository.getCollectors();
  }
}

import '../../data/models/collector_models.dart';

/// 采集器仓库接口
abstract class CollectorRepository {
  /// 获取采集器列表（按类型分组）
  Future<CollectorsResponse> getCollectors();
}

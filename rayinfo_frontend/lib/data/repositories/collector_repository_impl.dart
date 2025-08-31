import '../../domain/repositories/collector_repository.dart';
import '../datasources/api_datasource.dart';
import '../models/collector_models.dart';

/// 采集器仓库实现
class CollectorRepositoryImpl implements CollectorRepository {
  final ApiDataSource _apiDataSource;

  CollectorRepositoryImpl(this._apiDataSource);

  @override
  Future<CollectorsResponse> getCollectors() async {
    try {
      return await _apiDataSource.getCollectors();
    } catch (e) {
      throw Exception('获取采集器列表失败: $e');
    }
  }
}
